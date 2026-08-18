import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { WhatsAppField } from "../ui/WhatsAppField";
import { api } from "../../lib/api";
import type { Role } from "../../lib/auth";
import type { UserUpdateInput } from "../../lib/users";
import { DEFAULT_DIAL_CODE } from "../../lib/phoneCountries";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import {
  isNonEmpty,
  isValidWhatsapp,
  maskNationalNumber,
  normalizedEmail,
  normalizePhoneForApi,
  parsePhoneParts,
  trimmed,
} from "../../lib/validation";

interface Props {
  open: boolean;
  onClose: () => void;
  userId: string;
  userName: string;
  userEmail: string;
  userRole: Role;
  userWhatsapp?: string | null;
  onUpdated: () => void;
}

export function AccountEditModal({
  open,
  onClose,
  userId,
  userName,
  userEmail,
  userRole,
  userWhatsapp,
  onUpdated,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const isStudent = userRole === "student";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [whatsappDialCode, setWhatsappDialCode] = useState(DEFAULT_DIAL_CODE);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const parsed = parsePhoneParts(userWhatsapp ?? "");
    setName(userName);
    setEmail(userEmail);
    setWhatsappDialCode(parsed.dialCode);
    setWhatsapp(
      userWhatsapp ? maskNationalNumber(parsed.dialCode, parsed.national) : "",
    );
  }, [open, userName, userEmail, userWhatsapp]);

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

    let nextWhatsapp: string | undefined;
    if (isStudent) {
      nextWhatsapp = normalizePhoneForApi(whatsappDialCode, whatsapp);
      if (!nextWhatsapp || !isValidWhatsapp(whatsappDialCode, whatsapp)) {
        feedback.error("Informe um WhatsApp válido.");
        return;
      }
    }

    setSaving(true);
    await runAction({
      run: () => {
        const body: UserUpdateInput = {
          name: nextName,
          email: normalizedEmail(email),
          whatsapp: nextWhatsapp,
        };
        return api.patch(`/users/${userId}`, body);
      },
      successMessage: "Conta atualizada.",
      errorMessage: "Não foi possível salvar. Verifique e-mail ou WhatsApp duplicados.",
      onSuccess: () => {
        onUpdated();
        resetAndClose();
      },
    });
    setSaving(false);
  }

  const ready =
    isNonEmpty(name) &&
    isNonEmpty(email) &&
    (!isStudent || isValidWhatsapp(whatsappDialCode, whatsapp));

  return (
    <Modal open={open} onClose={resetAndClose} title="Editar conta">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <div className="field">
              <label htmlFor="account-name">Nome</label>
              <input
                id="account-name"
                className="input"
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="account-email">E-mail</label>
              <input
                id="account-email"
                type="email"
                className="input"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                required
              />
            </div>
            {isStudent && (
              <div className="field">
                <label htmlFor="account-whatsapp">WhatsApp</label>
                <WhatsAppField
                  id="account-whatsapp"
                  dialCode={whatsappDialCode}
                  national={whatsapp}
                  onDialCodeChange={setWhatsappDialCode}
                  onNationalChange={setWhatsapp}
                  required
                />
              </div>
            )}
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
