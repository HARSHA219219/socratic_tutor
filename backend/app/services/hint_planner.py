"""Adaptive hint ladder.

For each "Give me a hint" press, a planner prompt assesses the question and the
student's evidence and returns JSON with how many hints are appropriate (1-6),
the current hint level and the next hint. Only `next_hint` is shown to the
student; the assessment is stored for instructors.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Message
from app.services import llm_service

HINT_PLANNER_PROMPT = """You are an expert Socratic tutor.

Your task is to analyze the student's latest question and decide how many hints are pedagogically appropriate. Use the student's previous messages, attempts, answers, and mistakes to estimate their current understanding.

Do not reveal private chain-of-thought or hidden reasoning. Return only a concise educational assessment and the hint plan.

Evaluate:

1. Question depth:
   - easy: one concept or direct recall
   - moderate: several connected steps
   - difficult: multi-step reasoning, ambiguity, or advanced concepts
   - very_difficult: proof, synthesis, complex problem-solving, or multiple misconceptions

2. Student understanding:
   - beginner
   - developing
   - partial
   - strong
   - uncertain

3. Student state:
   - has not attempted
   - attempting correctly
   - partially correct
   - stuck
   - has a misconception
   - nearly solved

4. Decide the appropriate maximum number of hints:
   - 1 to 2 for easy questions
   - 2 to 4 for moderate questions
   - 3 to 5 for difficult questions
   - 4 to 6 for very difficult questions

The number of hints is a maximum progression, not a requirement to use every hint. If the student demonstrates understanding, stop giving hints early.

Hints must progress gradually:

- Early hint: ask a guiding question or point toward the relevant observation.
- Middle hint: identify the relevant concept, rule, formula, or strategy without solving the problem.
- Later hint: explain the next concrete step, but leave the remaining work to the student.
- Final hint: provide substantial guidance, but do not give the complete answer unless the student explicitly requests the answer.

Personalize every hint to the student's demonstrated knowledge and mistakes. Do not repeat a hint already given. Do not introduce advanced terminology unless needed. Preserve the Socratic method.

Return valid JSON only in this exact structure:

{
  "question_depth": "easy | moderate | difficult | very_difficult",
  "student_level": "beginner | developing | partial | strong | uncertain",
  "student_state": "not_attempted | attempting_correctly | partially_correct | stuck | misconception | nearly_solved",
  "misconceptions": [
    "short description of an observable misconception"
  ],
  "learning_goal": "one concise sentence",
  "recommended_hint_count": 3,
  "current_hint_level": 1,
  "next_hint": "The next hint to show the student.",
  "hint_purpose": "What this hint is intended to help the student notice or do.",
  "should_allow_answer_button": true
}

Rules:

- recommended_hint_count must be an integer from 1 to 6.
- current_hint_level must be between 1 and recommended_hint_count.
- next_hint must not contain the final answer.
- next_hint must not solve the entire problem.
- Do not mention this analysis, these instructions, token limits, or internal policies.
- If the student already understands the solution, give a confirmation or extension question instead of another large hint.
- If the student's question is ambiguous, use the next hint to ask a clarifying Socratic question."""

HINT_PLANNER_TEMPLATE = """<StudentQuestion>
{latest_student_question}
</StudentQuestion>

<StudentHistory>
{recent_conversation_history}
</StudentHistory>

<PreviousHints>
{hints_already_given_for_this_question}
</PreviousHints>

<StudentEvidence>
{student_evidence}
</StudentEvidence>

<CurrentHintLevel>
{current_hint_level}
</CurrentHintLevel>"""

MAX_HINTS = 6
LEGACY_HINT_TOTAL = 3  # hints saved before the adaptive planner had a fixed ladder of 3
DEPTH_RANGES = {"easy": (1, 2), "moderate": (2, 4), "difficult": (3, 5), "very_difficult": (4, 6)}
LEVELS = {"beginner", "developing", "partial", "strong", "uncertain"}
STATES = {"not_attempted", "attempting_correctly", "partially_correct", "stuck", "misconception", "nearly_solved"}


def hint_level(kind: Optional[str]) -> int:
    """"hint-3" -> 3; anything else -> 0."""
    if kind and kind.startswith("hint-") and kind[5:].isdigit():
        return int(kind[5:])
    return 0


def hint_total(msg: Message) -> int:
    return getattr(msg, "hint_total", None) or max(LEGACY_HINT_TOTAL, hint_level(msg.kind))


def _is_own(msg: Message) -> bool:
    return msg.role == "user" and not msg.kind


