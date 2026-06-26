import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { persistSequentialPositions } from "../../lib/reorder";
import { DragHandle } from "../ui/DragHandle";
import { SortableList, type SortableRenderProps } from "../ui/SortableList";
import { LessonEditorPanel, LessonListItem } from "./LessonEditor";
import {
  MODULE_LEVELS,
  levelLabel,
  nextLessonPosition,
  sortedLessons,
  type Lesson,
  type Module,
  type ModuleLevel,
} from "../../lib/tracks";

interface Props {
  module: Module;
  open: boolean;
  onToggle: () => void;
  selectedLessonId: string | null;
  onSelectLesson: (lessonId: string | null) => void;
  onChanged: () => void;
  sortable?: SortableRenderProps;
}

export function ModuleEditor({
  module,
  open,
  onToggle,
  selectedLessonId,
  onSelectLesson,
  onChanged,
  sortable,
}: Props) {
  const lessons = sortedLessons(module);
  const selectedLesson = lessons.find((l) => l.id === selectedLessonId) ?? null;
  const [title, setTitle] = useState(module.title);
  const [level, setLevel] = useState<ModuleLevel>(module.level);
  const [savingModule, setSavingModule] = useState(false);
  const [busyLessonId, setBusyLessonId] = useState<string | null>(null);
  const [reorderingLessons, setReorderingLessons] = useState(false);

  const moduleDirty = title !== module.title || level !== module.level;

  useEffect(() => {
    setTitle(module.title);
    setLevel(module.level);
  }, [module.id, module.title, module.level]);

  async function saveModule() {
    setSavingModule(true);
    try {
      await api.patch(`/tracks/modules/${module.id}`, { title, level });
      onChanged();
    } finally {
      setSavingModule(false);
    }
  }

  async function toggleModuleActive() {
    setSavingModule(true);
    try {
      await api.patch(`/tracks/modules/${module.id}`, { is_active: !module.is_active });
      onChanged();
    } finally {
      setSavingModule(false);
    }
  }

  async function removeModule() {
    if (!confirm(`Excluir o módulo "${module.title}" e todas as aulas?`)) return;
    await api.delete(`/tracks/modules/${module.id}`);
    onChanged();
  }

  async function addLesson() {
    setBusyLessonId("new");
    try {
      const { data } = await api.post<Lesson>(`/tracks/modules/${module.id}/lessons`, {
        title: `Aula ${nextLessonPosition(module)}`,
        content: "",
        position: nextLessonPosition(module),
      });
      onChanged();
      onSelectLesson(data.id);
    } finally {
      setBusyLessonId(null);
    }
  }

  async function reorderLessons(ordered: Lesson[]) {
    setReorderingLessons(true);
    try {
      await persistSequentialPositions(ordered, (id, position) =>
        api.patch(`/tracks/lessons/${id}`, { position }),
      );
      onChanged();
    } finally {
      setReorderingLessons(false);
    }
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
                {!module.is_active && " · desativado"}
              </span>
            </span>
          </button>
        </div>

        <div className="structure-module__toolbar">
          <button type="button" className="btn btn-ghost btn-sm" disabled={savingModule} onClick={toggleModuleActive}>
            {module.is_active ? "Desativar" : "Reativar"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm structure-module__danger" onClick={removeModule}>
            Excluir
          </button>
        </div>
      </header>

      {open && (
        <div className="structure-module__body">
          <div className="structure-module__fields">
            <div className="field">
              <label htmlFor={`mod-title-${module.id}`}>Nome do módulo</label>
              <input
                id={`mod-title-${module.id}`}
                className="input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
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
            {moduleDirty && (
              <button type="button" className="btn btn-primary btn-sm" disabled={savingModule} onClick={saveModule}>
                {savingModule ? "Salvando…" : "Salvar módulo"}
              </button>
            )}
          </div>

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
                      busy={busyLessonId === selectedLesson.id}
                      onSave={async (draft) => {
                        setBusyLessonId(selectedLesson.id);
                        try {
                          await api.patch(`/tracks/lessons/${selectedLesson.id}`, draft);
                          onChanged();
                        } finally {
                          setBusyLessonId(null);
                        }
                      }}
                      onToggleActive={async () => {
                        setBusyLessonId(selectedLesson.id);
                        try {
                          await api.patch(`/tracks/lessons/${selectedLesson.id}`, {
                            is_active: !selectedLesson.is_active,
                          });
                          onChanged();
                        } finally {
                          setBusyLessonId(null);
                        }
                      }}
                      onRemove={async () => {
                        if (!confirm(`Excluir a aula "${selectedLesson.title}"?`)) return;
                        setBusyLessonId(selectedLesson.id);
                        try {
                          await api.delete(`/tracks/lessons/${selectedLesson.id}`);
                          onSelectLesson(null);
                          onChanged();
                        } finally {
                          setBusyLessonId(null);
                        }
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
        </div>
      )}
    </article>
  );
}
