import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { Enrollment, ModuleClassDraft, ProfessorOption } from "../../lib/cohorts";
import {
  copyDivisionFromPrevious,
  moveStudentsToProfessor,
  splitEvenly,
  unassignedStudentIds,
} from "../../lib/cohorts";
import { Modal } from "../ui/Modal";

type ColumnKey = "unassigned" | string; // professorId

interface Props {
  open: boolean;
  moduleTitle: string;
  classes: ModuleClassDraft[];
  enrollments: Enrollment[];
  professors: ProfessorOption[];
  previousClasses: ModuleClassDraft[];
  /** When true, confirm persists to the server; otherwise only drafts locally. */
  persist?: boolean;
  busy?: boolean;
  onClose: () => void;
  onApply: (classes: ModuleClassDraft[]) => void | Promise<void>;
}

function professorName(
  professors: ProfessorOption[],
  professorId: string,
): string {
  return professors.find((item) => item.id === professorId)?.name ?? "Professor";
}

export function ModuleClassDivisionModal({
  open,
  moduleTitle,
  classes,
  enrollments,
  professors,
  previousClasses,
  persist = false,
  busy = false,
  onClose,
  onApply,
}: Props) {
  const [draft, setDraft] = useState<ModuleClassDraft[]>(classes);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [applying, setApplying] = useState(false);
  const locked = busy || applying;

  useEffect(() => {
    if (!open) return;
    setDraft(classes.map((item) => ({ ...item, studentIds: [...item.studentIds] })));
    setSelected(new Set());
    setQuery("");
  }, [open, classes]);

  const enrolledIds = useMemo(
    () => enrollments.map((item) => item.student_id),
    [enrollments],
  );
  const byId = useMemo(
    () => new Map(enrollments.map((item) => [item.student_id, item])),
    [enrollments],
  );
  const pending = unassignedStudentIds(draft, enrolledIds);
  const normalizedQuery = query.trim().toLocaleLowerCase();

  const columns = useMemo(() => {
    const list: { key: ColumnKey; title: string; studentIds: string[] }[] = [
      { key: "unassigned", title: "Sem grupo", studentIds: pending },
    ];
    for (const item of draft) {
      if (!item.professorId) continue;
      list.push({
        key: item.professorId,
        title: professorName(professors, item.professorId),
        studentIds: item.studentIds,
      });
    }
    return list;
  }, [draft, pending, professors]);

  function visibleIds(ids: string[]): string[] {
    if (!normalizedQuery) return ids;
    return ids.filter((id) => {
      const enrollment = byId.get(id);
      if (!enrollment) return false;
      return (
        enrollment.student_name.toLocaleLowerCase().includes(normalizedQuery) ||
        enrollment.student_email.toLocaleLowerCase().includes(normalizedQuery)
      );
    });
  }

  function toggle(studentId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(studentId)) next.delete(studentId);
      else next.add(studentId);
      return next;
    });
  }

  function toggleColumn(studentIds: string[]) {
    const visible = visibleIds(studentIds);
    setSelected((current) => {
      const next = new Set(current);
      const allSelected = visible.every((id) => next.has(id));
      for (const id of visible) {
        if (allSelected) next.delete(id);
        else next.add(id);
      }
      return next;
    });
  }

  function moveSelected(toProfessorId: string | null) {
    if (selected.size === 0) return;
    setDraft((current) =>
      moveStudentsToProfessor(current, [...selected], toProfessorId),
    );
    setSelected(new Set());
  }

  function applyEvenSplit() {
    setDraft(splitEvenly(draft, enrolledIds));
    setSelected(new Set());
  }

  function applyCopyPrevious() {
    setDraft(copyDivisionFromPrevious(draft, previousClasses, enrolledIds));
    setSelected(new Set());
  }

  function applyAllUnassignedTo(professorId: string) {
    if (pending.length === 0) return;
    setDraft((current) => moveStudentsToProfessor(current, pending, professorId));
    setSelected(new Set());
  }

  async function confirm() {
    if (locked) return;
    setApplying(true);
    try {
      await onApply(draft);
    } finally {
      setApplying(false);
    }
  }

  const canCopyPrevious =
    previousClasses.length > 1 &&
    previousClasses.some((item) => item.studentIds.length > 0);

  return (
    <Modal
      open={open}
      onClose={locked ? () => undefined : onClose}
      title={`Dividir alunos · ${moduleTitle}`}
      wide
      className="modal--division"
    >
      <div className="module-division modal-form">
        <div className="modal-form__body module-division__body">
          <p className="muted module-division__hint">
            Selecione vários alunos e mova para um professor. Alunos sem grupo
            bloqueiam o encerramento das aulas deste módulo.
            {persist
              ? " Ao salvar, a divisão fica valendo na turma."
              : " A divisão será gravada ao criar a turma."}
          </p>

          <div className="module-division__toolbar">
            <label className="field module-division__search">
              <input
                className="input"
                type="search"
                placeholder="Buscar por nome ou e-mail…"
                aria-label="Buscar aluno"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <div className="module-division__bulk">
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={applyEvenSplit}
                disabled={enrollments.length === 0}
              >
                Dividir igualmente
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={applyCopyPrevious}
                disabled={!canCopyPrevious}
                title={
                  canCopyPrevious
                    ? "Usa a divisão do módulo anterior quando o professor coincidir"
                    : "Não há divisão no módulo anterior"
                }
              >
                Copiar módulo anterior
              </button>
            </div>
          </div>

          <div className="module-division__move">
            <span className="muted">
              {selected.size > 0
                ? `${selected.size} selecionado(s)`
                : "Nenhum selecionado"}
            </span>
            <div className="module-division__move-actions">
              {draft
                .filter((item) => item.professorId)
                .map((item) => (
                  <button
                    key={item.professorId}
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={selected.size === 0}
                    onClick={() => moveSelected(item.professorId)}
                  >
                    → {professorName(professors, item.professorId)}
                  </button>
                ))}
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={selected.size === 0}
                onClick={() => moveSelected(null)}
              >
                → Sem grupo
              </button>
            </div>
          </div>

          {pending.length > 0 && draft.some((item) => item.professorId) && (
            <div className="module-division__unassigned-actions">
              <span className="muted">{pending.length} sem grupo</span>
              {draft
                .filter((item) => item.professorId)
                .map((item) => (
                  <button
                    key={item.professorId}
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => applyAllUnassignedTo(item.professorId)}
                  >
                    Todos → {professorName(professors, item.professorId)}
                  </button>
                ))}
            </div>
          )}

          <div
            className="module-division__columns"
            style={{ "--division-cols": columns.length } as CSSProperties}
          >
            {columns.map((column) => {
              const visible = visibleIds(column.studentIds);
              const allSelected =
                visible.length > 0 && visible.every((id) => selected.has(id));

              return (
                <section key={column.key} className="module-division__column">
                  <header className="module-division__column-head">
                    <div>
                      <strong>{column.title}</strong>
                      <span className="muted"> {column.studentIds.length}</span>
                    </div>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={visible.length === 0}
                      onClick={() => toggleColumn(column.studentIds)}
                    >
                      {allSelected ? "Limpar" : "Todos"}
                    </button>
                  </header>
                  <ul className="module-division__list">
                    {visible.length === 0 ? (
                      <li className="muted module-division__empty">
                        {column.studentIds.length === 0
                          ? "Nenhum aluno"
                          : "Nenhum resultado"}
                      </li>
                    ) : (
                      visible.map((studentId) => {
                        const enrollment = byId.get(studentId);
                        if (!enrollment) return null;
                        return (
                          <li key={studentId}>
                            <label className="module-division__row">
                              <input
                                type="checkbox"
                                checked={selected.has(studentId)}
                                onChange={() => toggle(studentId)}
                              />
                              <span>
                                <span className="module-division__name">
                                  {enrollment.student_name}
                                </span>
                                <span className="muted module-division__email">
                                  {enrollment.student_email}
                                </span>
                              </span>
                            </label>
                          </li>
                        );
                      })
                    )}
                  </ul>
                </section>
              );
            })}
          </div>
        </div>

        <div className="modal-form__footer">
          <div className="modal-form__actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={onClose}
              disabled={locked}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={confirm}
              disabled={locked}
            >
              {applying
                ? "Salvando…"
                : persist
                  ? "Salvar divisão"
                  : "Aplicar divisão"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
