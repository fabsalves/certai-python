import { type FormEvent, useEffect, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import type { OrgDetail, OrgListItem } from "../../lib/admin";
import { useApiAction } from "../../lib/useApiAction";
import { isNonEmpty, trimmed } from "../../lib/validation";

function slugify(value: string): string {
  const folded = value.normalize("NFKD").replace(/\p{M}/gu, "");
  const slug = folded.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "org";
  return slug.slice(0, 80).replace(/-+$/g, "") || "org";
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: (org: OrgDetail) => void;
  org?: Pick<OrgListItem, "id" | "name" | "slug"> | null;
}

export function CreateOrgModal({ open, onClose, onSaved, org = null }: Props) {
  const runAction = useApiAction();
  const editing = Boolean(org);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(org?.name ?? "");
    setSlug(org?.slug ?? "");
    setSlugTouched(Boolean(org));
  }, [open, org]);

  function resetAndClose() {
    setName("");
    setSlug("");
    setSlugTouched(false);
    onClose();
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const nextName = trimmed(name);
    const nextSlug = trimmed(slug);
    if (!nextName) return;
    setSaving(true);
    await runAction({
      run: () =>
        editing && org
          ? api.patch<OrgDetail>(`/admin/orgs/${org.id}`, { name: nextName })
          : api.post<OrgDetail>("/admin/orgs", {
              name: nextName,
              slug: nextSlug || undefined,
            }),
      successMessage: editing ? `Organização ${nextName} atualizada.` : `Organização ${nextName} criada.`,
      errorMessage: editing
        ? "Não foi possível atualizar a organização."
        : "Não foi possível criar a organização.",
      onSuccess: ({ data }) => {
        onSaved(data);
        resetAndClose();
      },
    });
    setSaving(false);
  }

  return (
    <Modal open={open} onClose={resetAndClose} title={editing ? "Editar organização" : "Nova organização"}>
      <form className="modal-form" onSubmit={onSubmit}>
        <div className="modal-form__body">
          <div className="modal-form__content">
            <div className="field">
              <label htmlFor="org-name">Nome</label>
              <input
                id="org-name"
                className="input"
                value={name}
                onChange={(ev) => {
                  const next = ev.target.value;
                  setName(next);
                  if (!editing && !slugTouched) setSlug(slugify(next));
                }}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="org-slug">Slug</label>
              <input
                id="org-slug"
                className="input"
                value={slug}
                readOnly={editing}
                onChange={(ev) => {
                  if (editing) return;
                  setSlugTouched(true);
                  setSlug(ev.target.value);
                }}
                placeholder="gerado a partir do nome"
              />
              <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
                {editing
                  ? "Definido na criação. Entra na URL do webhook do Cinndi."
                  : "Letras minúsculas e hífen. Depois da criação não muda mais."}
              </p>
            </div>
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={saving || !isNonEmpty(name)}>
                {saving ? (editing ? "Salvando…" : "Criando…") : editing ? "Salvar" : "Criar"}
              </button>
            </div>
          </div>
        </div>
      </form>
    </Modal>
  );
}
