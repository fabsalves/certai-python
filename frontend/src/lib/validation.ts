import {
  DEFAULT_DIAL_CODE,
  DIAL_CODES_BY_LENGTH,
  isKnownDialCode,
} from "./phoneCountries";

export function trimmed(value: string): string {
  return value.trim();
}

export function isNonEmpty(value: string): boolean {
  return trimmed(value).length > 0;
}

export function normalizedEmail(value: string): string {
  return trimmed(value).toLowerCase();
}

export const BR_DDI = DEFAULT_DIAL_CODE;

export function phoneDigits(value: string): string {
  return value.replace(/\D/g, "");
}

export interface PhoneParts {
  dialCode: string;
  national: string;
}

export function detectDialCode(digits: string): string | null {
  if (!digits) return null;
  for (const code of DIAL_CODES_BY_LENGTH) {
    if (!digits.startsWith(code)) continue;
    const national = digits.slice(code.length);
    if (national.length < 6) continue;
    // "+1" só quando o número completo é 1 + 10 dígitos (NANP), não DDD brasileiro.
    if (code === "1" && digits.length !== 11) continue;
    // "+55" só com comprimento de número brasileiro completo.
    if (code === DEFAULT_DIAL_CODE && digits.length !== 12 && digits.length !== 13) continue;
    return code;
  }
  return null;
}

function hasExplicitCountryPrefix(raw: string): boolean {
  return /^\s*\+/.test(raw.trim());
}

export function parsePhoneParts(
  raw: string,
  defaultDialCode: string = DEFAULT_DIAL_CODE,
): PhoneParts {
  const digits = phoneDigits(raw);
  if (!digits) {
    return { dialCode: defaultDialCode || DEFAULT_DIAL_CODE, national: "" };
  }

  const explicitIntl = hasExplicitCountryPrefix(raw);

  // Lista/planilha sem código: DDD + número → Brasil.
  if (!explicitIntl && (digits.length === 10 || digits.length === 11)) {
    return { dialCode: DEFAULT_DIAL_CODE, national: digits };
  }

  if (digits.startsWith(DEFAULT_DIAL_CODE) && (digits.length === 12 || digits.length === 13)) {
    return { dialCode: DEFAULT_DIAL_CODE, national: digits.slice(2) };
  }

  const detected = detectDialCode(digits);
  if (detected) {
    return { dialCode: detected, national: digits.slice(detected.length) };
  }

  return {
    dialCode: defaultDialCode || DEFAULT_DIAL_CODE,
    national: digits,
  };
}

export function nationalPhoneDigits(value: string, dialCode: string = DEFAULT_DIAL_CODE): string {
  const parsed = parsePhoneParts(value, dialCode);
  const maxLen = dialCode === DEFAULT_DIAL_CODE ? 11 : 15;
  return parsed.national.slice(0, maxLen);
}

function maskBrazilNational(digits: string): string {
  if (digits.length <= 2) return digits.length ? `(${digits}` : "";
  if (digits.length <= 7) return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
  if (digits.length <= 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }
  return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
}

function maskNanpNational(digits: string): string {
  const d = digits.slice(0, 10);
  if (d.length <= 3) return d;
  if (d.length <= 6) return `${d.slice(0, 3)} ${d.slice(3)}`;
  return `${d.slice(0, 3)} ${d.slice(3, 6)}-${d.slice(6)}`;
}

export function maskNationalNumber(dialCode: string, value: string): string {
  const digits = nationalPhoneDigits(value, dialCode);
  if (dialCode === DEFAULT_DIAL_CODE) return maskBrazilNational(digits);
  if (dialCode === "1") return maskNanpNational(digits);
  return digits;
}

/** @deprecated Use maskNationalNumber(dialCode, value) */
export function maskPhoneBR(value: string): string {
  return maskNationalNumber(DEFAULT_DIAL_CODE, value);
}

export function nationalPlaceholder(dialCode: string): string {
  if (dialCode === DEFAULT_DIAL_CODE) return "(11) 98765-4321";
  if (dialCode === "1") return "555 123-4567";
  return "Número local";
}

export function isValidWhatsapp(dialCode: string, national: string): boolean {
  const code = isKnownDialCode(dialCode) ? dialCode : DEFAULT_DIAL_CODE;
  const nationalDigits = phoneDigits(national);
  if (!nationalDigits) return false;

  if (code === DEFAULT_DIAL_CODE) {
    return nationalDigits.length === 10 || nationalDigits.length === 11;
  }
  if (code === "1") {
    return nationalDigits.length === 10;
  }

  const full = `${code}${nationalDigits}`;
  return nationalDigits.length >= 6 && full.length >= 10 && full.length <= 15;
}

/** Validates stored full number or national + implicit BR. */
export function isValidPhoneBR(value: string): boolean {
  const digits = phoneDigits(value);
  if (digits.length === 10 || digits.length === 11) {
    return isValidWhatsapp(DEFAULT_DIAL_CODE, digits);
  }
  const parsed = parsePhoneParts(digits);
  return isValidWhatsapp(parsed.dialCode, parsed.national);
}

export function normalizePhoneForApi(
  dialCode: string,
  national: string,
): string | undefined {
  const code = isKnownDialCode(dialCode) ? dialCode : DEFAULT_DIAL_CODE;
  const nationalDigits = phoneDigits(national);
  if (!isValidWhatsapp(code, nationalDigits)) return undefined;
  return `${code}${nationalDigits}`;
}

export function formatWhatsappDisplay(value: string): string {
  const parsed = parsePhoneParts(value);
  if (!parsed.national) return "";
  const masked = maskNationalNumber(parsed.dialCode, parsed.national);
  return `+${parsed.dialCode} ${masked}`;
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
