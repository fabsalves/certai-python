import { api } from "./api";

export interface PlaygroundMessage {
  author: "student" | "agent" | "professor";
  content: string;
  created_at: string;
}

export interface PlaygroundAgentResponse {
  conversation_id: string;
  response: string;
}

export async function fetchStudentMessages(
  cohortId: string,
  studentId: string,
  lessonId: string,
): Promise<PlaygroundMessage[]> {
  const { data } = await api.get<PlaygroundMessage[]>(
    `/admin/playground/cohorts/${cohortId}/students/${studentId}/lessons/${lessonId}/messages`,
  );
  return data;
}

export async function sendStudentMessage(
  cohortId: string,
  studentId: string,
  lessonId: string,
  content: string,
): Promise<PlaygroundAgentResponse> {
  const { data } = await api.post<PlaygroundAgentResponse>(
    `/admin/playground/cohorts/${cohortId}/students/${studentId}/lessons/${lessonId}/messages`,
    { content },
  );
  return data;
}

export function playgroundTranscribePath(cohortId: string, professorId: string): string {
  return `/admin/playground/cohorts/${cohortId}/professors/${professorId}/transcribe-report`;
}

export function playgroundCompletePath(cohortId: string, professorId: string): string {
  return `/admin/playground/cohorts/${cohortId}/professors/${professorId}/complete-lesson`;
}

export interface PlaygroundTrackMaterialContext {
  filename: string | null;
  ingestion_status: string | null;
  guide: string;
  in_ai_bundle: boolean;
}

export interface PlaygroundLessonNoteContext {
  lesson_id: string;
  lesson_title: string;
  ingestion_status: string | null;
  summary: string;
  unclear_points: string;
  knowledge_base: string;
  has_attachment: boolean;
  attachment_filename: string | null;
  in_ai_bundle: boolean;
}

export interface PlaygroundContext {
  scope: string;
  current_position: { module: string; lesson: string } | null;
  track_map: Array<Record<string, unknown>>;
  unlocked_content: Array<{ lesson: string; content: string }>;
  cohort_notes_in_bundle: Array<{
    summary: string;
    unclear_points: string;
    knowledge_base: string;
  }>;
  track_guide_in_bundle: string;
  system_blocks: string;
  track_material: PlaygroundTrackMaterialContext;
  lesson_notes: PlaygroundLessonNoteContext[];
}

export async function fetchPlaygroundContext(
  cohortId: string,
  lessonId: string,
): Promise<PlaygroundContext> {
  const { data } = await api.get<PlaygroundContext>(
    `/admin/playground/cohorts/${cohortId}/lessons/${lessonId}/context`,
  );
  return data;
}
