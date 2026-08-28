export const MIN_PASSWORD_LENGTH = 10;
export const MAX_PASSWORD_LENGTH = 128;

export const PASSWORD_RULES_HINT =
  "Mínimo 10 caracteres, com letra maiúscula, minúscula e número.";

export function validateNewPassword(password: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH || password.length > MAX_PASSWORD_LENGTH) {
    return PASSWORD_RULES_HINT;
  }
  if (!/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
    return PASSWORD_RULES_HINT;
  }
  return null;
}
