import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { AdminPageSkeleton } from "../../components/admin/AdminPageSkeleton";
import { IntegrationsForm } from "../../components/admin/IntegrationsForm";
import { MembersTable } from "../../components/admin/MembersTable";
import { PageHeader } from "../../components/layout/PageHeader";
import type { AdminUser, OrgDetail } from "../../lib/admin";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

type Tab = "members" | "integrations";

export function OrgDetailPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("members");
  const [org, setOrg] = useState<OrgDetail | null>(null);
  const [members, setMembers] = useState<AdminUser[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadMembers = useCallback(async () => {
    if (!orgId) return;
    try {
      const { data } = await api.get<AdminUser[]>(`/admin/orgs/${orgId}/users`);
      setMembers(data);
    } catch {
      setMembers([]);
    }
  }, [orgId]);

  useEffect(() => {
    if (!orgId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      api.get<OrgDetail>(`/admin/orgs/${orgId}`).then(({ data }) => {
        if (!cancelled) setOrg(data);
      }),
      loadMembers(),
    ])
      .catch(() => {
        if (!cancelled) setOrg(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [orgId, loadMembers]);

  if (loading) {
    return (
      <AdminPageSkeleton
        title="Organização"
        description="Membros e chaves desta organização."
      />
    );
  }

  if (!org || !orgId) {
    return <p className="muted">Organização não encontrada.</p>;
  }

  return (
    <>
      <PageHeader
        title={org.name}
        description={`Slug ${org.slug}. Membros e chaves desta organização.`}
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
          createPath={`/admin/orgs/${orgId}/users`}
          defaultRole="org_admin"
          createOpen={createOpen}
          onCreateOpenChange={setCreateOpen}
          memberPath={(member) => `/admin/orgs/${orgId}/users/${member.id}`}
          passwordPath={(member) => `/admin/orgs/${orgId}/users/${member.id}/password`}
          currentUserId={user?.id}
          onChanged={() => void loadMembers()}
        />
      )}
      {tab === "integrations" && (
        <IntegrationsForm
          settings={org.settings}
          settingsPath={`/admin/orgs/${org.id}/settings`}
          onSaved={(settings) => setOrg({ ...org, settings })}
        />
      )}
    </>
  );
}
