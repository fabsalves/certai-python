import { useEffect, useState } from "react";
import type { SortableRenderProps } from "../ui/SortableList";
import { DragHandle } from "../ui/DragHandle";
import type { Lesson } from "../../lib/tracks";

interface Props {
  lesson: Lesson;
  busy: boolean;
  onSave: (draft: { title: string; content: string }) => void;
  onToggleActive: () => void;
  onRemove: () => void;
}

export function LessonEditorPanel({ lesson, busy, onSave, onToggleActive, onRemove }: Props) {
  const [title, setTitle] = useState(lesson.title);
  const [content, setContent] = useState(lesson.content);
  const dirty = title !== lesson.title || content !== lesson.content;

  useEffect(() => {
    setTitle(lesson.title);
    setContent(lesson.content);
  }, [lesson.id, lesson.title, lesson.content]);

  return (
    <div className="lesson-panel" id={`lesson-${lesson.id}`}>
      <div className="lesson-panel__head">
        <span className="lesson-panel__label">Aula {lesson.position}</span>
        <div className="lesson-panel__actions">
          <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={onToggleActive}>
            {lesson.is_active ? "Desativar" : "Reativar"}
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm structure-module__danger"
            disabled={busy}
            onClick={onRemove}
          >
            Excluir
          </button>
        </div>
      </div>

      <div className="lesson-panel__fields">
        <div className="field">
          <label htmlFor={`lesson-title-${lesson.id}`}>Título</label>
          <input
            id={`lesson-title-${lesson.id}`}
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={`lesson-content-${lesson.id}`}>Conteúdo da aula</label>
          <textarea
            id={`lesson-content-${lesson.id}`}
            className="input lesson-panel__content"
            rows={8}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Material, orientações e referências que a turma verá nesta etapa…"
          />
        </div>
      </div>

      {dirty && (
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={busy}
          onClick={() => onSave({ title, content })}
        >
          {busy ? "Salvando…" : "Salvar aula"}
        </button>
      )}
    </div>
  );
}

interface ListItemProps {
  lesson: Lesson;
  selected: boolean;
  onSelect: () => void;
  sortable?: SortableRenderProps;
  disabled?: boolean;
}

export function LessonListItem({
  lesson,
  selected,
  onSelect,
  sortable,
  disabled = false,
}: ListItemProps) {
  return (
    <div
      className={`lesson-pick${selected ? " lesson-pick--selected" : ""}${!lesson.is_active ? " lesson-pick--inactive" : ""}`}
    >
      {sortable && (
        <DragHandle
          dragHandle={sortable.dragHandle}
          label={`Reordenar aula ${lesson.title || "sem título"}`}
        />
      )}
      <button
        type="button"
        className="lesson-pick__main"
        onClick={onSelect}
        disabled={disabled}
        aria-current={selected ? "true" : undefined}
      >
        <span className="lesson-pick__num">{lesson.position}</span>
        <span className="lesson-pick__title">{lesson.title || "Sem título"}</span>
      </button>
    </div>
  );
}
