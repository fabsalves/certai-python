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
