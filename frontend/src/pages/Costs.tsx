import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/layout/PageHeader";
import { CostStats, UnpricedWarning } from "../components/costs/CostStats";
import { CostsListSkeleton } from "../components/costs/CostsListSkeleton";
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
  fetchCohortCosts,
  formatMinutes,
  formatPeriod,
  formatUsd,
  NO_DATA,
  PERIOD_SEGMENT_OPTIONS,
  periodDaysFromKey,
  periodKeyFromSearch,
  type CohortCost,
  type CohortsCost,
  type PeriodKey,
} from "../lib/costs";
import { matchesAnySearch } from "../lib/listSearch";
import { useListView } from "../lib/useListView";
import { usePagination } from "../lib/usePagination";

export function Costs() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [view, setView] = useListView("costs");
  const [search, setSearch] = useState("");
  const [track, setTrack] = useState("");
  const period = periodKeyFromSearch(searchParams.get("period"));
  const model = searchParams.get("model") ?? "";
  const [data, setData] = useState<CohortsCost | null>(null);
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
    setLoading(true);
    fetchCohortCosts(periodDaysFromKey(period), model)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [period, model]);

  useEffect(() => {
    load();
  }, [load]);

  const cohorts = data?.cohorts ?? [];
  const models = data?.models ?? [];

  const trackOptions = useMemo(() => {
    const titles = [...new Set(cohorts.map((c) => c.track_title).filter(Boolean))];
    titles.sort((a, b) => a.localeCompare(b, "pt-BR"));
    return [
      { value: "", label: "Todas as trilhas" },
      ...titles.map((title) => ({ value: title, label: title })),
    ];
  }, [cohorts]);

  const modelOptions = useMemo(
    () => [
      { value: "", label: "Todos os modelos" },
      ...models.map((name) => ({ value: name, label: name })),
    ],
    [models],
  );

  const filtered = useMemo(
    () =>
      cohorts.filter(
        (cohort) =>
          matchesAnySearch(search, [cohort.cohort_title, cohort.track_title]) &&
          (!track || cohort.track_title === track),
      ),
    [cohorts, search, track],
  );

  const paging = usePagination(filtered, { resetKey: `${search}|${track}|${period}|${model}` });

  const columns = useMemo<DataColumn<CohortCost>[]>(
    () => [
      {
        id: "cohort",
        header: "Turma",
        primary: true,
        render: (cohort) => (
          <span className="table__primary">{cohort.cohort_title}</span>
        ),
      },
      {
        id: "track",
        header: "Trilha",
        render: (cohort) => cohort.track_title || NO_DATA,
      },
      {
        id: "students",
        header: "Alunos",
        align: "end",
        render: (cohort) => cohort.student_count || NO_DATA,
      },
      {
        id: "voice",
        header: "Voz (est.)",
        align: "end",
        render: (cohort) => formatMinutes(cohort.voice_minutes_est),
      },
      {
        id: "perStudentLesson",
        header: "Por aluno-aula",
        align: "end",
        render: (cohort) => formatUsd(cohort.cost_per_student_lesson_usd),
      },
      {
        id: "perStudent",
        header: "Por aluno",
        align: "end",
        render: (cohort) => formatUsd(cohort.cost_per_student_usd),
      },
      {
        id: "total",
        header: "Total",
        align: "end",
        render: (cohort) => formatUsd(cohort.cost_usd),
      },
      {
        id: "actions",
        header: "",
        card: "actions",
        align: "end",
        render: (cohort) => (
          <div className="table__actions">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() =>
                navigate(`/costs/${cohort.cohort_id}${costsSearchParams(period, model)}`)
              }
            >
              Detalhar
            </button>
          </div>
        ),
      },
    ],
    [navigate, period, model],
  );

  if (loading && !data) {
    return <CostsListSkeleton columns={7} />;
  }

  const hasUnattributed = (data?.unattributed_cost_usd ?? 0) > 0;
  const hasAnyMeasurement =
    cohorts.length > 0 || hasUnattributed || (data?.unpriced_events ?? 0) > 0;
  const hasResults = filtered.length > 0;
  const showTrackFilter = trackOptions.length > 2;
  const showModelFilter = modelOptions.length > 1;

  const totalStudentLessons = cohorts.reduce(
    (sum, cohort) => sum + cohort.student_lesson_count,
    0,
  );
  const cohortsCost = cohorts.reduce((sum, cohort) => sum + cohort.cost_usd, 0);
  const avgPerStudentLesson =
    totalStudentLessons > 0 ? cohortsCost / totalStudentLessons : 0;

  const totalStudents = cohorts.reduce(
    (sum, cohort) => sum + cohort.student_count,
    0,
  );
  const avgPerStudent = totalStudents > 0 ? cohortsCost / totalStudents : 0;

  return (
    <>
      <PageHeader
        title="Custos"
        description="Consumo de IA por turma, aluno e aula. Valores estimados em USD a partir do usage da API."
        actions={hasAnyMeasurement ? <ViewToggle value={view} onChange={setView} /> : undefined}
      />

      <ListToolbar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Buscar por turma ou trilha"
        searchLabel="Buscar turmas"
      >
        <FilterSegment
          value={period}
          options={PERIOD_SEGMENT_OPTIONS}
          onChange={setPeriod}
          aria-label="Filtrar por período"
        />
        {showTrackFilter && (
          <Select
            id="costs-track"
            className="list-toolbar__ui-select"
            value={track}
            onChange={setTrack}
            options={trackOptions}
            aria-label="Filtrar por trilha"
          />
        )}
        {showModelFilter && (
          <Select
            id="costs-model"
            className="list-toolbar__ui-select"
            value={model}
            onChange={setModel}
            options={modelOptions}
            aria-label="Filtrar por modelo"
          />
        )}
      </ListToolbar>

      {!hasAnyMeasurement && (
        <div className="card empty-state">
          <p>Nenhum consumo medido neste período.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            Os totais aparecem aqui depois das conversas, avaliações e ingestão.
          </p>
        </div>
      )}

      {hasAnyMeasurement && data && (
        <>
          <CostStats
            stats={
              cohorts.length === 0
                ? [
                    {
                      label: "Total no período",
                      value: formatUsd(data.total_cost_usd),
                      hint: formatPeriod(data.period_from, data.period_to),
                    },
                    {
                      label: "Sem turma atribuída",
                      value: formatUsd(data.unattributed_cost_usd),
                      hint: "Ingestão de material de trilha, que serve várias turmas",
                    },
                  ]
                : [
                    {
                      label: "Total no período",
                      value: formatUsd(data.total_cost_usd),
                      hint: formatPeriod(data.period_from, data.period_to),
                    },
                    {
                      label: "Por avaliação (aluno-aula)",
                      value: formatUsd(avgPerStudentLesson),
                      hint: `${totalStudentLessons} aluno-aula com medição`,
                    },
                    {
                      label: "Por aluno",
                      value: formatUsd(avgPerStudent),
                      hint: `${totalStudents} matriculados`,
                    },
                    ...(data.unattributed_cost_usd > 0
                      ? [
                          {
                            label: "Sem turma atribuída",
                            value: formatUsd(data.unattributed_cost_usd),
                            hint: "Ingestão de material de trilha, que serve várias turmas",
                          },
                        ]
                      : []),
                  ]
            }
          />

          <UnpricedWarning count={data.unpriced_events} />

          {cohorts.length === 0 && hasUnattributed && (
            <div className="card empty-state">
              <p>Nenhuma turma com consumo neste período.</p>
              <p className="muted" style={{ marginTop: 6 }}>
                O gasto acima é da ingestão de material da trilha. Ele não entra em
                nenhuma turma porque a trilha pode servir várias.
              </p>
            </div>
          )}

          {cohorts.length > 0 && !hasResults && <ListEmptyFilter />}

          {hasResults && (
            <>
              <DataTable
                columns={columns}
                rows={paging.items}
                rowKey={(cohort) => cohort.cohort_id}
                layout={view}
                aria-label="Custos por turma"
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