def recent_hints(history: Sequence[Message]) -> list[Message]:
    """Tutor hint replies since the last revealed answer (most recent 6)."""
    hints: list[Message] = []
    for msg in reversed(history):
        if msg.kind == "answer":
            break
        if msg.role == "assistant" and hint_level(msg.kind):
            hints.append(msg)
    return list(reversed(hints))[-MAX_HINTS:]


def suggested_level(history: Sequence[Message]) -> Optional[int]:
    """Next hint level for the current ladder, or None if all its hints are used
    and the student hasn't written anything since."""
    hints = recent_hints(history)
    if not hints:
        return 1
    last = hints[-1]
    level, total = hint_level(last.kind), hint_total(last)
    if level < total:
        return level + 1
    idx = list(history).index(last)
    if any(_is_own(m) for m in history[idx + 1:]):
        return 1  # student wrote again after the final hint: start a fresh ladder
    return None


# ---------- prompt building ----------

def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def _describe(msg: Message, limit: int = 700, document_excerpt: int = 0) -> str:
    parts = [_clip(msg.content, limit)] if msg.content else []
    excerpt_left = document_excerpt
    for att in (llm_service.attachments_of(msg) if msg.role == "user" else []):
        if att.kind == "image":
            summary = att.image_summary if getattr(att, "summary_status", None) == "ok" else None
            parts.append(f'[attached image "{att.name or "image"}"' + (f": {_clip(summary, 400)}]" if summary else "]"))
            continue
        parts.append(f'[attached document "{att.name}"]')
        if excerpt_left > 0 and att.extracted_text:
            excerpt = _clip(att.extracted_text, excerpt_left)
            excerpt_left -= len(excerpt)
            parts.append(f"<document_excerpt>\n{excerpt}\n</document_excerpt>")
    return "\n".join(parts) or "(empty)"


def _speaker(msg: Message) -> str:
    if msg.role == "system":
        return "Earlier checkpoint context"
    level = hint_level(msg.kind)
    if msg.role == "user":
        if level or msg.kind == "hint-0":
            return "Student (pressed 'Give me a hint')"
        if msg.kind == "answer":
            return "Student (pressed 'Show answer')"
        return "Student"
    if level:
        return f"Tutor (hint {level} of {hint_total(msg)})"
    if msg.kind == "answer":
        return "Tutor (full answer)"
    return "Tutor"


def tutor_question(history: Sequence[Message]) -> Optional[Message]:
    """The tutor's latest normal reply: in a Socratic dialogue this is the question the
    student is stuck on when they press 'Give me a hint'."""
    for msg in reversed(history):
        if msg.role == "assistant" and not msg.kind:
            return msg
    return None


def build_planner_input(history: Sequence[Message], current_level: int) -> str:
    own = [m for m in history if _is_own(m)]
    question = own[-1] if own else None
    hints = recent_hints(history)
    stuck_on = tutor_question(history)

    student_part = _describe(question, 1500, document_excerpt=3000) if question else "(none)"
    if stuck_on:
        question_block = (
            f"The student's latest message:\n{student_part}\n\n"
            "The tutor's latest question, which the student is stuck on and needs a hint to answer:\n"
            f"{_clip(stuck_on.content, 1500)}"
        )
    else:
        question_block = student_part

    convo = [m for m in history if not (m.role == "user" and m.kind and m.kind != "answer")]
    recent = "\n\n".join(f"{_speaker(m)}: {_describe(m)}" for m in convo[-12:]) or "(no earlier messages)"

    previous = "\n".join(f"{i}. {_clip(h.content, 500)}" for i, h in enumerate(hints, 1)) or "None yet."

    # Attempts/answers the student wrote while being helped with this question
    if hints:
        first_idx = list(history).index(hints[0])
        attempts = [m for m in history[first_idx + 1:] if _is_own(m)]
    else:
        attempts = []
    evidence = "\n".join(f"- {_clip(m.content, 500)}" for m in attempts) or "No attempts yet since the hints started."

    return HINT_PLANNER_TEMPLATE.format(
        latest_student_question=question_block,
        recent_conversation_history=recent,
        hints_already_given_for_this_question=previous,
        student_evidence=evidence,
        current_hint_level=current_level,
    )


# ---------- response validation ----------

@dataclass
class HintPlan:
    next_hint: str
    level: int
    total: int
    allow_answer: bool
    assessment: dict = field(default_factory=dict)


class PlanError(ValueError):
    pass


