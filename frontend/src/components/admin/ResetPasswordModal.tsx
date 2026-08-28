import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import {
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  PASSWORD_RULES_HINT,
  validateNewPassword,
} from "../../lib/password";

interface Props {
  open: boolean;
  memberName: string;
  passwordPath: string;
  onClose: () => void;
  onSaved: () => void;
}

export function ResetPasswordModal({
  open,
  memberName,
  passwordPath,
  onClose,
  onSaved,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) return;
    setPassword("");
    setConfirm("");
  }, [open]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const error = validateNewPassword(password);
    if (error) {
      feedback.error(error);
      return;
    }
    if (password !== confirm) {
      feedback.error("As senhas não coincidem.");
      return;
    }
    setSaving(true);
    await runAction({
      run: () => api.patch(passwordPath, { password }),
      successMessage: `Senha de ${memberName} atualizada. Sessões anteriores foram encerradas.`,
      errorMessage: "Não foi possível redefinir a senha.",
      onSuccess: () => {
        onSaved();
        onClose();
      },
    });
    setSaving(false);
  }

  return (
    <Modal open={open} onClose={onClose} title="Redefinir senha">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Nova senha para {memberName}. {PASSWORD_RULES_HINT}
            </p>
            <div className="field">
              <label htmlFor="reset-password">Nova senha</label>
              <input
                id="reset-password"
                className="input"
                type="password"
                value={password}
                onChange={(ev) => setPassword(ev.target.value)}
                minLength={MIN_PASSWORD_LENGTH}
                maxLength={MAX_PASSWORD_LENGTH}
                autoComplete="new-password"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="reset-password-confirm">Confirmar senha</label>
              <input
                id="reset-password-confirm"
                className="input"
                type="password"
                value={confirm}
                onChange={(ev) => setConfirm(ev.target.value)}
                minLength={MIN_PASSWORD_LENGTH}
                maxLength={MAX_PASSWORD_LENGTH}
                autoComplete="new-password"
                required
              />
            </div>
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? "Salvando…" : "Redefinir"}
              </button>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}
