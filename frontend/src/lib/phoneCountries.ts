export interface PhoneCountry {
  dialCode: string;
  name: string;
}

/** Same set as cert-ai — main markets for CertAI cohorts. */
const PHONE_COUNTRIES: PhoneCountry[] = [
  { dialCode: "55", name: "Brasil" },
  { dialCode: "351", name: "Portugal" },
  { dialCode: "598", name: "Uruguai" },
  { dialCode: "595", name: "Paraguai" },
  { dialCode: "54", name: "Argentina" },
  { dialCode: "56", name: "Chile" },
  { dialCode: "57", name: "Colômbia" },
  { dialCode: "52", name: "México" },
  { dialCode: "49", name: "Alemanha" },
  { dialCode: "44", name: "Reino Unido" },
  { dialCode: "34", name: "Espanha" },
  { dialCode: "33", name: "França" },
  { dialCode: "39", name: "Itália" },
  { dialCode: "1", name: "EUA/Canadá" },
];

export const DEFAULT_DIAL_CODE = "55";

/** Brazil first, then alphabetical. */
export const PHONE_COUNTRY_OPTIONS: PhoneCountry[] = [
  PHONE_COUNTRIES[0],
  ...PHONE_COUNTRIES.slice(1).sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
];

/** Longest codes first — for parsing pasted international numbers. */
export const DIAL_CODES_BY_LENGTH = [...PHONE_COUNTRIES]
  .map((c) => c.dialCode)
  .sort((a, b) => b.length - a.length);

export function phoneCountryByDialCode(dialCode: string): PhoneCountry | undefined {
  return PHONE_COUNTRIES.find((c) => c.dialCode === dialCode);
}

export function isKnownDialCode(dialCode: string): boolean {
  return PHONE_COUNTRIES.some((c) => c.dialCode === dialCode);
}
