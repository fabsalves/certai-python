import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { WhatsAppField } from "../ui/WhatsAppField";
import { api } from "../../lib/api";
import { DEFAULT_DIAL_CODE } from "../../lib/phoneCountries";
import type { UserOption, UserUpdateInput } from "../../lib/users";
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
  studentId: string;
  studentName: string;
  studentEmail: string;
  studentWhatsapp?: string | null;
  onUpdated: (student: UserOption) => void;
}

export function StudentEditModal({
  open,
  onClose,
  studentId,
  studentName,
  studentEmail,
  studentWhatsapp,
  onUpdated,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [whatsappDialCode, setWhatsappDialCode] = useState(DEFAULT_DIAL_CODE);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const parsed = parsePhoneParts(studentWhatsapp ?? "");
    setName(studentName);
    setEmail(studentEmail);
    setWhatsappDialCode(parsed.dialCode);
    setWhatsapp(
      studentWhatsapp ? maskNationalNumber(parsed.dialCode, parsed.national) : "",
    );
  }, [open, studentName, studentEmail, studentWhatsapp]);

  function resetAndClose() {
    onClose();
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const nextName = trimmed(name);
    if (!nextName) {
      feedback.error("Informe o nome do aluno.");
      return;
    }
    const nextWhatsapp = normalizePhoneForApi(whatsappDialCode, whatsapp);
    if (!nextWhatsapp || !isValidWhatsapp(whatsappDialCode, whatsapp)) {
      feedback.error("Informe um WhatsApp válido.");
      return;
    }

    setSaving(true);
    await runAction({
      run: () => {
        const body: UserUpdateInput = {
          name: nextName,
          email: normalizedEmail(email),
          whatsapp: nextWhatsapp,
        };
        return api.patch<UserOption>(`/users/${studentId}`, body);
      },
      successMessage: "Dados do aluno atualizados.",
      errorMessage: "Não foi possível salvar. Verifique e-mail ou WhatsApp duplicados.",
      onSuccess: ({ data }) => {
        onUpdated(data);
        resetAndClose();
      },
    });
    setSaving(false);
  }

  const ready =
    isNonEmpty(name) &&
    isNonEmpty(email) &&
    isValidWhatsapp(whatsappDialCode, whatsapp);

  return (
    <Modal open={open} onClose={resetAndClose} title="Editar aluno">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <div className="field">
              <label htmlFor="edit-student-name">Nome</label>
              <input
                id="edit-student-name"
                className="input"
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="edit-student-email">E-mail</label>
              <input
                id="edit-student-email"
                type="email"
                className="input"
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="edit-student-whatsapp">WhatsApp</label>
              <WhatsAppField
                id="edit-student-whatsapp"
                dialCode={whatsappDialCode}
                national={whatsapp}
                onDialCodeChange={setWhatsappDialCode}
                onNationalChange={setWhatsapp}
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