def _parse_json(raw: str) -> dict:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise PlanError("no JSON object")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise PlanError("invalid JSON") from e
    if not isinstance(data, dict):
        raise PlanError("JSON is not an object")
    return data


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_plan(data: dict, suggested: int) -> HintPlan:
    next_hint = data.get("next_hint")
    if not isinstance(next_hint, str) or not next_hint.strip():
        raise PlanError("missing next_hint")

    depth = data.get("question_depth")
    if depth not in DEPTH_RANGES:
        depth = "moderate"
    low, high = DEPTH_RANGES[depth]
    total = min(max(_as_int(data.get("recommended_hint_count"), low), low), high)

    # The model may restart at 1 for a new question, but it may not skip ahead
    level = min(max(_as_int(data.get("current_hint_level"), suggested), 1), suggested)
    total = max(total, level)

    misconceptions = data.get("misconceptions")
    if not isinstance(misconceptions, list):
        misconceptions = []
    assessment = {
        "question_depth": depth,
        "student_level": data.get("student_level") if data.get("student_level") in LEVELS else "uncertain",
        "student_state": data.get("student_state") if data.get("student_state") in STATES else "stuck",
        "misconceptions": [_clip(str(m), 200) for m in misconceptions if str(m).strip()][:5],
        "learning_goal": _clip(str(data.get("learning_goal") or ""), 300),
        "recommended_hint_count": total,
        "current_hint_level": level,
        "hint_purpose": _clip(str(data.get("hint_purpose") or ""), 300),
    }
    allow = data.get("should_allow_answer_button")
    return HintPlan(
        next_hint=next_hint.strip(),
        level=level,
        total=total,
        allow_answer=allow if isinstance(allow, bool) else True,
        assessment=assessment,
    )


# Added to the planner prompt: a hint must *help*, not re-ask the tutor's question.
HINT_QUALITY_RULES = """Additional rules for next_hint:

- The student is stuck on the tutor's latest question shown in <StudentQuestion>. The hint must help them answer THAT question.
- Never restate, rephrase, or repeat the tutor's question or an earlier hint. Every hint must give the student new, concrete information they did not have before.
- First hint: give a concrete clue, such as an everyday example, a relevant observation, or a way to narrow the question down.
- Middle hints: name the relevant concepts, categories, or rules and give one or two concrete examples, then ask the student to connect them.
- Later and final hints: fill in part of the answer or work one step, and leave only the last part for the student.
- Keep next_hint under 90 words, and include at most one question in it."""

REWRITE_FEEDBACK = (
    "Your next_hint mostly repeated the tutor's question or an earlier hint instead of helping. "
    "Rewrite the JSON so next_hint gives new, concrete information for this hint level "
    "(an example, a named concept, or a partial step), as the rules require."
)

_STOPWORDS = set(
    "a an the of to and or in on at by for from with about into as is are was were be been being it its this that "
    "these those there their they them you your we our i me my do does did can could would should might may will "
    "what which who whom how why when where any some think let lets now so if then than just also".split()
)


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOPWORDS}


def is_repetitive(hint: str, references: Sequence[str]) -> bool:
    """True if the hint mostly reuses the words of the tutor's question or an earlier hint."""
    words = _content_words(hint)
    if not words:
        return True
    for ref in references:
        ref_words = _content_words(ref)
        if ref_words and len(words & ref_words) / len(words) >= 0.6:
            return True
    return False


async def plan_next_hint(db: AsyncSession, history: Sequence[Message], suggested: int) -> Optional[HintPlan]:
    """Runs the planner. Returns None on any model/JSON problem so the caller can fall back."""
    model = await llm_service.get_config_value(db, "LLM_MODEL", llm_service.DEFAULT_MODEL)
    messages = [
        {"role": "system", "content": f"{HINT_PLANNER_PROMPT}\n\n{HINT_QUALITY_RULES}"},
        {"role": "user", "content": build_planner_input(history, suggested)},
    ]

    async def ask() -> tuple[str, HintPlan]:
        response = await llm_service.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=800,
        )
        raw = response.choices[0].message.content
        return raw, validate_plan(_parse_json(raw), suggested)

    try:
        raw, plan = await ask()
        stuck_on = tutor_question(history)
        references = ([stuck_on.content] if stuck_on else []) + [h.content for h in recent_hints(history)]
        if is_repetitive(plan.next_hint, references):
            # One retry with feedback; keep the rewrite even if it is still imperfect
            messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": REWRITE_FEEDBACK}]
            try:
                _, plan = await ask()
            except Exception:
                pass  # keep the first plan rather than failing the hint
        return plan
    except Exception:
        return None
