import type { Role } from "./auth";

export interface UserOption {
  id: string;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
  whatsapp?: string | null;
}

export interface UserCreateInput {
  email: string;
  name: string;
  password: string;
  role?: Role;
  whatsapp?: string;
}

export interface StudentDraft {
  id: string;
  name: string;
  email: string;
  whatsapp: string;
}

export interface StudentBulkItemInput {
  name: string;
  email: string;
  whatsapp: string;
}

export interface StudentBulkCreate {
  password: string;
  students: StudentBulkItemInput[];
}

export interface StudentBulkSkipped {
  email: string;
  reason: string;
}

export interface StudentBulkResult {
  created: UserOption[];
  reused_ids: string[];
  skipped: StudentBulkSkipped[];
}

export function emptyStudentDraft(): StudentDraft {
  return {
    id: crypto.randomUUID(),
    name: "",
    email: "",
    whatsapp: "",
  };
}
