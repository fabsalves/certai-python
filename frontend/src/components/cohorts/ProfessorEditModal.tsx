import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { UserOption, UserUpdateInput } from "../../lib/users";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import { isNonEmpty, normalizedEmail, trimmed } from "../../lib/validation";

interface Props {
  open: boolean;
  onClose: () => void;
  professorId: string;
  professorName: string;
  professorEmail: string;
  onUpdated: (professor: UserOption) => void;
}

export function ProfessorEditModal({
  open,
  onClose,
  professorId,
  professorName,
  professorEmail,
  onUpdated,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(professorName);
    setEmail(professorEmail);
  }, [open, professorName, professorEmail]);

  function resetAndClose() {
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
        const body: UserUpdateInput = {
          name: nextName,
          email: normalizedEmail(email),
        };
        return api.patch<UserOption>(`/users/${professorId}`, body);
      },
      successMessage: "Dados do professor atualizados.",
      errorMessage: "Não foi possível salvar. Verifique se o e-mail já existe.",
      onSuccess: ({ data }) => {
        onUpdated(data);
        resetAndClose();
      },
    });
    setSaving(false);
  }

  const ready = isNonEmpty(name) && isNonEmpty(email);

  return (
    <Modal open={open} onClose={resetAndClose} title="Editar professor">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <div className="field">
              <label htmlFor="edit-prof-name">Nome</label>
              <input
                id="edit-prof-name"
                className="input"
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="edit-prof-email">E-mail</label>
              <input
                id="edit-prof-email"
                type="email"
                className="input"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                required
              />
            </div>
          </div>
          <div className="modal-form__footer">
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving || !ready}>
                {saving ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}
