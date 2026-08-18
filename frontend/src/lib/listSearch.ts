export function normalizeSearch(text: string): string {
  return text.trim().toLocaleLowerCase("pt-BR");
}

export function matchesSearch(haystack: string, query: string): boolean {
  const normalized = normalizeSearch(query);
  if (!normalized) return true;
  return normalizeSearch(haystack).includes(normalized);
}

export function matchesAnySearch(query: string, values: Array<string | null | undefined>): boolean {
  const normalized = normalizeSearch(query);
  if (!normalized) return true;
  return values.some((value) => value && normalizeSearch(value).includes(normalized));
}
