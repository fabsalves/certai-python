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
