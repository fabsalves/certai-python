import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { PageHeader } from "../components/layout/PageHeader";

export function Dashboard() {
  const { user } = useAuth();
  if (!user) return null;

  const firstName = user.name.split(" ")[0];
  const isStudent = user.role === "student";
  const isContentRole = user.role === "admin" || user.role === "designer";
  const isProfessor = user.role === "professor";

  return (
    <>
      <PageHeader
        title={`Olá, ${firstName}.`}
        description="Aqui você acompanha trilhas, turmas e o andamento das aulas."
      />

      <div className="page-grid page-grid--stats" style={{ marginBottom: 24 }}>
        {isContentRole && (
          <>
            <div className="card stat-card">
              <div className="stat-card__label">Trilhas publicadas</div>
              <div className="stat-card__value">—</div>
            </div>
            <div className="card stat-card">
              <div className="stat-card__label">Turmas em andamento</div>
              <div className="stat-card__value">—</div>
            </div>
          </>
        )}
        {isProfessor && (
          <div className="card stat-card">
            <div className="stat-card__label">Turmas sob sua responsabilidade</div>
            <div className="stat-card__value">—</div>
          </div>
        )}
        {isStudent && (
          <div className="card stat-card">
            <div className="stat-card__label">Aulas já liberadas</div>
            <div className="stat-card__value">—</div>
          </div>
        )}
        <div className="card stat-card">
          <div className="stat-card__label">Certificados emitidos</div>
          <div className="stat-card__value">—</div>
        </div>
      </div>

      <div className="page-grid page-grid--2">
        <div className="card" style={{ padding: 28 }}>
          <h3>Como funciona</h3>
          <p className="muted" style={{ marginTop: 10 }}>
            O conteúdo é montado em trilhas, módulo a módulo. O professor informa quando a turma
            concluiu uma aula; só então o grupo avança e o material seguinte fica disponível.
            O registro de aprendizado usa níveis descritivos — sem nota numérica.
          </p>
        </div>

        <div className="card" style={{ padding: 28 }}>
          <h3>Atalhos</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 14 }}>
            {isContentRole && (
              <>
                <Link to="/tracks" className="btn btn-ghost" style={{ justifyContent: "flex-start" }}>
                  Ver trilhas
                </Link>
                <Link to="/cohorts" className="btn btn-ghost" style={{ justifyContent: "flex-start" }}>
                  Ver turmas
                </Link>
                <Link to="/professors" className="btn btn-ghost" style={{ justifyContent: "flex-start" }}>
                  Ver professores
                </Link>
              </>
            )}
            {isProfessor && (
              <Link to="/cohorts" className="btn btn-ghost" style={{ justifyContent: "flex-start" }}>
                Minhas turmas
              </Link>
            )}
            {isStudent && (
              <Link to="/learn" className="btn btn-primary" style={{ justifyContent: "flex-start" }}>
                Abrir minhas aulas
              </Link>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
