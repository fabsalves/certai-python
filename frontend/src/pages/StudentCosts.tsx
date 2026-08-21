import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/layout/PageHeader";
import { CostStats, UnpricedWarning } from "../components/costs/CostStats";
import { CostsListSkeleton } from "../components/costs/CostsListSkeleton";
import { KindBreakdown } from "../components/costs/KindBreakdown";
import { DataTable, type DataColumn } from "../components/ui/DataTable";
import {
  FilterSegment,
  ListEmptyFilter,
  ListToolbar,
} from "../components/ui/ListToolbar";
import { Pagination } from "../components/ui/Pagination";
import { Select } from "../components/ui/Select";
import { ViewToggle } from "../components/ui/ViewToggle";
import {
  costsSearchParams,
  fetchStudentCostDetail,
  formatMinutes,
  formatPeriod,
  formatUsd,
  NO_DATA,
  PERIOD_SEGMENT_OPTIONS,
  periodDaysFromKey,
  periodKeyFromSearch,
  type LessonCost,
  type PeriodKey,
  type StudentCostDetail,
} from "../lib/costs";
import { matchesAnySearch } from "../lib/listSearch";
import { useListView } from "../lib/useListView";
import { usePagination } from "../lib/usePagination";

type Scope = "all" | "measured";

const SCOPE_OPTIONS: Array<{ value: Scope; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "measured", label: "Só com medição" },
];

export function StudentCosts() {
  const { cohortId = "", studentId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useListView("costs-student");
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState<Scope>("all");
  const period = periodKeyFromSearch(searchParams.get("period"));
  const model = searchParams.get("model") ?? "";
  const [data, setData] = useState<StudentCostDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const setPeriod = (next: PeriodKey) => {
    const params = new URLSearchParams(searchParams);
    if (next === "30") params.delete("period");
    else params.set("period", next);
    setSearchParams(params, { replace: true });
  };

  const setModel = (next: string) => {
    const params = new URLSearchParams(searchParams);
    if (!next) params.delete("model");
    else params.set("model", next);
    setSearchParams(params, { replace: true });
  };

  const load = useCallback(() => {
    if (!cohortId || !studentId) return;
    setLoading(true);
    fetchStudentCostDetail(cohortId, studentId, periodDaysFromKey(period), model)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [cohortId, studentId, period, model]);

  useEffect(() => {
    load();
  }, [load]);

  const lessons = data?.lessons ?? [];
  const models = data?.models ?? [];

  const modelOptions = useMemo(
    () => [
      { value: "", label: "Todos os modelos" },
      ...models.map((name) => ({ value: name, label: name })),
    ],
    [models],
  );

  const filtered = useMemo(
    () =>
      lessons.filter(
        (lesson) =>
          matchesAnySearch(search, [lesson.lesson_title, lesson.module_title]) &&
          (scope === "all" || lesson.cost_usd > 0),
      ),
    [lessons, search, scope],
  );

  const paging = usePagination(filtered, {
    resetKey: `${search}|${scope}|${period}|${model}`,
  });

  const qs = costsSearchParams(period, model);

  const columns = useMemo<DataColumn<LessonCost>[]>(
    () => [
      {
        id: "lesson",
        header: "Aula",
        primary: true,
        render: (lesson) => (
          <span className="table__primary">{lesson.lesson_title}</span>
        ),
      },
      {
        id: "module",
        header: "Módulo",
        render: (lesson) => lesson.module_title || NO_DATA,
      },
      {
        id: "voice",
        header: "Voz (est.)",
        align: "end",
        render: (lesson) => formatMinutes(lesson.voice_minutes_est),
      },
      {
        id: "voiceCost",
        header: "Voz",
        align: "end",
        render: (lesson) => formatUsd(lesson.voice_cost_usd),
      },
      {
        id: "otherCost",
        header: "Outros",
        align: "end",
        render: (lesson) => formatUsd(lesson.other_cost_usd),
      },
      {
        id: "total",
        header: "Total",
        align: "end",
        render: (lesson) => formatUsd(lesson.cost_usd),
      },
    ],
    [],
  );

  if (loading && !data) {
    return (
      <CostsListSkeleton
        title="Custos do aluno"
        description="Consumo de IA aula por aula."
        columns={6}
      />
    );
  }

  if (!data) {
    return (
      <>
        <PageHeader eyebrow="Custos" title="Aluno não encontrado" />
        <div className="card empty-state">
          <p>Não foi possível carregar os custos deste aluno.</p>
          <Link
            to={`/costs/${cohortId}${qs}`}
            className="btn btn-ghost"
            style={{ marginTop: 20 }}
          >
            Voltar para a turma
          </Link>
        </div>
      </>
    );
  }

  const hasResults = filtered.length > 0;
  const showModelFilter = modelOptions.length > 1;
  const measuredLessons = lessons.filter((lesson) => lesson.cost_usd > 0).length;
  const perLesson = measuredLessons > 0 ? data.cost_usd / measuredLessons : 0;

  return (
    <>
      <PageHeader
        eyebrow={data.cohort_title}
        title={data.student_name}
        description="Consumo de IA deste aluno, aula por aula."
        actions={lessons.length > 0 ? <ViewToggle value={view} onChange={setView} /> : undefined}
      />

      <ListToolbar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Buscar por aula ou módulo"
        searchLabel="Buscar aulas"
      >
        <FilterSegment
          value={period}
          options={PERIOD_SEGMENT_OPTIONS}
          onChange={setPeriod}
          aria-label="Filtrar por período"
        />
        <FilterSegment
          value={scope}
          options={SCOPE_OPTIONS}
          onChange={setScope}
          aria-label="Filtrar aulas por medição"
        />
        {showModelFilter && (
          <Select
            id="student-costs-model"
            className="list-toolbar__ui-select"
            value={model}
            onChange={setModel}
            options={modelOptions}
            aria-label="Filtrar por modelo"
          />
        )}
      </ListToolbar>

      <CostStats
        stats={[
          {
            label: "Total do aluno",
            value: formatUsd(data.cost_usd),
            hint: formatPeriod(data.period_from, data.period_to),
          },
          {
            label: "Por aula medida",
            value: formatUsd(perLesson),
            hint: `${measuredLessons} de ${lessons.length} aulas com medição`,
          },
          {
            label: "Voz (estimada)",
            value: formatMinutes(data.voice_minutes_est),
            hint: "Derivada dos tokens de áudio, não do relógio",
          },
        ]}
      />

      <UnpricedWarning count={data.unpriced_events} />

      <KindBreakdown rows={data.by_kind} />

      {lessons.length === 0 && (
        <div className="card empty-state">
          <p>Nenhum consumo medido para este aluno no período.</p>
        </div>
      )}

      {lessons.length > 0 && (
        <>
          {!hasResults && <ListEmptyFilter />}

          {hasResults && (
            <>
              <DataTable
                columns={columns}
                rows={paging.items}
                rowKey={(lesson) => lesson.lesson_id ?? "no-lesson"}
                layout={view}
                aria-label="Custos por aula"
              />
              <Pagination
                page={paging.page}
                totalPages={paging.totalPages}
                total={paging.total}
                from={paging.from}
                to={paging.to}
                onPageChange={paging.setPage}
              />
            </>
          )}
        </>
      )}
    </>
  );
}
