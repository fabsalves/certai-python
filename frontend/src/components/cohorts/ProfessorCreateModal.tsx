import { type FormEvent, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { UserOption, UserCreateInput } from "../../lib/users";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import { isNonEmpty, normalizedEmail, trimmed } from "../../lib/validation";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (professor: UserOption) => void;
}

export function ProfessorCreateModal({ open, onClose, onCreated }: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);

  function resetAndClose() {
    setName("");
    setEmail("");
    setPassword("");
    onClose();
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const nextName = trimmed(name);
    if (!nextName) {
      feedback.error("Informe o nome do professor.");
      return;
    }
    setSaving(true);
    await runAction({
      run: () => {
        const body: UserCreateInput = { email: normalizedEmail(email), name: nextName, password, role: "professor" };
        return api.post<UserOption>("/users", body);
      },
      successMessage: `${nextName} cadastrado(a) como professor.`,
      errorMessage: "Não foi possível cadastrar. Verifique se o e-mail já existe.",
      onSuccess: ({ data }) => {
        onCreated(data);
        resetAndClose();
      },
    });
    setSaving(false);
  }

  return (
    <Modal open={open} onClose={resetAndClose} title="Novo professor">
      <form className="modal-form" onSubmit={onSubmit}>
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>
          Cria a conta de professor para atribuir à turma.
        </p>
        <div className="field">
          <label htmlFor="prof-name">Nome</label>
          <input
            id="prof-name"
            className="input"
            value={name}
            onChange={(ev) => setName(ev.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="prof-email">E-mail</label>
          <input
            id="prof-email"
            type="email"
            className="input"
            value={email}
            onChange={(ev) => setEmail(ev.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="prof-password">Senha inicial</label>
          <input
            id="prof-password"
            type="password"
            className="input"
            minLength={8}
            value={password}
            onChange={(ev) => setPassword(ev.target.value)}
            required
          />
        </div>
        <div className="modal-form__actions">
          <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving || !isNonEmpty(name)}>
            {saving ? "Cadastrando…" : "Cadastrar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
