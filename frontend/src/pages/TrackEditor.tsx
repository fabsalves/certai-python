import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { EditorTabPanel, EditorTabs } from "../components/tracks/EditorTabs";
import { ModuleEditor } from "../components/tracks/ModuleEditor";
import { TrackPathPreview } from "../components/tracks/TrackPathPreview";
import { SortableList } from "../components/ui/SortableList";
import { api } from "../lib/api";
import { persistSequentialPositions } from "../lib/reorder";
import {
  nextModulePosition,
  sortedModules,
  totalLessons,
  type Module,
  type Track,
} from "../lib/tracks";

type EditorTab = "meta" | "structure";

export function TrackEditor() {
  const { trackId } = useParams<{ trackId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const isNew = trackId === "new";

  const [track, setTrack] = useState<Track | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [title, setTitle] = useState("");
  const [competency, setCompetency] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [addingModule, setAddingModule] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);
  const [expandedModuleId, setExpandedModuleId] = useState<string | null>(null);
  const [tab, setTab] = useState<EditorTab>("meta");

  const reloadTrack = useCallback(async () => {
    if (!trackId || isNew) return;
    setLoadError("");
    try {
      const { data } = await api.get<Track>(`/tracks/${trackId}`);
      setTrack(data);
      setTitle(data.title);
      setCompetency(data.competency);
      setDescription(data.description);
    } catch (err) {
      if (axios.isCancel(err)) return;
      setLoadError("Trilha não encontrada.");
    }
  }, [trackId, isNew]);

  useEffect(() => {
    if (isNew) {
      setTrack(null);
      setLoadError("");
      setFormError("");
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setLoadError("");

    api
      .get<Track>(`/tracks/${trackId}`, { signal: controller.signal })
      .then(({ data }) => {
        setTrack(data);
        setTitle(data.title);
        setCompetency(data.competency);
        setDescription(data.description);
      })
      .catch((err) => {
        if (controller.signal.aborted || axios.isCancel(err)) return;
        setTrack(null);
        setLoadError("Trilha não encontrada.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [trackId, isNew]);

  useEffect(() => {
    const nextTab = (location.state as { tab?: EditorTab } | null)?.tab;
    if (nextTab === "meta" || nextTab === "structure") {
      setTab(nextTab);
      return;
    }
    setTab(isNew ? "meta" : "structure");
  }, [trackId, isNew, location.state]);

  const metaDirty = track
    ? title !== track.title || competency !== track.competency || description !== track.description
    : title.trim().length > 0;

  async function saveMeta(e?: FormEvent) {
    e?.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      if (isNew) {
        const { data } = await api.post<Track>("/tracks", { title, competency, description });
        navigate(`/tracks/${data.id}`, { replace: true, state: { tab: "structure" } });
        return;
      }
      if (!track) return;
      const { data } = await api.patch<Track>(`/tracks/${track.id}`, { title, competency, description });
      setTrack(data);
    } catch {
      setFormError("Não foi possível salvar a trilha.");
    } finally {
      setSaving(false);
    }
  }

  async function togglePublish() {
    if (!track || !track.is_active) return;
    setSaving(true);
    try {
      if (track.published) {
        const { data } = await api.patch<Track>(`/tracks/${track.id}`, { published: false });
        setTrack(data);
      } else {
        const { data } = await api.post<Track>(`/tracks/${track.id}/publish`);
        setTrack(data);
      }
    } finally {
      setSaving(false);
    }
  }

  async function toggleTrackActive() {
    if (!track) return;
    if (track.is_active && !confirm("Desativar esta trilha? Turmas novas não poderão usá-la.")) return;
    setSaving(true);
    try {
      const { data } = await api.patch<Track>(`/tracks/${track.id}`, { is_active: !track.is_active });
      setTrack(data);
    } finally {
      setSaving(false);
    }
  }

  async function addModule() {
    if (!track) return;
    setAddingModule(true);
    try {
      const { data } = await api.post<Module>(`/tracks/${track.id}/modules`, {
        title: `Módulo ${nextModulePosition(track)}`,
        level: "beginner",
        position: nextModulePosition(track),
      });
      await reloadTrack();
      setExpandedModuleId(data.id);
    } finally {
      setAddingModule(false);
    }
  }

  async function reorderModules(ordered: Module[]) {
    await persistSequentialPositions(ordered, (id, position) =>
      api.patch(`/tracks/modules/${id}`, { position }),
    );
    await reloadTrack();
  }

  function selectLesson(lessonId: string, moduleId: string) {
    setTab("structure");
    setSelectedLessonId(lessonId);
    setExpandedModuleId(moduleId);
    document.getElementById(`lesson-${lessonId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById(`module-${moduleId}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  if (loading) return <p className="muted">Carregando trilha…</p>;
  if (loadError && !isNew && !track) return <p className="form-error">{loadError}</p>;

  const modules = track ? sortedModules(track) : [];
  const previewTrack: Track = track ?? {
    id: "",
    title,
    description,
    competency,
    published: false,
    is_active: true,
    modules: [],
  };

  return (
    <div className="track-editor">
      <div className="track-editor__toolbar">
        <Link to="/tracks" className="track-editor__back">← Trilhas</Link>
        <div className="track-editor__toolbar-actions">
          {track && !track.is_active && <span className="tag tag--inactive">Desativada</span>}
          {track && track.is_active && (
            <span className="tag">{track.published ? "Publicada" : "Rascunho"}</span>
          )}
          {track && (
            <button type="button" className="btn btn-ghost" disabled={saving} onClick={toggleTrackActive}>
              {track.is_active ? "Desativar trilha" : "Reativar trilha"}
            </button>
          )}
          {track && track.is_active && (
            <button type="button" className="btn btn-ghost" disabled={saving} onClick={togglePublish}>
              {track.published ? "Despublicar" : "Publicar"}
            </button>
          )}
        </div>
      </div>

      <div className={`track-editor__layout${tab === "structure" && track ? "" : " track-editor__layout--single"}`}>
        <div className="track-editor__main">
          <div className="card track-editor-panel">
            <EditorTabs
              tabs={[
                { id: "meta", label: isNew ? "Nova trilha" : "Dados da trilha" },
                {
                  id: "structure",
                  label: "Módulos e aulas",
                  disabled: !track,
                  count: track ? modules.length : undefined,
                },
              ]}
              active={tab}
              onChange={(id) => setTab(id as EditorTab)}
            >
              <EditorTabPanel id="meta" labelledBy="track-tab-meta" hidden={tab !== "meta"}>
                <form className="track-meta" onSubmit={saveMeta}>
                  <p className="muted track-meta__hint">
                    {isNew
                      ? "Nome, objetivo e descrição. Depois monte módulos e aulas na outra aba."
                      : `${modules.length} módulo(s) · ${track ? totalLessons(track) : 0} aula(s)`}
                  </p>

                  <div className="track-meta__fields">
                    <div className="field">
                      <label htmlFor="track-title">Título</label>
                      <input
                        id="track-title"
                        className="input"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        required
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="track-objective">Objetivo</label>
                      <input
                        id="track-objective"
                        className="input"
                        value={competency}
                        onChange={(e) => setCompetency(e.target.value)}
                        placeholder="O que o aluno deve saber fazer ao concluir"
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="track-description">Descrição</label>
                      <textarea
                        id="track-description"
                        className="input"
                        rows={4}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                      />
                    </div>
                  </div>

                  {formError && <div className="form-error">{formError}</div>}

                  {(isNew || metaDirty) && (
                    <button type="submit" className="btn btn-primary" disabled={saving}>
                      {saving ? "Salvando…" : isNew ? "Criar trilha" : "Salvar dados"}
                    </button>
                  )}
                </form>
              </EditorTabPanel>

              <EditorTabPanel id="structure" labelledBy="track-tab-structure" hidden={tab !== "structure" || !track}>
                {track && (
                  <section className="track-structure">
                    <div className="track-structure__toolbar">
                      <p className="muted track-structure__hint">
                        Arraste pelo ícone ⋮⋮ para reordenar módulos e aulas. Expanda um módulo para editar o conteúdo.
                      </p>
                      <button type="button" className="btn btn-primary" disabled={addingModule} onClick={addModule}>
                        {addingModule ? "Adicionando…" : "Novo módulo"}
                      </button>
                    </div>

                    {modules.length === 0 && (
                      <div className="empty-state track-structure__empty">
                        <p>Nenhum módulo ainda.</p>
                        <p className="muted" style={{ marginTop: 6 }}>
                          Cada módulo agrupa aulas em sequência, com um nível de dificuldade.
                        </p>
                        <button
                          type="button"
                          className="btn btn-primary"
                          style={{ marginTop: 20 }}
                          disabled={addingModule}
                          onClick={addModule}
                        >
                          Criar primeiro módulo
                        </button>
                      </div>
                    )}

                    {modules.length > 0 && (
                      <SortableList
                        items={modules}
                        className="structure-stack"
                        onReorder={reorderModules}
                        renderItem={(mod, sortable) => (
                          <ModuleEditor
                            module={mod}
                            open={expandedModuleId === mod.id}
                            onToggle={() =>
                              setExpandedModuleId((current) => (current === mod.id ? null : mod.id))
                            }
                            selectedLessonId={selectedLessonId}
                            onSelectLesson={setSelectedLessonId}
                            onChanged={reloadTrack}
                            sortable={sortable}
                          />
                        )}
                      />
                    )}
                  </section>
                )}
              </EditorTabPanel>
            </EditorTabs>
          </div>
        </div>

        {tab === "structure" && track && (
          <aside className="track-editor__preview">
            <TrackPathPreview
              track={previewTrack}
              selectedLessonId={selectedLessonId}
              onSelectLesson={selectLesson}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
