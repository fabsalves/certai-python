import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { UserCreated, UserCreateInput, UserOption } from "../../lib/users";
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
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState<UserCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (open) return;
    setName("");
    setEmail("");
    setCreated(null);
    setCopied(false);
    setShowPassword(false);
  }, [open]);

  function resetAndClose() {
    setName("");
    setEmail("");
    setCreated(null);
    setCopied(false);
    setShowPassword(false);
    onClose();
  }

  async function copyPassword() {
    const password = created?.initial_password;
    if (!password) return;
    try {
      await navigator.clipboard.writeText(password);
      setCopied(true);
    } catch {
      feedback.error("Não foi possível copiar. Selecione a senha e copie manualmente.");
    }
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
        const body: UserCreateInput = {
          email: normalizedEmail(email),
          name: nextName,
          role: "professor",
        };
        return api.post<UserCreated>("/users", body);
      },
      successMessage: `${nextName} cadastrado(a) como professor.`,
      errorMessage: "Não foi possível cadastrar. Verifique se o e-mail já existe.",
      onSuccess: ({ data }) => {
        onCreated(data);
        setCreated(data);
      },
    });
    setSaving(false);
  }

  if (created) {
    return (
      <Modal open={open} onClose={resetAndClose} title="Senha do professor">
        <div className="modal-form">
          <div className="modal-form__body">
            <div className="modal-form__content">
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                Copie agora. Essa senha não aparece de novo.
              </p>
              <div className="field">
                <label htmlFor="prof-created-email">E-mail</label>
                <input
                  id="prof-created-email"
                  className="input"
                  value={created.email}
                  readOnly
                />
              </div>
              <div className="field">
                <label htmlFor="prof-created-password">Senha</label>
                <div className="password-field">
                  <input
                    id="prof-created-password"
                    className="input"
                    type={showPassword ? "text" : "password"}
                    value={created.initial_password ?? ""}
                    readOnly
                  />
                  <button
                    type="button"
                    className="password-field__toggle"
                    onClick={() => setShowPassword((current) => !current)}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  >
                    {showPassword ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
                        <path d="M3 3l18 18M10.58 10.58a2 2 0 0 0 2.84 2.84M9.88 5.09A10.94 10.94 0 0 1 12 5c7 0 10 7 10 7a18.45 18.45 0 0 1-2.16 3.19M6.12 6.12A18.5 18.5 0 0 0 2 12s3 7 10 7a10.8 10.8 0 0 0 5.12-1.28" strokeLinecap="round" />
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
                        <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              <div className="modal-form__actions">
                <button type="button" className="btn btn-ghost" onClick={() => void copyPassword()}>
                  {copied ? "Copiada" : "Copiar senha"}
                </button>
                <button type="button" className="btn btn-primary" onClick={resetAndClose}>
                  Pronto
                </button>
              </div>
            </div>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal open={open} onClose={resetAndClose} title="Novo professor">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Nome e e-mail. A senha aparece uma vez depois de cadastrar.
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
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving || !isNonEmpty(name)}>
                {saving ? "Cadastrando…" : "Cadastrar"}
              </button>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}
