import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { UserOption, UserCreateInput } from "../../lib/users";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import { isNonEmpty, normalizedEmail, trimmed } from "../../lib/validation";

interface Props {
  open: boolean;
  onClose: () => void;
  cohortId: string;
  enrolledIds: Set<string>;
  canCreate: boolean;
  onEnrolled: () => void;
}

export function StudentEnrollModal({
  open,
  onClose,
  cohortId,
  enrolledIds,
  canCreate,
  onEnrolled,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const [students, setStudents] = useState<UserOption[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [mode, setMode] = useState<"enroll" | "create">("enroll");

  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMode("enroll");
    setQuery("");
    setSelectedIds(new Set());
    setLoadingStudents(true);
    api
      .get<UserOption[]>("/users", { params: { role: "student" } })
      .then(({ data }) => setStudents(data))
      .finally(() => setLoadingStudents(false));
  }, [open, enrolledIds]);

  function resetAndClose() {
    setNewName("");
    setNewEmail("");
    setNewPassword("");
    setQuery("");
    setSelectedIds(new Set());
    onClose();
  }

  const availableStudents = useMemo(
    () =>
      students
        .filter((s) => !enrolledIds.has(s.id))
        .sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
    [students, enrolledIds],
  );

  const filteredStudents = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? availableStudents.filter(
          (s) => s.name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q),
        )
      : availableStudents;
    return list;
  }, [availableStudents, query]);

  const allFilteredSelected =
    filteredStudents.length > 0 &&
    filteredStudents.every((s) => selectedIds.has(s.id));

  function toggleStudent(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllFiltered() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        filteredStudents.forEach((s) => next.delete(s.id));
      } else {
        filteredStudents.forEach((s) => next.add(s.id));
      }
      return next;
    });
  }

  async function enrollSelected(e: FormEvent) {
    e.preventDefault();
    const ids = [...selectedIds];
    if (ids.length === 0) return;

    setEnrolling(true);
    await runAction({
      run: () => api.post(`/cohorts/${cohortId}/enrollments/bulk`, { student_ids: ids }),
      successMessage:
        ids.length > 1 ? `${ids.length} alunos matriculados.` : "Aluno matriculado.",
      errorMessage: "Não foi possível matricular os alunos selecionados.",
      onSuccess: () => {
        onEnrolled();
        resetAndClose();
      },
    });
    setEnrolling(false);
  }

  async function createAndEnroll(e: FormEvent) {
    e.preventDefault();
    const nextName = trimmed(newName);
    if (!nextName) {
      feedback.error("Informe o nome do aluno.");
      return;
    }
    setCreating(true);
    await runAction({
      run: async () => {
        const body: UserCreateInput = {
          email: normalizedEmail(newEmail),
          name: nextName,
          password: newPassword,
          role: "student",
        };
        const { data: created } = await api.post<UserOption>("/users", body);
        await api.post(`/cohorts/${cohortId}/enrollments`, { student_id: created.id });
        return created;
      },
      successMessage: `${nextName} cadastrado(a) e matriculado(a).`,
      errorMessage: "Não foi possível cadastrar o aluno. Verifique se o e-mail já existe.",
      onSuccess: () => {
        onEnrolled();
        resetAndClose();
      },
    });
    setCreating(false);
  }

  const selectedCount = selectedIds.size;

  return (
    <Modal
      open={open}
      onClose={resetAndClose}
      title={mode === "enroll" ? "Matricular alunos" : "Cadastrar aluno"}
    >
      {mode === "enroll" ? (
        <form className="modal-form" onSubmit={enrollSelected}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            Selecione um ou mais alunos já cadastrados no sistema.
          </p>

          {loadingStudents ? (
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Carregando…
            </p>
          ) : availableStudents.length === 0 ? (
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Nenhum aluno disponível para matricular.
            </p>
          ) : (
            <>
              <div className="field">
                <label htmlFor="enroll-search">Buscar</label>
                <input
                  id="enroll-search"
                  className="input"
                  value={query}
                  onChange={(ev) => setQuery(ev.target.value)}
                  placeholder="Nome ou e-mail…"
                />
              </div>

              <div className="enroll-picker">
                <div className="enroll-picker__toolbar">
                  <span className="enroll-picker__count">
                    {selectedCount} selecionado(s)
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={toggleAllFiltered}
                    disabled={filteredStudents.length === 0}
                  >
                    {allFilteredSelected ? "Limpar filtro" : "Selecionar filtrados"}
                  </button>
                </div>

                <ul className="enroll-picker__list">
                  {filteredStudents.length === 0 ? (
                    <li className="enroll-picker__empty muted">Nenhum aluno encontrado.</li>
                  ) : (
                    filteredStudents.map((student) => {
                      const checked = selectedIds.has(student.id);
                      return (
                        <li key={student.id}>
                          <label className={`enroll-picker__item${checked ? " is-selected" : ""}`}>
                            <input
                              type="checkbox"
                              className="enroll-picker__check"
                              checked={checked}
                              onChange={() => toggleStudent(student.id)}
                            />
                            <span className="enroll-picker__item-main">
                              <span className="enroll-picker__name">{student.name}</span>
                              <span className="muted enroll-picker__email">{student.email}</span>
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

          <footer className="modal-form__footer">
            {canCreate && (
              <button type="button" className="modal-form__back" onClick={() => setMode("create")}>
                + Cadastrar novo aluno
              </button>
            )}
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={enrolling || selectedCount === 0}
              >
                {enrolling
                  ? "Matriculando…"
                  : selectedCount > 1
                    ? `Matricular (${selectedCount})`
                    : "Matricular"}
              </button>
            </div>
          </footer>
        </form>
      ) : (
        <form className="modal-form" onSubmit={createAndEnroll}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            Cria a conta e matricula automaticamente nesta turma.
          </p>
          <div className="field">
            <label htmlFor="student-name">Nome</label>
            <input
              id="student-name"
              className="input"
              value={newName}
              onChange={(ev) => setNewName(ev.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="student-email">E-mail</label>
            <input
              id="student-email"
              type="email"
              className="input"
              value={newEmail}
              onChange={(ev) => setNewEmail(ev.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="student-password">Senha inicial</label>
            <input
              id="student-password"
              type="password"
              className="input"
              minLength={8}
              value={newPassword}
              onChange={(ev) => setNewPassword(ev.target.value)}
              required
            />
          </div>
          <footer className="modal-form__footer">
            <button type="button" className="modal-form__back" onClick={() => setMode("enroll")}>
              ← Alunos existentes
            </button>
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={creating || !isNonEmpty(newName)}>
                {creating ? "Cadastrando…" : "Cadastrar"}
              </button>
            </div>
          </footer>
        </form>
      )}
    </Modal>
  );
}
