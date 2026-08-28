import { type FormEvent, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { OrgDetail } from "../../lib/admin";
import { useApiAction } from "../../lib/useApiAction";
import { isNonEmpty, trimmed } from "../../lib/validation";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (org: OrgDetail) => void;
}

export function CreateOrgModal({ open, onClose, onCreated }: Props) {
  const runAction = useApiAction();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [saving, setSaving] = useState(false);

  function resetAndClose() {
    setName("");
    setSlug("");
    onClose();
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const nextName = trimmed(name);
    if (!nextName) return;
    setSaving(true);
    await runAction({
      run: () =>
        api.post<OrgDetail>("/admin/orgs", {
          name: nextName,
          slug: trimmed(slug) || undefined,
        }),
      successMessage: `Organização ${nextName} criada.`,
      errorMessage: "Não foi possível criar a organização.",
      onSuccess: ({ data }) => {
        onCreated(data);
        resetAndClose();
      },
    });
    setSaving(false);
  }

  return (
    <Modal open={open} onClose={resetAndClose} title="Nova organização">
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <div className="field">
              <label htmlFor="org-name">Nome</label>
              <input
                id="org-name"
                className="input"
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="org-slug">Slug (opcional)</label>
              <input
                id="org-slug"
                className="input"
                value={slug}
                onChange={(ev) => setSlug(ev.target.value)}
                placeholder="gerado a partir do nome"
              />
            </div>
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving || !isNonEmpty(name)}>
                {saving ? "Criando…" : "Criar"}
              </button>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}
