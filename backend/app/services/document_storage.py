"""Disk storage + text extraction for chat documents (PDF, DOCX, TXT).

Mirrors image_storage: the type is detected from the file contents (never the
filename alone), files are saved under a random server-generated name, and
SQLite only keeps the key, metadata and extracted text.
"""
import asyncio
import base64
import io
import re
import threading
import unicodedata
import uuid
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings
from app.services.image_storage import detect_image_type

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT_MIME = "text/plain"

_EXT = {PDF_MIME: "pdf", DOCX_MIME: "docx", TXT_MIME: "txt"}
_KEY_RE = re.compile(r"^[0-9a-f]{32}\.(pdf|docx|txt)$")

# Guards against decompression bombs / pathological files
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DOCX_ENTRIES = 2000
MAX_PDF_PAGES = 300


class DocumentError(Exception):
    """A user-facing problem with an uploaded document."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------- Type detection ----------

def _decode_text(data: bytes) -> Optional[str]:
    """Plain text must decode cleanly and contain no NUL bytes (binary files do)."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError:
            return None
    else:
        if b"\x00" in data:
            return None
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
    return None if "\x00" in text else text


def _is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return False
    return "word/document.xml" in names and "[Content_Types].xml" in names


def detect_document_type(data: bytes, filename: str) -> Optional[str]:
    if b"%PDF-" in data[:1024]:
        return PDF_MIME
    if _is_docx(data):
        return DOCX_MIME
    # Text has no magic bytes, so it also needs a .txt name AND must really be text
    if filename.lower().endswith(".txt") and _decode_text(data) is not None:
        return TXT_MIME
    return None


def validate_document(data: bytes, filename: str) -> str:
    """Returns the detected MIME type or raises DocumentError."""
    if not data:
        raise DocumentError("The file is empty.")
    if len(data) > settings.MAX_DOCUMENT_BYTES:
        raise DocumentError(
            f"File is too large (max {settings.MAX_DOCUMENT_BYTES // (1024 * 1024)} MB).", status_code=413
        )
    if detect_image_type(data):
        raise DocumentError("That's an image. Please use the image button to attach it.")
    mime = detect_document_type(data, filename)
    if not mime:
        raise DocumentError("Unsupported file type. Please upload a PDF, DOCX or TXT file.")
    return mime


# ---------- Filenames ----------

def sanitize_filename(name: str, mime: str) -> str:
    """Display/download name only; never used as a path on disk."""
    return sanitize_display_name(name, _EXT[mime], "document")


