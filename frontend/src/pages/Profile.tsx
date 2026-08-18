import { useState } from "react";
import { useAuth } from "../lib/auth";
import { ProfileEditModal } from "../components/profile/ProfileEditModal";
import { PageHeader } from "../components/layout/PageHeader";

export function Profile() {
  const { user, refreshUser } = useAuth();
  const [editOpen, setEditOpen] = useState(false);

  if (!user) return null;

  return (
    <>
      <PageHeader
        title="Meu perfil"
        description="Seu nome e e-mail usados na plataforma."
      />

      <div className="card professors-list__item" style={{ maxWidth: 480 }}>
        <div>
          <div className="professors-list__name">{user.name}</div>
          <div className="muted professors-list__email">{user.email}</div>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm professors-list__edit"
          onClick={() => setEditOpen(true)}
        >
          Editar
        </button>
      </div>

      <ProfileEditModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        userId={user.id}
        userName={user.name}
        userEmail={user.email}
        onUpdated={() => void refreshUser()}
      />
    </>
  );
}
