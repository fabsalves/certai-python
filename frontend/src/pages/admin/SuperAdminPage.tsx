import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AdminPageSkeleton } from "../../components/admin/AdminPageSkeleton";
import { MembersTable } from "../../components/admin/MembersTable";
import { CreateOrgModal } from "../../components/admin/CreateOrgModal";
import { PageHeader } from "../../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../../components/ui/DataTable";
import { FilterSegment, ListEmptyFilter, ListToolbar } from "../../components/ui/ListToolbar";
import { Pagination } from "../../components/ui/Pagination";
import type { AdminUser, OrgListItem } from "../../lib/admin";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { matchesAnySearch } from "../../lib/listSearch";
import { useOrg } from "../../lib/orgContext";
import { usePagination } from "../../lib/usePagination";

type Tab = "orgs" | "users";
type StatusFilter = "all" | "active" | "inactive";

const ORG_STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "active", label: "Ativas" },
  { value: "inactive", label: "Inativas" },
];

export function SuperAdminPage() {
  const { user } = useAuth();
  const { refreshOrgs } = useOrg();
  const [tab, setTab] = useState<Tab>("orgs");
  const [orgs, setOrgs] = useState<OrgListItem[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [orgFilter, setOrgFilter] = useState("");
  const [orgSearch, setOrgSearch] = useState("");
  const [orgStatus, setOrgStatus] = useState<StatusFilter>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [createUserOpen, setCreateUserOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadOrgs = useCallback(async () => {
    try {
      const { data } = await api.get<OrgListItem[]>("/admin/orgs");
      setOrgs(data);
    } catch {
      setOrgs([]);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      const { data } = await api.get<AdminUser[]>("/admin/users");
      setUsers(data);
    } catch {
      setUsers([]);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadOrgs(), loadUsers()]).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [loadOrgs, loadUsers]);

  const filteredOrgs = useMemo(
    () =>
      orgs.filter((org) => {
        if (orgStatus === "active" && !org.is_active) return false;
        if (orgStatus === "inactive" && org.is_active) return false;
        return matchesAnySearch(orgSearch, [org.name, org.slug]);
      }),
    [orgs, orgSearch, orgStatus],
  );

  const orgPaging = usePagination(filteredOrgs, { resetKey: `${orgSearch}|${orgStatus}` });

  const orgColumns = useMemo<DataColumn<OrgListItem>[]>(
    () => [
      {
        id: "name",
        header: "Organização",
        primary: true,
        render: (org) => <span className="table__primary">{org.name}</span>,
      },
      { id: "slug", header: "Slug", render: (org) => org.slug },
      { id: "members", header: "Membros", render: (org) => String(org.user_count) },
      {
        id: "status",
        header: "Status",
        render: (org) => (org.is_active ? "Ativa" : "Inativa"),
      },
      {
        id: "actions",
        header: "",
        card: "actions",
        align: "end",
        render: (org) => (
          <Link className="btn btn-ghost btn-sm" to={`/admin/orgs/${org.id}`}>
            Gerenciar
          </Link>
        ),
      },
    ],
    [],
  );

  const createPath = orgFilter ? `/admin/orgs/${orgFilter}/users` : undefined;
  const hasOrgCatalog = orgs.length > 0;
  const hasOrgResults = filteredOrgs.length > 0;

  if (loading) {
    return (
      <AdminPageSkeleton
        title="Plataforma"
        description="Organizações e usuários da plataforma."
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Plataforma"
        description="Organizações e usuários da plataforma."
        actions={
          tab === "orgs" ? (
            <button type="button" className="btn btn-primary" onClick={() => setCreateOpen(true)}>
              Nova organização
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setCreateUserOpen(true)}
              disabled={!orgFilter}
            >
              Novo membro
            </button>
          )
        }
      />

      <div className="editor-tabs__bar" style={{ marginBottom: 16, borderRadius: 12, overflow: "hidden" }}>
        <button type="button" className={`editor-tabs__tab${tab === "orgs" ? " editor-tabs__tab--active" : ""}`} onClick={() => setTab("orgs")}>
          Organizações
        </button>
        <button type="button" className={`editor-tabs__tab${tab === "users" ? " editor-tabs__tab--active" : ""}`} onClick={() => setTab("users")}>
          Usuários
        </button>
      </div>

      {tab === "orgs" && (
        <>
          {hasOrgCatalog && (
            <ListToolbar
              search={orgSearch}
              onSearchChange={setOrgSearch}
              searchPlaceholder="Buscar por nome ou slug"
              searchLabel="Buscar organizações"
            >
              <FilterSegment
                value={orgStatus}
                options={ORG_STATUS_OPTIONS}
                onChange={setOrgStatus}
                aria-label="Filtrar por status"
              />
            </ListToolbar>
          )}
          {!hasOrgCatalog && (
            <div className="card empty-state">
              <p>Nenhuma organização ainda.</p>
              <p className="muted" style={{ marginTop: 6 }}>
                Crie a primeira organização para provisionar acessos.
              </p>
            </div>
          )}
          {hasOrgCatalog && !hasOrgResults && <ListEmptyFilter />}
          {hasOrgResults && (
            <>
              <DataTable columns={orgColumns} rows={orgPaging.items} rowKey={(org) => org.id} aria-label="Organizações" />
              <Pagination
                page={orgPaging.page}
                totalPages={orgPaging.totalPages}
                total={orgPaging.total}
                from={orgPaging.from}
                to={orgPaging.to}
                onPageChange={orgPaging.setPage}
              />
            </>
          )}
        </>
      )}

      {tab === "users" && (
        <>
          {!orgFilter && (
            <p className="muted" style={{ marginBottom: 12, fontSize: 13 }}>
              Selecione uma organização para cadastrar um membro.
            </p>
          )}
          <MembersTable
            members={users}
            showOrg
            orgs={orgs}
            orgFilter={orgFilter}
            onOrgFilterChange={setOrgFilter}
            createPath={createPath}
            defaultRole="org_admin"
            createOpen={createUserOpen}
            onCreateOpenChange={setCreateUserOpen}
            memberPath={(member) =>
              member.organization_id
                ? `/admin/orgs/${member.organization_id}/users/${member.id}`
                : `/users/${member.id}`
            }
            passwordPath={(member) =>
              member.organization_id
                ? `/admin/orgs/${member.organization_id}/users/${member.id}/password`
                : `/users/${member.id}/password`
            }
            currentUserId={user?.id}
            onChanged={() => {
              void loadUsers();
              loadOrgs();
            }}
          />
        </>
      )}

      <CreateOrgModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSaved={() => {
          void loadOrgs();
          refreshOrgs();
        }}
      />
    </>
  );
}
