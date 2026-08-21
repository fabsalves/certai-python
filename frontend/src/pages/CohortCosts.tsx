import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
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
  fetchCohortCostDetail,
  formatMinutes,
  formatPeriod,
  formatUsd,
  NO_DATA,
  PERIOD_SEGMENT_OPTIONS,
  periodDaysFromKey,
  periodKeyFromSearch,
  type CohortCostDetail,
  type PeriodKey,
  type StudentCost,
} from "../lib/costs";
import { matchesAnySearch } from "../lib/listSearch";
import { useListView } from "../lib/useListView";
import { usePagination } from "../lib/usePagination";

export function CohortCosts() {
  const { cohortId = "" } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useListView("costs-cohort");
  const [search, setSearch] = useState("");
  const period = periodKeyFromSearch(searchParams.get("period"));
  const model = searchParams.get("model") ?? "";
  const [data, setData] = useState<CohortCostDetail | null>(null);
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
    if (!cohortId) return;
    setLoading(true);
    fetchCohortCostDetail(cohortId, periodDaysFromKey(period), model)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [cohortId, period, model]);

  useEffect(() => {
    load();
  }, [load]);

  const students = data?.students ?? [];
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
      students.filter((student) => matchesAnySearch(search, [student.student_name])),
    [students, search],
  );

  const paging = usePagination(filtered, {
    resetKey: `${search}|${period}|${model}`,
  });

  const qs = costsSearchParams(period, model);

  const columns = useMemo<DataColumn<StudentCost>[]>(
    () => [
      {
        id: "student",
        header: "Aluno",
        primary: true,
        render: (student) => (
          <span className="table__primary">{student.student_name}</span>
        ),
      },
      {
        id: "lessons",
        header: "Aulas",
        align: "end",
        render: (student) => student.lesson_count || NO_DATA,
      },
      {
        id: "voice",
        header: "Voz (est.)",
        align: "end",
        render: (student) => formatMinutes(student.voice_minutes_est),
      },
      {
        id: "perLesson",
        header: "Por aula",
        align: "end",
        render: (student) => formatUsd(student.cost_per_lesson_usd),
      },
      {
        id: "total",
        header: "Total",
        align: "end",
        render: (student) => formatUsd(student.cost_usd),
      },
      {
        id: "actions",
        header: "",
        card: "actions",
        align: "end",
        render: (student) =>
          student.student_id ? (
            <div className="table__actions">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() =>
                  navigate(`/costs/${cohortId}/alunos/${student.student_id}${qs}`)
                }
              >
                Detalhar
              </button>
            </div>
          ) : null,
      },
    ],
    [cohortId, navigate, qs],
  );

  if (loading && !data) {
    return (
      <CostsListSkeleton
        title="Custos da turma"
        description="Consumo de IA por aluno."
        columns={5}
      />
    );
  }

  if (!data) {
    return (
      <>
        <PageHeader eyebrow="Custos" title="Turma não encontrada" />
        <div className="card empty-state">
          <p>Não foi possível carregar os custos desta turma.</p>
          <Link to={`/costs${qs}`} className="btn btn-ghost" style={{ marginTop: 20 }}>
            Voltar para Custos
          </Link>
        </div>
      </>
    );
  }

  const hasResults = filtered.length > 0;
  const showModelFilter = modelOptions.length > 1;

  return (
    <>
      <PageHeader
        eyebrow={data.track_title || "Custos"}
        title={data.cohort_title}
        description="Consumo de IA por aluno desta turma."
        actions={students.length > 0 ? <ViewToggle value={view} onChange={setView} /> : undefined}
      />

      <ListToolbar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Buscar por aluno"
        searchLabel="Buscar alunos"
      >
        <FilterSegment
          value={period}
          options={PERIOD_SEGMENT_OPTIONS}
          onChange={setPeriod}
          aria-label="Filtrar por período"
        />
        {showModelFilter && (
          <Select
            id="cohort-costs-model"
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
            label: "Total da turma",
            value: formatUsd(data.cost_usd),
            hint: formatPeriod(data.period_from, data.period_to),
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

      {students.length === 0 && (
        <div className="card empty-state">
          <p>Nenhum consumo medido nesta turma no período.</p>
        </div>
      )}

      {students.length > 0 && (
        <>
          {!hasResults && <ListEmptyFilter />}

          {hasResults && (
            <>
              <DataTable
                columns={columns}
                rows={paging.items}
                rowKey={(student) => student.student_id ?? "cohort-level"}
                layout={view}
                aria-label="Custos por aluno"
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
