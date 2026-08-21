import { api } from "./api";

/**
 * Consumo de IA medido, em USD. BRL é conversão de exibição.
 *
 * `unpriced_events > 0` significa que há chamadas de um modelo sem tarifa
 * conhecida: o total exibido está INCOMPLETO e a tela precisa avisar.
 * Valor não medido nunca é renderizado como zero — ver `formatUsd`.
 */

export interface KindBreakdown {
  cost_kind: string;
  label: string;
  provider: string;
  total_tokens: number;
  cost_usd: number;
  unpriced_events: number;
}

export interface LessonCost {
  lesson_id: string | null;
  lesson_title: string;
  module_title: string;
  voice_minutes_est: number;
  voice_cost_usd: number;
  other_cost_usd: number;
  cost_usd: number;
  unpriced_events: number;
}

export interface StudentCost {
  student_id: string | null;
  student_name: string;
  lesson_count: number;
  voice_minutes_est: number;
  cost_usd: number;
  cost_per_lesson_usd: number;
  unpriced_events: number;
}

export interface CohortCost {
  cohort_id: string;
  cohort_title: string;
  track_id: string | null;
  track_title: string;
  student_count: number;
  lesson_count: number;
  student_lesson_count: number;
  voice_minutes_est: number;
  cost_usd: number;
  cost_per_student_usd: number;
  cost_per_student_lesson_usd: number;
  unpriced_events: number;
}

interface PeriodMeta {
  usd_brl_rate: number;
  period_from: string;
  period_to: string;
  models: string[];
}

export interface CohortsCost extends PeriodMeta {
  cohorts: CohortCost[];
  total_cost_usd: number;
  unattributed_cost_usd: number;
  unpriced_events: number;
}

export interface CohortCostDetail extends PeriodMeta {
  cohort_id: string;
  cohort_title: string;
  track_title: string;
  voice_minutes_est: number;
  cost_usd: number;
  unpriced_events: number;
  by_kind: KindBreakdown[];
  students: StudentCost[];
}

export interface StudentCostDetail extends PeriodMeta {
  cohort_id: string;
  cohort_title: string;
  student_id: string;
  student_name: string;
  voice_minutes_est: number;
  cost_usd: number;
  unpriced_events: number;
  by_kind: KindBreakdown[];
  lessons: LessonCost[];
}

/** Janelas de período. `null` = tudo. */
export type PeriodDays = 30 | 90 | null;

export type PeriodKey = "30" | "90" | "all";

export const PERIOD_SEGMENT_OPTIONS: Array<{ value: PeriodKey; label: string }> = [
  { value: "30", label: "30 dias" },
  { value: "90", label: "90 dias" },
  { value: "all", label: "Tudo" },
];

export function periodDaysFromKey(key: PeriodKey): PeriodDays {
  if (key === "90") return 90;
  if (key === "all") return null;
  return 30;
}

export function periodKeyFromSearch(value: string | null): PeriodKey {
  if (value === "90" || value === "all") return value;
  return "30";
}

function costQueryParams(days: PeriodDays, model: string): Record<string, string> {
  const params: Record<string, string> = {};
  if (days === null) {
    params.from = "2020-01-01T00:00:00Z";
  } else {
    params.from = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
  }
  if (model.trim()) params.model = model.trim();
  return params;
}

export function costsSearchParams(period: PeriodKey, model: string): string {
  const params = new URLSearchParams();
  if (period !== "30") params.set("period", period);
  if (model.trim()) params.set("model", model.trim());
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchCohortCosts(
  days: PeriodDays,
  model = "",
): Promise<CohortsCost> {
  const { data } = await api.get<CohortsCost>("/costs/cohorts", {
    params: costQueryParams(days, model),
  });
  return data;
}

export async function fetchCohortCostDetail(
  cohortId: string,
  days: PeriodDays,
  model = "",
): Promise<CohortCostDetail> {
  const { data } = await api.get<CohortCostDetail>(`/costs/cohorts/${cohortId}`, {
    params: costQueryParams(days, model),
  });
  return data;
}

export async function fetchStudentCostDetail(
  cohortId: string,
  studentId: string,
  days: PeriodDays,
  model = "",
): Promise<StudentCostDetail> {
  const { data } = await api.get<StudentCostDetail>(
    `/costs/cohorts/${cohortId}/students/${studentId}`,
    { params: costQueryParams(days, model) },
  );
  return data;
}

// --- Formatação --------------------------------------------------------------
// Único lugar com Intl. Nenhuma tela formata por conta própria.

const usd = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const tokens = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

/** Placeholder de "não medido". Zero é uma afirmação; isto é a verdade. */
export const NO_DATA = "-";

/** Valor não medido vira "-", nunca US$ 0,00. Abaixo de um centavo: "< US$ 0,01". */
export function formatUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return NO_DATA;
  if (value === 0) return NO_DATA;
  if (value < 0.01) return "< US$ 0,01";
  return usd.format(value);
}

export function formatBrl(
  valueUsd: number | null | undefined,
  rate: number,
): string {
  if (valueUsd === null || valueUsd === undefined || valueUsd === 0) return NO_DATA;
  const converted = valueUsd * rate;
  if (converted < 0.01) return "< R$ 0,01";
  return brl.format(converted);
}

export function formatTokens(value: number | null | undefined): string {
  if (!value) return NO_DATA;
  return tokens.format(Math.round(value));
}

/** Minutos de voz derivados de tokens de áudio (estimativa, não relógio). */
export function formatMinutes(value: number | null | undefined): string {
  if (!value) return NO_DATA;
  if (value < 1) return "< 1 min";
  return `${tokens.format(Math.round(value))} min`;
}

export function formatPeriod(from: string, to: string): string {
  const fmt = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" });
  return `${fmt.format(new Date(from))} a ${fmt.format(new Date(to))}`;
}
