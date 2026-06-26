import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { sortedModules, totalLessons, activeLessonsCount, type Track } from "../lib/tracks";
import { PageHeader } from "../components/layout/PageHeader";

export function Tracks() {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTracks = useCallback(() => {
    setLoading(true);
    api
      .get<Track[]>("/tracks")
      .then((r) => setTracks(r.data))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadTracks();
  }, [loadTracks]);

  return (
    <>
      <PageHeader
        title="Trilhas"
        description="Monte o percurso completo: trilha, módulos com nível e aulas em sequência."
        actions={
          <Link to="/tracks/new" className="btn btn-primary">
            Nova trilha
          </Link>
        }
      />

      {loading && <p className="muted">Carregando trilhas…</p>}

      {!loading && tracks.length === 0 && (
        <div className="card empty-state">
          <p>Nenhuma trilha ainda.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            Abra o editor para cadastrar módulos e aulas com visualização do percurso.
          </p>
          <Link to="/tracks/new" className="btn btn-primary" style={{ marginTop: 20 }}>
            Nova trilha
          </Link>
        </div>
      )}

      {!loading && tracks.length > 0 && (
        <div className="tracks-list">
          {tracks.map((t) => {
            const modules = sortedModules(t);
            return (
              <Link
                key={t.id}
                to={`/tracks/${t.id}`}
                className={`card tracks-list__item${!t.is_active ? " tracks-list__item--inactive" : ""}`}
              >
                <div className="tracks-list__head">
                  <div>
                    <h3 style={{ margin: 0 }}>{t.title}</h3>
                    <p className="muted" style={{ marginTop: 4, fontSize: 14 }}>
                      {t.competency || "Sem objetivo definido"}
                    </p>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                    {!t.is_active && <span className="tag tag--inactive">Desativada</span>}
                    {t.is_active && (t.published
                      ? <span className="tag tag--brand">Publicada</span>
                      : <span className="tag">Rascunho</span>)}
                  </div>
                </div>
                <p className="muted tracks-list__meta">
                  {modules.length} módulo(s) · {activeLessonsCount(t)} aula(s) ativa(s)
                  {activeLessonsCount(t) !== totalLessons(t) && ` (${totalLessons(t)} no total)`}
                </p>
              </Link>
            );
          })}
        </div>
      )}
    </>
  );
}
