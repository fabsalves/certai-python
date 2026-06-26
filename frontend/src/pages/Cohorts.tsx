import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { type Cohort, uniqueProfessorNames } from "../lib/cohorts";
import { PageHeader } from "../components/layout/PageHeader";

export function Cohorts() {
  const { user } = useAuth();
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
            <Link to="/cohorts/new" className="btn btn-primary">
              Nova turma
            </Link>
          ) : undefined
        }
      />

      {loading && <p className="muted">Carregando turmas…</p>}

      {!loading && cohorts.length === 0 && (
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

      {!loading && cohorts.length > 0 && (
        <div className="cohorts-list">
          {cohorts.map((c) => (
            <Link key={c.id} to={`/cohorts/${c.id}`} className="card cohorts-list__item">
              <div className="cohorts-list__head">
                <div>
                  <h3 style={{ margin: 0 }}>{c.name}</h3>
                  <p className="muted" style={{ marginTop: 4, fontSize: 14 }}>
                    {c.track_title}
                  </p>
                </div>
                {canManage && (
                  <span className="tag" title={c.module_professors.map((mp) => `${mp.module_title}: ${mp.professor_name}`).join("\n")}>
                    {uniqueProfessorNames(c)}
                  </span>
                )}
              </div>
              <p className="muted cohorts-list__meta">
                {c.enrollment_count} aluno(s) matriculado(s)
              </p>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
