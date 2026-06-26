import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { UserOption, UserCreateInput } from "../../lib/users";

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
  const [students, setStudents] = useState<UserOption[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [studentId, setStudentId] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"enroll" | "create">("enroll");

  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMode("enroll");
    setError("");
    setLoadingStudents(true);
    api
      .get<UserOption[]>("/users", { params: { role: "student" } })
      .then(({ data }) => {
        setStudents(data);
        const available = data.filter((s) => !enrolledIds.has(s.id));
        setStudentId(available[0]?.id ?? "");
      })
      .finally(() => setLoadingStudents(false));
  }, [open, enrolledIds]);

  function resetAndClose() {
    setNewName("");
    setNewEmail("");
    setNewPassword("");
    setError("");
    onClose();
  }

  const availableStudents = students.filter((s) => !enrolledIds.has(s.id));

  async function enrollExisting(e: FormEvent) {
    e.preventDefault();
    if (!studentId) return;
    setError("");
    setEnrolling(true);
    try {
      await api.post(`/cohorts/${cohortId}/enrollments`, { student_id: studentId });
      onEnrolled();
      resetAndClose();
    } catch {
      setError("Não foi possível matricular o aluno.");
    } finally {
      setEnrolling(false);
    }
  }

  async function createAndEnroll(e: FormEvent) {
    e.preventDefault();
    setError("");
    setCreating(true);
    try {
      const body: UserCreateInput = {
        email: newEmail,
        name: newName,
        password: newPassword,
        role: "student",
      };
      const { data: created } = await api.post<UserOption>("/users", body);
      await api.post(`/cohorts/${cohortId}/enrollments`, { student_id: created.id });
      onEnrolled();
      resetAndClose();
    } catch {
      setError("Não foi possível cadastrar o aluno. Verifique se o e-mail já existe.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={resetAndClose}
      title={mode === "enroll" ? "Matricular aluno" : "Cadastrar aluno"}
    >
      {mode === "enroll" ? (
        <form className="modal-form" onSubmit={enrollExisting}>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            Escolha um aluno já cadastrado no sistema.
          </p>
          <div className="field">
            <label htmlFor="enroll-student">Aluno</label>
            {loadingStudents ? (
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>Carregando…</p>
            ) : (
              <select
                id="enroll-student"
                className="input"
                value={studentId}
                onChange={(ev) => setStudentId(ev.target.value)}
                disabled={availableStudents.length === 0}
              >
                {availableStudents.length === 0 && (
                  <option value="">Nenhum aluno disponível</option>
                )}
                {availableStudents.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.email})
                  </option>
                ))}
              </select>
            )}
          </div>
          {error && <div className="form-error">{error}</div>}
          <div className="modal-form__actions">
            {canCreate && (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ marginRight: "auto" }}
                onClick={() => {
                  setMode("create");
                  setError("");
                }}
              >
                Cadastrar novo
              </button>
            )}
            <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={enrolling || !studentId}>
              {enrolling ? "Matriculando…" : "Matricular"}
            </button>
          </div>
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
          {error && <div className="form-error">{error}</div>}
          <div className="modal-form__actions">
            <button
              type="button"
              className="btn btn-ghost"
              style={{ marginRight: "auto" }}
              onClick={() => {
                setMode("enroll");
                setError("");
              }}
            >
              ← Matricular existente
            </button>
            <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={creating}>
              {creating ? "Cadastrando…" : "Cadastrar e matricular"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
