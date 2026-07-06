export function trimmed(value: string): string {
  return value.trim();
}

export function isNonEmpty(value: string): boolean {
  return trimmed(value).length > 0;
}

export function normalizedEmail(value: string): string {
  return trimmed(value).toLowerCase();
}

export function maskPhoneBR(value: string): string {
  const digits = phoneDigits(value).slice(0, 11);
  if (digits.length <= 2) return digits.length ? `(${digits}` : "";
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  if (digits.length <= 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

export function phoneDigits(value: string): string {
  return value.replace(/\D/g, "");
}

export function isValidPhoneBR(value: string): boolean {
  const digits = phoneDigits(value);
  if (digits.length === 10 || digits.length === 11) return true;
  if (digits.length === 12 || digits.length === 13) return digits.startsWith("55");
  return false;
}

export function normalizePhoneForApi(value: string): string | undefined {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  return trimmed;
}

export function normalizeName(value: string): string {
  return trimmed(value).toLocaleLowerCase("pt-BR");
}

export function isDuplicateName(
  value: string,
  siblings: string[],
  current?: string,
): boolean {
  const candidate = normalizeName(value);
  if (!candidate) return false;
  const currentNorm = current ? normalizeName(current) : null;
  return siblings.some((sibling) => {
    const norm = normalizeName(sibling);
    if (!norm) return false;
    if (currentNorm && norm === currentNorm) return false;
    return norm === candidate;
  });
}
