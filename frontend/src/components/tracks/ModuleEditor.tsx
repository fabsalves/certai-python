import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useConfirm } from "../../lib/confirm";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import { isDuplicateName, isNonEmpty, trimmed } from "../../lib/validation";
import { persistSequentialPositions, withSequentialPositions } from "../../lib/reorder";
import { DragHandle } from "../ui/DragHandle";
import { SortableList, type SortableRenderProps } from "../ui/SortableList";
import { LessonEditorPanel, LessonListItem } from "./LessonEditor";
import {
  ContentSourceImport,
  type ContentSource,
} from "./LessonContentImport";
import {
  MODULE_LEVELS,
  levelLabel,
  nextLessonPosition,
  sortedLessons,
  type Lesson,
  type Module,
  type ModuleLevel,
} from "../../lib/tracks";

type ModulePane = "meta" | "lessons";

function descriptionSourceFromModule(module: Module): ContentSource | null {
  if (!module.description_source_filename) return null;
  return {
    filename: module.description_source_filename,
    contentType: module.description_source_content_type,
    kind: module.description_source_kind,
  };
}

interface Props {
  module: Module;
  open: boolean;
  onToggle: () => void;
  selectedLessonId: string | null;
  onSelectLesson: (lessonId: string | null) => void;
  onChanged: () => void | Promise<void>;
  onLessonsReordered?: (lessons: Lesson[]) => void;
  onRemoved?: () => void;
  siblingModules?: Module[];
  sortable?: SortableRenderProps;
}

