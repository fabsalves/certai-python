import { useEffect, useMemo, useState } from "react";
import { Modal } from "../ui/Modal";

export interface UnassignedStudentOption {
  student_id: string;
  student_name: string;
  student_email: string;
}

interface Props {
  open: boolean;
  moduleTitle: string;
  students: UnassignedStudentOption[];
  busy: boolean;
  onClose: () => void;
  onConfirm: (studentIds: string[]) => void;
}

export function ClaimUnassignedStudentsModal({
  open,
  moduleTitle,
  students,
  busy,
  onClose,
  onConfirm,
}: Props) {
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setSelectedIds(new Set());
  }, [open, students]);

  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filtered = useMemo(() => {
    if (!normalizedQuery) return students;
    return students.filter(
      (student) =>
        student.student_name.toLocaleLowerCase().includes(normalizedQuery) ||
        student.student_email.toLocaleLowerCase().includes(normalizedQuery),
    );
  }, [students, normalizedQuery]);

  const selectedCount = selectedIds.size;
  const allFilteredSelected =
    filtered.length > 0 && filtered.every((s) => selectedIds.has(s.student_id));

  function toggleStudent(studentId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(studentId)) next.delete(studentId);
      else next.add(studentId);
      return next;
    });
  }

  function toggleAllFiltered() {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (allFilteredSelected) {
        for (const student of filtered) next.delete(student.student_id);
      } else {
        for (const student of filtered) next.add(student.student_id);
      }
      return next;
    });
  }

  function handleClose() {
    if (busy) return;
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={`Alunos sem turma · ${moduleTitle}`}
      wide
    >
      <div className="modal-form">
        <div className="modal-form__body">
          <div className="modal-form__content">
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Selecione os alunos para adicionar à sua turma. O progresso será
              alinhado às aulas já encerradas neste módulo.
            </p>

            {students.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                Nenhum aluno sem turma neste módulo.
              </p>
            ) : (
              <>
                <div className="field">
                  <label htmlFor="claim-unassigned-search">Buscar</label>
                  <input
                    id="claim-unassigned-search"
                    className="input"
                    type="search"
                    value={query}
                    onChange={(ev) => setQuery(ev.target.value)}
                    placeholder="Nome ou e-mail…"
                    disabled={busy}
                  />
                </div>

                <div className="enroll-picker">
                  <div className="enroll-picker__toolbar">
                    <span className="enroll-picker__count">
                      {selectedCount} selecionado(s) · {students.length} sem turma
                    </span>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={toggleAllFiltered}
                      disabled={busy || filtered.length === 0}
                    >
                      {allFilteredSelected ? "Limpar filtro" : "Selecionar filtrados"}
                    </button>
                  </div>

                  <ul className="enroll-picker__list">
                    {filtered.length === 0 ? (
                      <li className="enroll-picker__empty muted">
                        Nenhum aluno encontrado.
                      </li>
                    ) : (
                      filtered.map((student) => {
                        const checked = selectedIds.has(student.student_id);
                        return (
                          <li key={student.student_id}>
                            <label
                              className={`enroll-picker__item${checked ? " is-selected" : ""}`}
                            >
                              <input
                                type="checkbox"
                                className="enroll-picker__check"
                                checked={checked}
                                disabled={busy}
                                onChange={() => toggleStudent(student.student_id)}
                              />
                              <span className="enroll-picker__item-main">
                                <span className="enroll-picker__name">
                                  {student.student_name}
                                </span>
                                <span className="muted enroll-picker__email">
                                  {student.student_email}
                                </span>
                              </span>
                            </label>
                          </li>
                        );
                      })
                    )}
                  </ul>
                </div>
              </>
            )}
          </div>
        </div>

        <footer className="modal-form__footer">
          <div className="modal-form__actions">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={handleClose}
              disabled={busy}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy || students.length === 0}
              onClick={() => onConfirm(students.map((s) => s.student_id))}
            >
              Adicionar todos
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || selectedCount === 0}
              onClick={() => onConfirm([...selectedIds])}
            >
              {busy
                ? "Vinculando…"
                : selectedCount > 1
                  ? `Adicionar ${selectedCount}`
                  : "Adicionar selecionados"}
            </button>
          </div>
        </footer>
      </div>
    </Modal>
  );
}
