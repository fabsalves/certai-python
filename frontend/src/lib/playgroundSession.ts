const STORAGE_KEY = "certai.playground.session";

export type PlaygroundSessionMode = "student" | "professor";
export type PlaygroundRailTab = "track" | "context" | "scores";

export interface PlaygroundSessionSnapshot {
  cohortId: string;
  mode: PlaygroundSessionMode;
  studentId: string;
  professorId: string;
  selectedLessonId: string | null;
  railTab: PlaygroundRailTab;
}

export function readPlaygroundSession(): Partial<PlaygroundSessionSnapshot> | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Partial<PlaygroundSessionSnapshot>;
  } catch {
    return null;
  }
}

export function writePlaygroundSession(snapshot: PlaygroundSessionSnapshot): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // private mode / quota — ignore
  }
}
