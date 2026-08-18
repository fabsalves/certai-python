import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useListView } from "../lib/useListView";
import { sortedModules, totalLessons, activeLessonsCount, type Track } from "../lib/tracks";
import { TracksListSkeleton } from "../components/tracks/TracksListSkeleton";
import { PageHeader } from "../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../components/ui/DataTable";
import { ViewToggle } from "../components/ui/ViewToggle";

function trackStatus(track: Track) {
  if (!track.is_active) {
    return <span className="tag tag--inactive">Desativada</span>;
  }
  if (track.published) {
    return <span className="tag tag--brand">Publicada</span>;
  }
  return <span className="tag">Rascunho</span>;
}

function trackMeta(track: Track) {
  const modules = sortedModules(track);
  const active = activeLessonsCount(track);
  const total = totalLessons(track);
  return (
    <>
      {modules.length} módulo(s) · {active} aula(s) ativa(s)
      {active !== total && ` (${total} no total)`}
    </>
  );
}

export function Tracks() {
  const [view, setView] = useListView("tracks");
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

  const columns = useMemo<DataColumn<Track>[]>(
    () => [
      {
        id: "title",
        header: "Trilha",
        primary: true,
        render: (track) => (
          <Link
            to={`/tracks/${track.id}`}
            className={`table__link table__primary${!track.is_active ? " table__primary--muted" : ""}`}
          >
            {track.title}
          </Link>
        ),
      },
      {
        id: "competency",
        header: "Objetivo",
        render: (track) => track.competency || "Sem objetivo definido",
      },
      {
        id: "status",
        header: "Status",
        render: (track) => trackStatus(track),
      },
      {
        id: "meta",
        header: "Estrutura",
        render: (track) => <span className="muted">{trackMeta(track)}</span>,
      },
      {
        id: "actions",
        header: "",
        card: "actions",
        align: "end",
        render: (track) => (
          <div className="table__actions">
            <Link to={`/tracks/${track.id}`} className="btn btn-ghost btn-sm">
              Abrir
            </Link>
          </div>
        ),
      },
    ],
    [],
  );

  if (loading) {
    return <TracksListSkeleton />;
  }

  return (
    <>
      <PageHeader
        title="Trilhas"
        description="Monte o percurso completo: trilha, módulos com nível e aulas em sequência."
        actions={
          <>
            {tracks.length > 0 && <ViewToggle value={view} onChange={setView} />}
            <Link to="/tracks/new" className="btn btn-primary">
              Nova trilha
            </Link>
          </>
        }
      />

      {tracks.length === 0 && (
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

      {tracks.length > 0 && (
        <DataTable
          columns={columns}
          rows={tracks}
          rowKey={(track) => track.id}
          layout={view}
          aria-label="Trilhas"
        />
      )}
    </>
  );
}