def sanitize_display_name(name: str, ext: str, fallback: str) -> str:
    """Safe display name ending in .ext (path parts, control and reserved characters removed)."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(ch for ch in unicodedata.normalize("NFC", base) if ch.isprintable() and ch not in '<>:"|?*')
    base = base.strip().lstrip(".").strip()
    if not base:
        base = f"{fallback}.{ext}"
    same_ext = base.lower().endswith(f".{ext}") or (ext == "jpg" and base.lower().endswith(".jpeg"))
    if not same_ext:
        base = f"{base}.{ext}"
    if len(base) > 150:
        base = f"{base[:140].rstrip()}….{ext}"
    return base


# ---------- Text extraction ----------

def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                ok = reader.decrypt("")
            except Exception:
                ok = 0
            if not ok:
                raise DocumentError("This PDF is password-protected. Please upload an unlocked copy.", 422)
        parts: list[str] = []
        total = 0
        for i, page in enumerate(reader.pages):
            if i >= MAX_PDF_PAGES or total > settings.MAX_DOCUMENT_TEXT_CHARS:
                break
            text = page.extract_text() or ""
            parts.append(text)
            total += len(text)
        return "\n\n".join(parts)
    except DocumentError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, RecursionError) as e:
        raise DocumentError("Could not read this PDF. It may be damaged.", 422) from e


def _extract_docx(data: bytes) -> str:
    from docx import Document

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_DOCX_ENTRIES or sum(i.file_size for i in infos) > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise DocumentError("This Word document is too complex to read.", 422)
    try:
        doc = Document(io.BytesIO(data))
        lines = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                lines.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(lines)
    except Exception as e:
        raise DocumentError("Could not read this Word document. It may be damaged.", 422) from e


# PDFs with no text layer (scans, or "Print to PDF" output where letters became
# vector outlines) are rendered to page images and read by the vision model instead.
_PDFIUM_LOCK = threading.Lock()  # pdfium is not thread-safe
PDF_RENDER_MAX_SIDE = 1400  # px, longest side of a rendered page


def render_pdf_pages(data: bytes, max_pages: int) -> Tuple[list[bytes], bool]:
    """Renders up to max_pages pages to JPEG. Returns (jpegs, all_pages_blank)."""
    import pypdfium2 as pdfium

    with _PDFIUM_LOCK:
        try:
            pdf = pdfium.PdfDocument(data)
        except Exception as e:
            raise DocumentError("Could not read this PDF. It may be damaged.", 422) from e
        try:
            jpegs: list[bytes] = []
            blank = True
            for i in range(min(len(pdf), max_pages)):
                page = pdf[i]
                width, height = page.get_size()
                scale = min(2.0, PDF_RENDER_MAX_SIDE / max(width, height, 1))
                img = page.render(scale=scale).to_pil().convert("RGB")
                low, high = img.convert("L").getextrema()
                blank = blank and (high - low) < 8
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=80)
                jpegs.append(buf.getvalue())
            return jpegs, blank
        except DocumentError:
            raise
        except Exception as e:
            raise DocumentError("Could not read this PDF. It may be damaged.", 422) from e
        finally:
            pdf.close()


async def load_pdf_page_data_urls(key: str) -> Optional[list[str]]:
    """Page images of a stored text-less PDF, as data URLs for the vision model."""
    try:
        data = await asyncio.to_thread(resolve_document_path(key).read_bytes)
        jpegs, _ = await asyncio.to_thread(render_pdf_pages, data, settings.MAX_PDF_IMAGE_PAGES)
    except (OSError, ValueError, DocumentError):
        return None
    return [f"data:image/jpeg;base64,{base64.b64encode(j).decode()}" for j in jpegs]


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_text(data: bytes, mime: str) -> Tuple[str, str]:
    """Returns (text, status). status is "ok", "truncated", or "image" for a PDF with
    no text layer whose pages will be sent to the vision model. Raises DocumentError."""
    if mime == PDF_MIME:
        raw = _extract_pdf(data)
    elif mime == DOCX_MIME:
        raw = _extract_docx(data)
    else:
        raw = _decode_text(data) or ""
    text = _clean(raw)
    if not text and mime == PDF_MIME:
        # Make sure the pages really render and aren't empty before accepting it
        jpegs, blank = render_pdf_pages(data, settings.MAX_PDF_IMAGE_PAGES)
        if not jpegs or blank:
            raise DocumentError("This PDF appears to be blank.", 422)
        return "", "image"
    if not text:
        raise DocumentError(
            "No readable text was found in this file. If it's a scanned PDF, "
            "take a photo of the page and use the image button instead.",
            422,
        )
    limit = settings.MAX_DOCUMENT_TEXT_CHARS
    if len(text) > limit:
        return text[:limit], "truncated"
    return text, "ok"


# ---------- Storage ----------

def _storage_dir() -> Path:
    path = Path(settings.DOCUMENT_STORAGE_DIR).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_document_path(key: str) -> Path:
    if not _KEY_RE.match(key or ""):
        raise ValueError("Invalid document key")
    base = _storage_dir()
    path = (base / key).resolve()
    if path.parent != base:
        raise ValueError("Invalid document key")
    return path


async def save_document(data: bytes, mime: str) -> str:
    key = f"{uuid.uuid4().hex}.{_EXT[mime]}"
    await asyncio.to_thread(resolve_document_path(key).write_bytes, data)
    return key
