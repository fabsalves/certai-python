import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { matchesAnySearch } from "../lib/listSearch";
import { useListView } from "../lib/useListView";
import { usePagination } from "../lib/usePagination";
import { type Cohort, uniqueProfessorNames } from "../lib/cohorts";
import { CohortsListSkeleton } from "../components/cohorts/CohortsListSkeleton";
import { PageHeader } from "../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../components/ui/DataTable";
import { ListEmptyFilter, ListFilterSelect, ListToolbar } from "../components/ui/ListToolbar";
import { Pagination } from "../components/ui/Pagination";
import { ViewToggle } from "../components/ui/ViewToggle";

function cohortTo(id: string) {
  return `/cohorts/${id}`;
}

function CohortShortcuts({ cohort, canManage }: { cohort: Cohort; canManage: boolean }) {
  if (canManage) {
    return (
      <>
        <Link
          to={cohortTo(cohort.id)}
          state={{ tab: "professors" }}
          className="btn btn-ghost btn-sm"
        >
          Professores
        </Link>
        <Link
          to={cohortTo(cohort.id)}
          state={{ tab: "students" }}
          className="btn btn-ghost btn-sm"
        >
          Alunos
        </Link>
        <Link
          to={cohortTo(cohort.id)}
          state={{ tab: "progress" }}
          className="btn btn-ghost btn-sm"
        >
          Andamento
        </Link>
      </>
    );
  }

  return (
    <>
      <Link
        to={cohortTo(cohort.id)}
        state={{ tab: "students" }}
        className="btn btn-ghost btn-sm"
      >
        Alunos
      </Link>
      <Link
        to={cohortTo(cohort.id)}
        state={{ tab: "progress" }}
        className="btn btn-ghost btn-sm"
      >
        Andamento
      </Link>
    </>
  );
}

export function Cohorts() {
  const { user } = useAuth();
  const [view, setView] = useListView("cohorts");
  const [search, setSearch] = useState("");
  const [trackFilter, setTrackFilter] = useState("");
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [loading, setLoading] = useState(true);
  const canManage = user?.role === "org_admin";

  const loadCohorts = useCallback(() => {
    setLoading(true);
    api
      .get<Cohort[]>("/cohorts")
      .then((r) => setCohorts(r.data))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadCohorts();
  }, [loadCohorts]);

  const trackOptions = useMemo(() => {
    const byId = new Map<string, string>();
    for (const cohort of cohorts) {
      byId.set(cohort.track_id, cohort.track_title);
    }
    return [
      { value: "", label: "Todas as trilhas" },
      ...[...byId.entries()]
        .sort((a, b) => a[1].localeCompare(b[1], "pt-BR"))
        .map(([value, label]) => ({ value, label })),
    ];
  }, [cohorts]);

  const filtered = useMemo(
    () =>
      cohorts.filter(
        (cohort) =>
          (!trackFilter || cohort.track_id === trackFilter) &&
          matchesAnySearch(search, [cohort.name, cohort.track_title]),
      ),
    [cohorts, search, trackFilter],
  );

  const paging = usePagination(filtered, { resetKey: `${search}|${trackFilter}` });

  const columns = useMemo<DataColumn<Cohort>[]>(() => {
    const base: DataColumn<Cohort>[] = [
      {
        id: "name",
        header: "Turma",
        primary: true,
        render: (cohort) => (
          <Link to={cohortTo(cohort.id)} state={{ tab: "meta" }} className="table__link table__primary">
            {cohort.name}
          </Link>
        ),
      },
      {
        id: "track",
        header: "Trilha",
        render: (cohort) => cohort.track_title,
      },
    ];

    if (canManage) {
      base.push({
        id: "professors",
        header: "Professores",
        render: (cohort) => (
          <span
            className="tag"
            title={cohort.module_professors
              .map((mp) => `${mp.module_title}: ${mp.professor_name}`)
              .join("\n")}
          >
            {uniqueProfessorNames(cohort)}
          </span>
        ),
      });
    }

    base.push(
      {
        id: "enrollment",
        header: "Matrículas",
        render: (cohort) => `${cohort.enrollment_count} aluno(s)`,
      },
      {
        id: "actions",
        header: "Ações",
        card: "actions",
        align: "end",
        render: (cohort) => (
          <div className="table__actions">
            <CohortShortcuts cohort={cohort} canManage={canManage} />
          </div>
        ),
      },
    );

    return base;
  }, [canManage]);

  if (loading) {
    return <CohortsListSkeleton canManage={canManage} />;
  }

  const hasCatalog = cohorts.length > 0;
  const hasResults = filtered.length > 0;
  const showTrackFilter = trackOptions.length > 2;

  return (
    <>
      <PageHeader
        title={canManage ? "Turmas" : "Minhas turmas"}
        description={
          canManage
            ? "Organize turmas por trilha, matricule alunos e acompanhe o andamento."
            : "Confirme quando a turma terminou uma aula para liberar a seguinte."
        }
        actions={
          canManage ? (
            <>
              {hasCatalog && <ViewToggle value={view} onChange={setView} />}
              <Link to="/cohorts/new" className="btn btn-primary">
                Nova turma
              </Link>
            </>
          ) : (
            hasCatalog ? <ViewToggle value={view} onChange={setView} /> : undefined
          )
        }
      />

      {!hasCatalog && (
        <div className="card empty-state">
          <p>Nenhuma turma cadastrada.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            {canManage
              ? "Crie uma turma vinculada a uma trilha, matricule alunos e acompanhe o percurso."
              : "Aguarde a matrícula em uma turma para começar."}
          </p>
          {canManage && (
            <Link to="/cohorts/new" className="btn btn-primary" style={{ marginTop: 20 }}>
              Nova turma
            </Link>
          )}
        </div>
      )}

      {hasCatalog && (
        <>
          <ListToolbar
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder="Buscar por turma ou trilha"
            searchLabel="Buscar turmas"
          >
            {showTrackFilter && (
              <ListFilterSelect
                id="cohorts-track-filter"
                value={trackFilter}
                onChange={setTrackFilter}
                options={trackOptions}
                aria-label="Filtrar por trilha"
              />
            )}
          </ListToolbar>

          {!hasResults && <ListEmptyFilter />}

          {hasResults && (
            <>
              <DataTable
                columns={columns}
                rows={paging.items}
                rowKey={(cohort) => cohort.id}
                layout={view}
                aria-label="Turmas"
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
