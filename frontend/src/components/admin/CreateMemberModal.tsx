import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { WhatsAppField } from "../ui/WhatsAppField";
import { api } from "../../lib/api";
import { roleLabel, type Role } from "../../lib/auth";
import type { UserCreated, UserCreateInput } from "../../lib/users";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import { isNonEmpty, isValidWhatsapp, normalizedEmail, normalizePhoneForApi, trimmed } from "../../lib/validation";
import { DEFAULT_DIAL_CODE } from "../../lib/phoneCountries";

const ASSIGNABLE: Role[] = ["org_admin", "professor", "student"];

interface Props {
  open: boolean;
  onClose: () => void;
  createPath: string;
  defaultRole?: Role;
  onCreated: (user: UserCreated) => void;
}

export function CreateMemberModal({
  open,
  onClose,
  createPath,
  defaultRole = "org_admin",
  onCreated,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>(defaultRole);
  const [whatsapp, setWhatsapp] = useState("");
  const [whatsappDial, setWhatsappDial] = useState(DEFAULT_DIAL_CODE);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState<UserCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (open) return;
    setName("");
    setEmail("");
    setRole(defaultRole);
    setWhatsapp("");
    setWhatsappDial(DEFAULT_DIAL_CODE);
    setCreated(null);
    setCopied(false);
    setShowPassword(false);
  }, [open, defaultRole]);

  function resetAndClose() {
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
      feedback.error("Informe o nome.");
      return;
    }
    if (role === "student" && !isValidWhatsapp(whatsappDial, whatsapp)) {
      feedback.error("Informe um WhatsApp válido para o aluno.");
      return;
    }
    setSaving(true);
    await runAction({
      run: () => {
        const body: UserCreateInput = {
          email: normalizedEmail(email),
          name: nextName,
          role,
        };
        if (role === "student") {
          body.whatsapp = normalizePhoneForApi(whatsappDial, whatsapp);
        }
        return api.post<UserCreated>(createPath, body);
      },
      successMessage: `${nextName} cadastrado(a).`,
      errorMessage: "Não foi possível cadastrar. Verifique se o e-mail ou WhatsApp já existe.",
      onSuccess: ({ data }) => {
        onCreated(data);
        setCreated(data);
      },
    });
    setSaving(false);
  }

  if (created?.initial_password) {
    return (
      <Modal open={open} onClose={resetAndClose} title="Senha gerada">
        <div className="modal-form">
          <div className="modal-form__body">
            <div className="modal-form__content">
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                Copie agora. Essa senha não aparece de novo.
              </p>
              <div className="field">
                <label htmlFor="member-created-email">E-mail</label>
                <input id="member-created-email" className="input" value={created.email} readOnly />
              </div>
              <div className="field">
                <label htmlFor="member-created-password">Senha</label>
                <div className="password-field password-field--with-label">
                  <input
                    id="member-created-password"
                    className="input"
                    type={showPassword ? "text" : "password"}
                    value={created.initial_password}
                    readOnly
                  />
                  <button
                    type="button"
                    className="password-field__toggle"
                    onClick={() => setShowPassword((current) => !current)}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  >
                    {showPassword ? "Ocultar" : "Mostrar"}
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

  if (created) {
    return (
      <Modal open={open} onClose={resetAndClose} title="Aluno cadastrado">
        <div className="modal-form">
          <div className="modal-form__body">
            <div className="modal-form__content">
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                O acesso do aluno é o WhatsApp. Não há senha para copiar.
              </p>
              <div className="modal-form__actions">
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
    <Modal open={open} onClose={resetAndClose} title="Novo membro">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Staff recebe senha gerada uma vez. Aluno entra pelo WhatsApp.
            </p>
            <div className="field">
              <label htmlFor="member-name">Nome</label>
              <input
                id="member-name"
                className="input"
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="member-email">E-mail</label>
              <input
                id="member-email"
                type="email"
                className="input"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="member-role">Papel</label>
              <select
                id="member-role"
                className="input"
                value={role}
                onChange={(ev) => setRole(ev.target.value as Role)}
              >
                {ASSIGNABLE.map((value) => (
                  <option key={value} value={value}>
                    {roleLabel[value]}
                  </option>
                ))}
              </select>
            </div>
            {role === "student" && (
              <div className="field">
                <label htmlFor="member-whatsapp">WhatsApp</label>
                <WhatsAppField
                  id="member-whatsapp"
                  dialCode={whatsappDial}
                  national={whatsapp}
                  onDialCodeChange={setWhatsappDial}
                  onNationalChange={setWhatsapp}
                  required
                />
              </div>
            )}
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
