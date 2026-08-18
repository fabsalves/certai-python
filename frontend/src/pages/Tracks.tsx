import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { matchesAnySearch } from "../lib/listSearch";
import { useListView } from "../lib/useListView";
import { usePagination } from "../lib/usePagination";
import { sortedModules, totalLessons, activeLessonsCount, type Track } from "../lib/tracks";
import { TracksListSkeleton } from "../components/tracks/TracksListSkeleton";
import { PageHeader } from "../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../components/ui/DataTable";
import { FilterSegment, ListEmptyFilter, ListToolbar } from "../components/ui/ListToolbar";
import { Pagination } from "../components/ui/Pagination";
import { ViewToggle } from "../components/ui/ViewToggle";

type TrackStatusFilter = "all" | "published" | "draft" | "inactive";

const STATUS_OPTIONS: Array<{ value: TrackStatusFilter; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "published", label: "Publicada" },
  { value: "draft", label: "Rascunho" },
  { value: "inactive", label: "Desativada" },
];

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

function matchesTrackStatus(track: Track, status: TrackStatusFilter) {
  if (status === "all") return true;
  if (status === "inactive") return !track.is_active;
  if (!track.is_active) return false;
  if (status === "published") return track.published;
  return !track.published;
}

export function Tracks() {
  const [view, setView] = useListView("tracks");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<TrackStatusFilter>("all");
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

  const filtered = useMemo(
    () =>
      tracks.filter(
        (track) =>
          matchesTrackStatus(track, statusFilter) &&
          matchesAnySearch(search, [track.title, track.competency]),
      ),
    [tracks, search, statusFilter],
  );

  const paging = usePagination(filtered, { resetKey: `${search}|${statusFilter}` });

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

  const hasCatalog = tracks.length > 0;
  const hasResults = filtered.length > 0;

  return (
    <>
      <PageHeader
        title="Trilhas"
        description="Monte o percurso completo: trilha, módulos com nível e aulas em sequência."
        actions={
          <>
            {hasCatalog && <ViewToggle value={view} onChange={setView} />}
            <Link to="/tracks/new" className="btn btn-primary">
              Nova trilha
            </Link>
          </>
        }
      />

      {!hasCatalog && (
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

      {hasCatalog && (
        <>
          <ListToolbar
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder="Buscar por título ou objetivo"
            searchLabel="Buscar trilhas"
          >
            <FilterSegment
              value={statusFilter}
              options={STATUS_OPTIONS}
              onChange={setStatusFilter}
              aria-label="Filtrar por status"
            />
          </ListToolbar>

          {!hasResults && <ListEmptyFilter />}

          {hasResults && (
            <>
              <DataTable
                columns={columns}
                rows={paging.items}
                rowKey={(track) => track.id}
                layout={view}
                aria-label="Trilhas"
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
