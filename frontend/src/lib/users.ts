import type { Role } from "./auth";
import { DEFAULT_DIAL_CODE } from "./phoneCountries";

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
  role?: Role;
  whatsapp?: string;
}

export interface UserUpdateInput {
  email: string;
  name: string;
  whatsapp?: string;
}

export interface UserCreated extends UserOption {
  initial_password?: string | null;
}

export interface StudentDraft {
  id: string;
  name: string;
  email: string;
  whatsapp: string;
  whatsappDialCode: string;
}

export interface StudentBulkItemInput {
  name: string;
  email: string;
  whatsapp: string;
}

export interface StudentBulkCreate {
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
    whatsappDialCode: DEFAULT_DIAL_CODE,
  };
}
