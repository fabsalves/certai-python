import type { Role } from "./auth";

export interface UserOption {
  id: string;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
}

export interface UserCreateInput {
  email: string;
  name: string;
  password: string;
  role?: Role;
}
