import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { UserUpdateInput } from "../../lib/users";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import { isNonEmpty, normalizedEmail, trimmed } from "../../lib/validation";

interface Props {
  open: boolean;
  onClose: () => void;
  userId: string;
  userName: string;
  userEmail: string;
  onUpdated: () => void;
}

export function ProfileEditModal({
  open,
  onClose,
  userId,
  userName,
  userEmail,
  onUpdated,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(userName);
    setEmail(userEmail);
  }, [open, userName, userEmail]);

  function resetAndClose() {
    onClose();
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const nextName = trimmed(name);
    if (!nextName) {
      feedback.error("Informe seu nome.");
      return;
    }

    setSaving(true);
    await runAction({
      run: () => {
        const body: UserUpdateInput = {
          name: nextName,
          email: normalizedEmail(email),
        };
        return api.patch(`/users/${userId}`, body);
      },
      successMessage: "Perfil atualizado.",
      errorMessage: "Não foi possível salvar. Verifique se o e-mail já existe.",
      onSuccess: () => {
        onUpdated();
        resetAndClose();
      },
    });
    setSaving(false);
  }

  const ready = isNonEmpty(name) && isNonEmpty(email);

  return (
    <Modal open={open} onClose={resetAndClose} title="Editar perfil">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <div className="field">
              <label htmlFor="profile-name">Nome</label>
              <input
                id="profile-name"
                className="input"
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="profile-email">E-mail</label>
              <input
                id="profile-email"
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
