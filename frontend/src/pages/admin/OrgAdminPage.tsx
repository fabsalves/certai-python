import { useCallback, useEffect, useState } from "react";
import { AdminPageSkeleton } from "../../components/admin/AdminPageSkeleton";
import { IntegrationsForm } from "../../components/admin/IntegrationsForm";
import { MembersTable } from "../../components/admin/MembersTable";
import { PageHeader } from "../../components/layout/PageHeader";
import type { AdminUser, OrgSettings } from "../../lib/admin";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

type Tab = "members" | "integrations";

export function OrgAdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("members");
  const [members, setMembers] = useState<AdminUser[]>([]);
  const [settings, setSettings] = useState<OrgSettings | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadMembers = useCallback(async () => {
    try {
      const { data } = await api.get<AdminUser[]>("/users");
      setMembers(data);
    } catch {
      setMembers([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      loadMembers(),
      api.get<OrgSettings>("/settings").then(({ data }) => {
        if (!cancelled) setSettings(data);
      }),
    ])
      .catch(() => {
        if (!cancelled) setSettings(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadMembers]);

  if (loading) {
    return (
      <AdminPageSkeleton
        title="Administração"
        description="Membros desta organização e chaves de integração."
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Administração"
        description="Membros desta organização e chaves de integração."
        actions={
          tab === "members" ? (
            <button type="button" className="btn btn-primary" onClick={() => setCreateOpen(true)}>
              Novo membro
            </button>
          ) : undefined
        }
      />

      <div className="editor-tabs__bar" style={{ marginBottom: 16, borderRadius: 12, overflow: "hidden" }}>
        <button type="button" className={`editor-tabs__tab${tab === "members" ? " editor-tabs__tab--active" : ""}`} onClick={() => setTab("members")}>
          Membros
        </button>
        <button
          type="button"
          className={`editor-tabs__tab${tab === "integrations" ? " editor-tabs__tab--active" : ""}`}
          onClick={() => setTab("integrations")}
        >
          Integrações
        </button>
      </div>

      {tab === "members" && (
        <MembersTable
          members={members}
          createPath="/users"
          defaultRole="professor"
          createOpen={createOpen}
          onCreateOpenChange={setCreateOpen}
          memberPath={(member) => `/users/${member.id}`}
          passwordPath={(member) => `/users/${member.id}/password`}
          currentUserId={user?.id}
          onChanged={() => void loadMembers()}
        />
      )}
      {tab === "integrations" && settings && (
        <IntegrationsForm settings={settings} settingsPath="/settings" onSaved={setSettings} />
      )}
    </>
  );
}
