export function trimmed(value: string): string {
  return value.trim();
}

export function isNonEmpty(value: string): boolean {
  return trimmed(value).length > 0;
}

export function normalizedEmail(value: string): string {
  return trimmed(value).toLowerCase();
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
