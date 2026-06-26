import { type FormEvent, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { UserOption, UserCreateInput } from "../../lib/users";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (professor: UserOption) => void;
}

export function ProfessorCreateModal({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function resetAndClose() {
    setName("");
    setEmail("");
    setPassword("");
    setError("");
    onClose();
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body: UserCreateInput = { email, name, password, role: "professor" };
      const { data } = await api.post<UserOption>("/users", body);
      onCreated(data);
      resetAndClose();
    } catch {
      setError("Não foi possível cadastrar. Verifique se o e-mail já existe.");
    } finally {
      setSaving(false);
    }
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
        {error && <div className="form-error">{error}</div>}
        <div className="modal-form__actions">
          <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? "Cadastrando…" : "Cadastrar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
