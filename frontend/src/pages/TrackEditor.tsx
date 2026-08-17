import { type FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { EditorTabPanel, EditorTabs } from "../components/tracks/EditorTabs";
import {
  ContentSourceImport,
  type ContentSource,
} from "../components/tracks/LessonContentImport";
import { ModuleEditor } from "../components/tracks/ModuleEditor";
import { TrackEditorSkeleton } from "../components/tracks/TrackEditorSkeleton";
import { TrackPathPreview } from "../components/tracks/TrackPathPreview";
import {
  FileAttachmentBlock,
  FileChip,
  FilePicker,
  fileKindFromName,
} from "../components/ui/FileAttachment";
import { SortableList } from "../components/ui/SortableList";
import { api } from "../lib/api";
import { useConfirm } from "../lib/confirm";
import { downloadApiFile } from "../lib/download";
import { useFeedback } from "../lib/feedback";
import { useApiAction } from "../lib/useApiAction";
import { isNonEmpty, trimmed } from "../lib/validation";
import { persistSequentialPositions, withSequentialPositions } from "../lib/reorder";
import {
  nextModulePosition,
  sortedModules,
  totalLessons,
  type Module,
  type Track,
} from "../lib/tracks";

function descriptionSourceFromTrack(track: Track | null): ContentSource | null {
  if (!track?.description_source_filename) return null;
  return {
    filename: track.description_source_filename,
    contentType: track.description_source_content_type,
    kind: track.description_source_kind,
  };
}

type EditorTab = "meta" | "structure";

const INGESTION_LABELS: Record<string, string> = {
  pending: "Material aguardando processamento",
  processing: "Processando material…",
  done: "Material processado",
  failed: "Falha ao processar o material",
  unsupported: "Formato sem processamento automático (envie PDF ou PPTX)",
};

export function TrackEditor() {
  const { trackId } = useParams<{ trackId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const confirm = useConfirm();
  const runAction = useApiAction();
  const feedback = useFeedback();
  const isNew = trackId === "new";

  const [track, setTrack] = useState<Track | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [title, setTitle] = useState("");
  const [competency, setCompetency] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [addingModule, setAddingModule] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);
  const [expandedModuleId, setExpandedModuleId] = useState<string | null>(null);
  const [tab, setTab] = useState<EditorTab>("meta");
  const [materialFile, setMaterialFile] = useState<File | null>(null);
  const [uploadingMaterial, setUploadingMaterial] = useState(false);
  const [downloadingMaterial, setDownloadingMaterial] = useState(false);
  const [reingestingMaterial, setReingestingMaterial] = useState(false);

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

  function postMaterial(trackId: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    return api.post<Track>(`/tracks/${trackId}/material`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  }

  async function saveMeta(e?: FormEvent) {
    e?.preventDefault();
    const nextTitle = trimmed(title);
    if (!nextTitle) {
      feedback.error("Informe o título da trilha.");
      return;
    }
    setSaving(true);
    if (isNew) {
      const created = await runAction({
        run: () => api.post<Track>("/tracks", { title: nextTitle, competency, description }),
        successMessage: "Trilha criada.",
        errorMessage: "Não foi possível criar a trilha.",
      });
      if (!created) {
        setSaving(false);
        return;
      }
      if (materialFile) {
        const uploaded = await runAction({
          run: () => postMaterial(created.data.id, materialFile),
          successMessage: "Material da trilha enviado.",
          errorMessage: "Não foi possível enviar o material.",
        });
        if (!uploaded) {
          navigate(`/tracks/${created.data.id}`, { replace: true, state: { tab: "meta" } });
          setSaving(false);
          return;
        }
        setMaterialFile(null);
      }
      navigate(`/tracks/${created.data.id}`, { replace: true, state: { tab: "structure" } });
      setSaving(false);
      return;
    }
    if (!track) {
      setSaving(false);
      return;
    }
    await runAction({
      run: () =>
        api.patch<Track>(`/tracks/${track.id}`, { title: nextTitle, competency, description }),
      successMessage: "Dados da trilha salvos.",
      errorMessage: "Não foi possível salvar a trilha.",
      onSuccess: ({ data }) => setTrack(data),
    });
    setSaving(false);
  }

  async function uploadMaterial() {
    if (!track || !materialFile) return;
    setUploadingMaterial(true);
    await runAction({
      run: () => postMaterial(track.id, materialFile),
      successMessage: "Material da trilha enviado.",
      errorMessage: "Não foi possível enviar o material.",
      onSuccess: ({ data }) => {
        setTrack(data);
        setMaterialFile(null);
      },
    });
    setUploadingMaterial(false);
  }

  async function downloadMaterial() {
    if (!track?.material_filename) return;
    setDownloadingMaterial(true);
    await runAction({
      run: () => downloadApiFile(`/tracks/${track.id}/material`, track.material_filename ?? "material"),
      errorMessage: "Não foi possível baixar o material.",
    });
    setDownloadingMaterial(false);
  }

  async function reingestMaterial() {
    if (!track?.material_filename) return;
    setReingestingMaterial(true);
    await runAction({
      run: () => api.post<Track>(`/tracks/${track.id}/material/ingest`),
      successMessage: "Processamento do material enfileirado.",
      errorMessage: "Não foi possível reprocessar o material.",
      onSuccess: ({ data }) => setTrack(data),
    });
    setReingestingMaterial(false);
  }

  // Refresh the ingestion status while the worker processes the material.
  const materialIngestionStatus = track?.material_ingestion_status ?? null;
  useEffect(() => {
    if (materialIngestionStatus !== "pending" && materialIngestionStatus !== "processing") return;
    const timer = window.setInterval(reloadTrack, 4000);
    return () => window.clearInterval(timer);
  }, [materialIngestionStatus, reloadTrack]);

  async function togglePublish() {
    if (!track || !track.is_active) return;
    setSaving(true);
    if (track.published) {
      await runAction({
        run: () => api.patch<Track>(`/tracks/${track.id}`, { published: false }),
        successMessage: "Trilha despublicada.",
        errorMessage: "Não foi possível despublicar a trilha.",
        onSuccess: ({ data }) => setTrack(data),
      });
    } else {
      await runAction({
        run: () => api.post<Track>(`/tracks/${track.id}/publish`),
        successMessage: "Trilha publicada.",
        errorMessage: "Não foi possível publicar a trilha.",
        onSuccess: ({ data }) => setTrack(data),
      });
    }
    setSaving(false);
  }

  async function toggleTrackActive() {
    if (!track) return;
    if (track.is_active) {
      const ok = await confirm({
        title: "Desativar trilha",
        message: "Desativar esta trilha? Turmas novas não poderão usá-la.",
        confirmLabel: "Desativar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setSaving(true);
    await runAction({
      run: () => api.patch<Track>(`/tracks/${track.id}`, { is_active: !track.is_active }),
      successMessage: track.is_active ? "Trilha desativada." : "Trilha reativada.",
      errorMessage: "Não foi possível alterar a trilha.",
      onSuccess: ({ data }) => setTrack(data),
    });
    setSaving(false);
  }

  async function addModule() {
    if (!track) return;
    setAddingModule(true);
    await runAction({
      run: () =>
        api.post<Module>(`/tracks/${track.id}/modules`, {
          title: `Módulo ${nextModulePosition(track)}`,
          level: "beginner",
          position: nextModulePosition(track),
        }),
      successMessage: "Módulo adicionado.",
      errorMessage: "Não foi possível adicionar o módulo.",
      onSuccess: async ({ data }) => {
        await reloadTrack();
        setExpandedModuleId(data.id);
      },
    });
    setAddingModule(false);
  }

  async function reorderModules(ordered: Module[]) {
    if (!track) return;
    const previous = track;
    setTrack({ ...track, modules: withSequentialPositions(ordered) });
    const result = await runAction({
      run: async () => {
        await persistSequentialPositions(ordered, (id, position) =>
          api.patch(`/tracks/modules/${id}`, { position }),
        );
      },
      successMessage: "Ordem dos módulos atualizada.",
      errorMessage: "Não foi possível reordenar os módulos.",
    });
    if (result === null) {
      setTrack(previous);
      await reloadTrack();
    }
  }

  function selectLesson(lessonId: string, moduleId: string) {
    setTab("structure");
    setSelectedLessonId(lessonId);
    setExpandedModuleId(moduleId);
    document.getElementById(`lesson-${lessonId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById(`module-${moduleId}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  if (loading) return <TrackEditorSkeleton />;
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
                      ? "Nome, objetivo, descrição e material. Depois monte módulos e aulas na outra aba."
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
                      {track && !isNew && (
                        <ContentSourceImport
                          idPrefix={`track-description-${track.id}`}
                          importUrl={`/tracks/${track.id}/import-description`}
                          downloadUrl={`/tracks/${track.id}/description-source`}
                          disabled={saving}
                          currentContent={description}
                          source={descriptionSourceFromTrack(track)}
                          onImported={(text) => {
                            setDescription(text);
                            void reloadTrack();
                          }}
                          fieldLabel="Preencher descrição a partir de áudio ou arquivo"
                          hint="Grave ou anexe. O texto novo é acrescentado à descrição (separado do material PDF/PPT); o arquivo fonte fica o último anexado."
                        />
                      )}
                    </div>
                  </div>

                  <div className="track-meta__material">
                    <FileAttachmentBlock
                      label="Material da trilha"
                      hint={
                        isNew
                          ? "PDF ou PPT. Opcional; você também pode enviar depois."
                          : "PDF ou PPT. Um arquivo por trilha; enviar outro substitui o atual."
                      }
                    >
                      {track?.material_filename && !materialFile && (
                        <FileChip
                          filename={track.material_filename}
                          kind={fileKindFromName(track.material_filename)}
                          meta={
                            materialIngestionStatus
                              ? INGESTION_LABELS[materialIngestionStatus] ?? materialIngestionStatus
                              : "Ainda não processado"
                          }
                          onDownload={downloadMaterial}
                          downloading={downloadingMaterial}
                        />
                      )}
                      {track?.material_filename &&
                        !materialFile &&
                        (materialIngestionStatus === "failed" || materialIngestionStatus === null) && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            disabled={reingestingMaterial}
                            onClick={reingestMaterial}
                          >
                            {reingestingMaterial
                              ? "Enfileirando…"
                              : materialIngestionStatus === "failed"
                                ? "Reprocessar material"
                                : "Processar material"}
                          </button>
                        )}
                      {materialFile && (
                        <FileChip
                          filename={materialFile.name}
                          kind={fileKindFromName(materialFile.name)}
                          meta={isNew ? "Vai junto ao criar a trilha" : "Pronto para enviar"}
                          onClear={() => setMaterialFile(null)}
                          clearLabel="Cancelar"
                        />
                      )}
                      <div className="file-attachment__actions">
                        <FilePicker
                          id="track-material"
                          accept=".pdf,.ppt,.pptx,application/pdf,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                          buttonLabel={
                            track?.material_filename || materialFile
                              ? "Escolher outro arquivo"
                              : "Escolher arquivo"
                          }
                          disabled={saving || uploadingMaterial}
                          onChange={setMaterialFile}
                        />
                        {track && materialFile && (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={uploadingMaterial}
                            onClick={() => void uploadMaterial()}
                          >
                            {uploadingMaterial
                              ? "Enviando…"
                              : track.material_filename
                                ? "Substituir material"
                                : "Enviar material"}
                          </button>
                        )}
                      </div>
                    </FileAttachmentBlock>
                  </div>

                  {(isNew || metaDirty) && (
                    <button
                      type="submit"
                      className="btn btn-primary"
                      disabled={saving || !isNonEmpty(title)}
                    >
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
                            siblingModules={modules.filter((m) => m.id !== mod.id)}
                            open={expandedModuleId === mod.id}
                            onToggle={() =>
                              setExpandedModuleId((current) => (current === mod.id ? null : mod.id))
                            }
                            selectedLessonId={selectedLessonId}
                            onSelectLesson={setSelectedLessonId}
                            onChanged={reloadTrack}
                            onLessonsReordered={(lessons) => {
                              setTrack((current) =>
                                current
                                  ? {
                                      ...current,
                                      modules: current.modules.map((item) =>
                                        item.id === mod.id ? { ...item, lessons } : item,
                                      ),
                                    }
                                  : current,
                              );
                            }}
                            onRemoved={() => {
                              setExpandedModuleId((current) => (current === mod.id ? null : current));
                              setSelectedLessonId(null);
                            }}
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
