/**
 * Focused validation for multiple attachments and the password toggle (Node 22.6+ runs TS directly):
 *   npm run check:attachments
 */
import assert from 'node:assert/strict';
import {
  checkNewFiles, classifyFile, MAX_ATTACHMENTS, MAX_DOCUMENT_BYTES, MAX_IMAGE_BYTES, MAX_TOTAL_ATTACHMENT_BYTES,
} from '../src/services/attachmentRules.ts';
import { passwordToggleState } from '../src/services/passwordToggle.ts';
import { applySavedUser, completeStream, startStream, streamingId } from '../src/services/chatStream.ts';
import type { Message } from '../src/types/api';

let passed = 0;
const check = (name: string, fn: () => void) => {
  fn();
  passed++;
  console.log(`  ok  ${name}`);
};

const file = (name: string, size: number, type = '') => ({ name, size, type });
const MB = 1024 * 1024;

// ---------- attachment rules ----------

check('classifies images by type and documents by extension', () => {
  assert.equal(classifyFile(file('a.png', 10, 'image/png')), 'image');
  assert.equal(classifyFile(file('notes.PDF', 10, 'application/pdf')), 'document');
  assert.equal(classifyFile(file('essay.docx', 10)), 'document');
  assert.equal(classifyFile(file('x.gif', 10, 'image/gif')), null);
  assert.equal(classifyFile(file('run.exe', 10)), null);
});

check('accepts a mix of images and documents in order', () => {
  const incoming = [file('a.png', MB, 'image/png'), file('n.txt', 100, 'text/plain'), file('w.pdf', 2 * MB, 'application/pdf')];
  const { accepted, errors } = checkNewFiles([], incoming);
  assert.deepEqual(accepted.map(f => f.name), ['a.png', 'n.txt', 'w.pdf']);
  assert.deepEqual(errors, []);
});

check('rejects unsupported, empty and oversized files without blocking the rest', () => {
  const { accepted, errors } = checkNewFiles([], [
    file('virus.exe', 10),
    file('empty.txt', 0, 'text/plain'),
    file('huge.png', MAX_IMAGE_BYTES + 1, 'image/png'),
    file('huge.pdf', MAX_DOCUMENT_BYTES + 1, 'application/pdf'),
    file('fine.png', 100, 'image/png'),
  ]);
  assert.deepEqual(accepted.map(f => f.name), ['fine.png']);
  assert.equal(errors.length, 4);
  assert.match(errors[0], /"virus.exe": unsupported file type/);
  assert.match(errors[1], /"empty.txt" is empty/);
  assert.match(errors[2], /max 5 MB for images/);
  assert.match(errors[3], /max 10 MB for documents/);
});

check(`enforces the ${MAX_ATTACHMENTS}-file limit across picks (one clear message)`, () => {
  const current = [file('1.txt', 1), file('2.txt', 1), file('3.txt', 1), file('4.txt', 1)];
  const { accepted, errors } = checkNewFiles(current, [file('5.txt', 1), file('6.txt', 1), file('7.txt', 1)]);
  assert.deepEqual(accepted.map(f => f.name), ['5.txt']);
  assert.deepEqual(errors, [`You can attach up to ${MAX_ATTACHMENTS} files per message.`]);
});

check('enforces the total size limit', () => {
  const current = [file('big1.pdf', 9 * MB, 'application/pdf'), file('big2.pdf', 9 * MB, 'application/pdf')];
  const { accepted, errors } = checkNewFiles(current, [file('more.pdf', 3 * MB, 'application/pdf'), file('tiny.txt', 10)]);
  assert.deepEqual(accepted.map(f => f.name), ['tiny.txt']);
  assert.match(errors[0], new RegExp(`larger than ${MAX_TOTAL_ATTACHMENT_BYTES / MB} MB in total`));
});

// ---------- previews survive the server swap (no flicker, no refetch while sending) ----------

check('local attachment previews are kept when the saved message replaces the optimistic one', () => {
  const local = [{ name: 'a.png', size: 5, mime: 'image/png', kind: 'image' as const, previewUrl: 'blob:1' }];
  const userTemp: Message = { id: 'local-1', session_id: 's', role: 'user', content: 'hi', timestamp: '', local_attachments: local };
  const tempA = streamingId(userTemp.id);
  const saved: Message = { id: 'u', session_id: 's', role: 'user', content: 'hi', timestamp: '',
    attachments: [{ id: 'att1', position: 0, kind: 'image', name: 'a.png', mime_type: 'image/png', size_bytes: 5 }] };
  let state = applySavedUser(startStream([], userTemp, tempA, null), userTemp.id, tempA, saved);
  assert.equal(state[0].attachments?.[0].id, 'att1');
  assert.equal(state[0].local_attachments?.[0].previewUrl, 'blob:1');
  state = completeStream(state, 'u', tempA, { user_message: saved, assistant_message: { ...saved, id: 'a', role: 'assistant' } });
  assert.equal(state.filter(m => m.role === 'assistant').length, 1);
});

// ---------- password toggle ----------

check('password toggle switches type, label and pressed state', () => {
  assert.deepEqual(passwordToggleState(false), { inputType: 'password', label: 'Show password', pressed: false });
  assert.deepEqual(passwordToggleState(true), { inputType: 'text', label: 'Hide password', pressed: true });
});

console.log(`\n${passed} attachment/password checks passed`);