export function ModuleEditor({
  module,
  open,
  onToggle,
  selectedLessonId,
  onSelectLesson,
  onChanged,
  onLessonsReordered,
  onRemoved,
  siblingModules = [],
  sortable,
}: Props) {
  const confirm = useConfirm();
  const feedback = useFeedback();
  const runAction = useApiAction();
  const lessons = sortedLessons(module);
  const siblingModuleTitles = siblingModules.map((item) => item.title);
  const selectedLesson = lessons.find((l) => l.id === selectedLessonId) ?? null;
  const [title, setTitle] = useState(module.title);
  const [description, setDescription] = useState(module.description ?? "");
  const [level, setLevel] = useState<ModuleLevel>(module.level);
  const [source, setSource] = useState<ContentSource | null>(() =>
    descriptionSourceFromModule(module),
  );
  const [savingModule, setSavingModule] = useState(false);
  const [busyLessonId, setBusyLessonId] = useState<string | null>(null);
  const [reorderingLessons, setReorderingLessons] = useState(false);
  const [pane, setPane] = useState<ModulePane>(() =>
    module.lessons.length === 0 ? "meta" : "lessons",
  );

  const moduleDirty =
    title !== module.title ||
    description !== (module.description ?? "") ||
    level !== module.level;
  const moduleTitleValid =
    isNonEmpty(title) && !isDuplicateName(title, siblingModuleTitles, module.title);
  const lessonTitles = lessons.map((lesson) => lesson.title);

  useEffect(() => {
    setTitle(module.title);
    setDescription(module.description ?? "");
    setLevel(module.level);
    setSource(descriptionSourceFromModule(module));
  }, [
    module.id,
    module.title,
    module.description,
    module.level,
    module.description_source_filename,
    module.description_source_content_type,
    module.description_source_kind,
  ]);

  useEffect(() => {
    if (open && selectedLesson) setPane("lessons");
  }, [open, selectedLesson]);

  async function saveModule() {
    const nextTitle = trimmed(title);
    if (!nextTitle) {
      feedback.error("Informe o nome do módulo.");
      return;
    }
    if (isDuplicateName(nextTitle, siblingModuleTitles, module.title)) {
      feedback.error("Já existe um módulo com este nome nesta trilha.");
      return;
    }
    setSavingModule(true);
    await runAction({
      run: () =>
        api.patch(`/tracks/modules/${module.id}`, {
          title: nextTitle,
          description,
          level,
        }),
      successMessage: "Módulo salvo.",
      errorMessage: "Não foi possível salvar o módulo.",
      onSuccess: () => onChanged(),
    });
    setSavingModule(false);
  }

  async function toggleModuleActive() {
    setSavingModule(true);
    await runAction({
      run: () =>
        api.patch(`/tracks/modules/${module.id}`, { is_active: !module.is_active }),
      successMessage: module.is_active ? "Módulo desativado." : "Módulo reativado.",
      errorMessage: "Não foi possível alterar o módulo.",
      onSuccess: () => onChanged(),
    });
    setSavingModule(false);
  }

  async function removeModule() {
    const ok = await confirm({
      title: "Excluir módulo",
      message: `Excluir o módulo "${module.title}" e todas as aulas?`,
      confirmLabel: "Excluir",
      tone: "danger",
    });
    if (!ok) return;
    setSavingModule(true);
    const deleted = await runAction({
      run: () => api.delete(`/tracks/modules/${module.id}`),
      successMessage: `Módulo "${module.title}" excluído.`,
      errorMessage: "Não foi possível excluir o módulo.",
    });
    if (deleted !== null) {
      await runAction({
        run: () =>
          persistSequentialPositions(siblingModules, (id, position) =>
            api.patch(`/tracks/modules/${id}`, { position }),
          ),
        errorMessage: "Não foi possível atualizar a ordem dos módulos.",
      });
      onRemoved?.();
      onSelectLesson(null);
      await onChanged();
    }
    setSavingModule(false);
  }

  async function addLesson() {
    setBusyLessonId("new");
    await runAction({
      run: () =>
        api.post<Lesson>(`/tracks/modules/${module.id}/lessons`, {
          title: `Aula ${nextLessonPosition(module)}`,
          content: "",
          position: nextLessonPosition(module),
        }),
      successMessage: "Aula adicionada.",
      errorMessage: "Não foi possível adicionar a aula.",
      onSuccess: ({ data }) => {
        onChanged();
        onSelectLesson(data.id);
      },
    });
    setBusyLessonId(null);
  }

  async function reorderLessons(ordered: Lesson[]) {
    setReorderingLessons(true);
    onLessonsReordered?.(withSequentialPositions(ordered));
    const result = await runAction({
      run: async () => {
        await persistSequentialPositions(ordered, (id, position) =>
          api.patch(`/tracks/lessons/${id}`, { position }),
        );
      },
      successMessage: "Ordem das aulas atualizada.",
      errorMessage: "Não foi possível reordenar as aulas.",
    });
    if (result === null) await onChanged();
    setReorderingLessons(false);
  }

  return (
    <article
      className={`structure-module${!module.is_active ? " structure-module--inactive" : ""}${open ? " structure-module--open" : ""}${sortable?.isDragging ? " structure-module--dragging" : ""}`}
      id={`module-${module.id}`}
    >
      <header className="structure-module__header">
        <div className="structure-module__toggle-row">
          {sortable && (
            <DragHandle
              dragHandle={sortable.dragHandle}
              label={`Reordenar módulo ${module.title || "sem nome"}`}
            />
          )}
          <button
            type="button"
            className="structure-module__toggle"
            onClick={onToggle}
            aria-expanded={open}
          >
            <span className="structure-module__chevron" aria-hidden />
            <span className="structure-module__badge">{module.position}</span>
            <span className="structure-module__summary">
              <span className="structure-module__name">{module.title || "Sem nome"}</span>
              <span className="structure-module__meta">
                {levelLabel(module.level)} · {lessons.length} aula{lessons.length !== 1 ? "s" : ""}
                {module.description?.trim() ? " · com descrição" : ""}
                {!module.is_active && " · desativado"}
              </span>
            </span>
          </button>
        </div>

        <div className="structure-module__toolbar">
          <button type="button" className="btn btn-ghost btn-sm" disabled={savingModule} onClick={toggleModuleActive}>
            {module.is_active ? "Desativar" : "Reativar"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm structure-module__danger" disabled={savingModule} onClick={removeModule}>
            {savingModule ? "Excluindo…" : "Excluir"}
          </button>
        </div>
      </header>

      {open && (
        <div className="structure-module__body">
          <div className="structure-module__panes" role="tablist" aria-label="Seções do módulo">
            <button
              type="button"
              role="tab"
              aria-selected={pane === "meta"}
              className={`structure-module__pane${pane === "meta" ? " structure-module__pane--active" : ""}`}
              onClick={() => setPane("meta")}
            >
              Dados
              {moduleDirty && <span className="structure-module__pane-dot" aria-label="Alterações não salvas" />}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={pane === "lessons"}
              className={`structure-module__pane${pane === "lessons" ? " structure-module__pane--active" : ""}`}
              onClick={() => setPane("lessons")}
            >
              Aulas
              {lessons.length > 0 && (
                <span className="structure-module__pane-count">{lessons.length}</span>
              )}
            </button>
          </div>

          {pane === "meta" && (
          <div className="structure-module__fields">
            <div className="field field--wide">
              <label htmlFor={`mod-title-${module.id}`}>Nome do módulo</label>
              <input
                id={`mod-title-${module.id}`}
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label>Nível</label>
              <div className="level-pills" role="group" aria-label="Nível do módulo">
                {MODULE_LEVELS.map((l) => (
                  <button
                    key={l.value}
                    type="button"
                    className={`level-pills__item${level === l.value ? " level-pills__item--active" : ""}`}
                    onClick={() => setLevel(l.value)}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="field field--wide">
              <label htmlFor={`mod-description-${module.id}`}>Descrição</label>
              <textarea
                id={`mod-description-${module.id}`}
                className="input lesson-panel__content"
                rows={6}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Material, orientações e referências deste módulo…"
              />
              <ContentSourceImport
                idPrefix={`module-description-${module.id}`}
                importUrl={`/tracks/modules/${module.id}/import-description`}
                downloadUrl={`/tracks/modules/${module.id}/description-source`}
                disabled={savingModule}
                currentContent={description}
                source={source}
                onImported={(text, nextSource) => {
                  setDescription(text);
                  setSource(nextSource);
                  void onChanged();
                }}
                fieldLabel="Preencher descrição a partir de áudio ou arquivo"
                hint="Grave ou anexe. O texto novo é acrescentado à descrição; o arquivo fonte fica o último anexado. Edite e salve o módulo se quiser ajustar."
              />
            </div>
            {moduleDirty && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={savingModule || !moduleTitleValid}
                onClick={saveModule}
              >
                {savingModule ? "Salvando…" : "Salvar módulo"}
              </button>
            )}
          </div>
          )}

          {pane === "lessons" && (
          <div className="structure-lessons">
            <div className="structure-lessons__head">
              <span className="structure-lessons__title">Aulas</span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={busyLessonId === "new"}
                onClick={addLesson}
              >
                {busyLessonId === "new" ? "Adicionando…" : "+ Aula"}
              </button>
            </div>

            {lessons.length === 0 ? (
              <p className="structure-lessons__empty muted">Nenhuma aula. Adicione a primeira na sequência.</p>
            ) : (
              <div className="structure-lessons__workspace">
                <nav className="structure-lessons__nav" aria-label="Aulas do módulo">
                  <SortableList
                    items={lessons}
                    className="structure-lessons__list"
                    onReorder={reorderLessons}
                    renderItem={(lesson, lessonSortable) => (
                      <LessonListItem
                        lesson={lesson}
                        selected={selectedLessonId === lesson.id}
                        onSelect={() => onSelectLesson(lesson.id)}
                        sortable={lessonSortable}
                        disabled={reorderingLessons}
                      />
                    )}
                  />
                </nav>

                <div className="structure-lessons__editor">
                  {selectedLesson ? (
                    <LessonEditorPanel
                      key={selectedLesson.id}
                      lesson={selectedLesson}
                      siblingLessonTitles={lessons
                        .filter((lesson) => lesson.id !== selectedLesson.id)
                        .map((lesson) => lesson.title)}
                      busy={busyLessonId === selectedLesson.id}
                      onSourceChanged={() => onChanged()}
                      onSave={async (draft) => {
                        const nextTitle = trimmed(draft.title);
                        if (!nextTitle) {
                          feedback.error("Informe o título da aula.");
                          return;
                        }
                        if (isDuplicateName(nextTitle, lessonTitles, selectedLesson.title)) {
                          feedback.error("Já existe uma aula com este título neste módulo.");
                          return;
                        }
                        setBusyLessonId(selectedLesson.id);
                        await runAction({
                          run: () =>
                            api.patch(`/tracks/lessons/${selectedLesson.id}`, {
                              ...draft,
                              title: nextTitle,
                            }),
                          successMessage: "Aula salva.",
                          errorMessage: "Não foi possível salvar a aula.",
                          onSuccess: () => onChanged(),
                        });
                        setBusyLessonId(null);
                      }}
                      onToggleActive={async () => {
                        setBusyLessonId(selectedLesson.id);
                        await runAction({
                          run: () =>
                            api.patch(`/tracks/lessons/${selectedLesson.id}`, {
                              is_active: !selectedLesson.is_active,
                            }),
                          successMessage: selectedLesson.is_active
                            ? "Aula desativada."
                            : "Aula reativada.",
                          errorMessage: "Não foi possível alterar a aula.",
                          onSuccess: () => onChanged(),
                        });
                        setBusyLessonId(null);
                      }}
                      onRemove={async () => {
                        const ok = await confirm({
                          title: "Excluir aula",
                          message: `Excluir a aula "${selectedLesson.title}"?`,
                          confirmLabel: "Excluir",
                          tone: "danger",
                        });
                        if (!ok) return;
                        setBusyLessonId(selectedLesson.id);
                        const deleted = await runAction({
                          run: () => api.delete(`/tracks/lessons/${selectedLesson.id}`),
                          successMessage: `Aula "${selectedLesson.title}" excluída.`,
                          errorMessage: "Não foi possível excluir a aula.",
                        });
                        if (deleted !== null) {
                          await runAction({
                            run: () =>
                              persistSequentialPositions(
                                lessons.filter((item) => item.id !== selectedLesson.id),
                                (id, position) => api.patch(`/tracks/lessons/${id}`, { position }),
                              ),
                            errorMessage: "Não foi possível atualizar a ordem das aulas.",
                          });
                          onSelectLesson(null);
                          await onChanged();
                        }
                        setBusyLessonId(null);
                      }}
                    />
                  ) : (
                    <div className="structure-lessons__placeholder">
                      <p>Selecione uma aula na lista</p>
                      <p className="muted">Ou clique numa etapa do percurso à direita.</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          )}
        </div>
      )}
    </article>
  );
}
