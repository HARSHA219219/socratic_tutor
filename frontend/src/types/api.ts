export interface Student {
  id: string;
  name: string;
  roll_no: string;
  username: string;
  created_at: string;
}

export interface StudentAuthResponse {
  access_token: string;
  token_type: string;
  student: Student;
  /** Only present right after signup / password reset. Shown once. */
  recovery_code?: string | null;
}

export interface Session {
  id: string;
  student_id: string;
  title?: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface Message {
  id: string;
  session_id: string;
  /** 'system' = checkpoint context at the start of a continued chat */
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  image_mime_type?: string | null;
  image_size_bytes?: number | null;
  /** null = normal turn; "hint-1".."hint-3" = hint ladder; "answer" = direct answer */
  kind?: string | null;
  document_name?: string | null;
  document_mime_type?: string | null;
  document_size_bytes?: number | null;
  /** "ok" | "truncated" (text shortened) | "image" (PDF without text, pages sent as images) */
  document_text_status?: string | null;
  /** Hint ladder: total hints planned for this question; whether "Show answer" is offered */
  hint_total?: number | null;
  hint_allow_answer?: boolean | null;
  /** Admin only: the hint planner's assessment */
  hint_assessment?: HintAssessment | null;
  /** Client-only info for a document that is still uploading */
  local_document?: { name: string; size: number; mime: string };
  /** Every file on the message (image_* / document_* above describe only the first of each) */
  attachments?: Attachment[];
  /** Client-only: files of a message that is still being sent (previews) */
  local_attachments?: LocalAttachment[];
  /** Client-only: tutor reply that is still streaming in */
  streaming?: boolean;
  /** Client-only preview for an image that is still uploading */
  local_image_url?: string;
}

export interface HintAssessment {
  question_depth: string;
  student_level: string;
  student_state: string;
  misconceptions: string[];
  learning_goal: string;
  recommended_hint_count: number;
  current_hint_level: number;
  hint_purpose: string;
}

export interface CheckpointSummary {
  topic: string;
  learning_objective: string;
  student_knowledge: string[];
  student_attempts: string[];
  correct_understanding: string[];
  misconceptions: string[];
  hints_given: string[];
  answers_revealed: string[];
  attachments: string[];
  unresolved_questions: string[];
  next_tutoring_action: string;
  continuation_notes: string;
}

export interface Checkpoint {
  id: string;
  session_id: string;
  /** Last message included in the summary */
  message_id: string;
  source: 'manual' | 'automatic';
  summary_token_count?: number | null;
  created_at?: string | null;
  summary: CheckpointSummary;
}

export interface Attachment {
  id: string;
  position: number;
  kind: 'image' | 'document';
  name?: string | null;
  mime_type: string;
  size_bytes: number;
  /** Documents: "ok" | "truncated" | "image" */
  text_status?: string | null;
  /** Images: description the tutor reuses in later turns */
  image_summary?: string | null;
  /** null = pending, "ok", "failed" */
  summary_status?: string | null;
}

export interface LocalAttachment {
  name: string;
  size: number;
  mime: string;
  kind: 'image' | 'document';
  previewUrl?: string;
}

/** Server-Sent Events from the streaming chat endpoints */
export type StreamEvent =
  | { type: 'start'; session_id: string; user_message: Message | null }
  | { type: 'user_message'; user_message: Message }
  | { type: 'chunk'; text: string }
  | { type: 'complete'; message_id: string; session_title?: string | null; user_message: Message; assistant_message: Message }
  | { type: 'error'; message: string };

export interface ChatResponse {
  session_id: string;
  response: string;
  session_title?: string | null;
  user_message?: Message | null;
  assistant_message?: Message | null;
}
