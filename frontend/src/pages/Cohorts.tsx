import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useListView } from "../lib/useListView";
import { type Cohort, uniqueProfessorNames } from "../lib/cohorts";
import { CohortsListSkeleton } from "../components/cohorts/CohortsListSkeleton";
import { PageHeader } from "../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../components/ui/DataTable";
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
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [loading, setLoading] = useState(true);
  const canManage = user?.role === "admin" || user?.role === "designer";

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
              {cohorts.length > 0 && <ViewToggle value={view} onChange={setView} />}
              <Link to="/cohorts/new" className="btn btn-primary">
                Nova turma
              </Link>
            </>
          ) : (
            cohorts.length > 0 ? <ViewToggle value={view} onChange={setView} /> : undefined
          )
        }
      />

      {cohorts.length === 0 && (
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

      {cohorts.length > 0 && (
        <DataTable
          columns={columns}
          rows={cohorts}
          rowKey={(cohort) => cohort.id}
          layout={view}
          aria-label="Turmas"
        />
      )}
    </>
  );
}
