import { useMemo, useState } from "react";
import type { AdminUser, OrgListItem } from "../../lib/admin";
import { api } from "../../lib/api";
import { roleLabel, type Role } from "../../lib/auth";
import { useConfirm } from "../../lib/confirm";
import { useFeedback } from "../../lib/feedback";
import { matchesAnySearch } from "../../lib/listSearch";
import { usePagination } from "../../lib/usePagination";
import { DataTable, type DataColumn } from "../ui/DataTable";
import { FilterSegment, ListEmptyFilter, ListToolbar } from "../ui/ListToolbar";
import { Pagination } from "../ui/Pagination";
import { Select } from "../ui/Select";
import { CreateMemberModal } from "./CreateMemberModal";
import { ResetPasswordModal } from "./ResetPasswordModal";

type StatusFilter = "all" | "active" | "inactive";

interface Props {
  members: AdminUser[];
  showOrg?: boolean;
  orgs?: OrgListItem[];
  orgFilter?: string;
  onOrgFilterChange?: (orgId: string) => void;
  createPath?: string;
  defaultRole?: Role;
  createOpen: boolean;
  onCreateOpenChange: (open: boolean) => void;
  memberPath: (member: AdminUser) => string;
  passwordPath: (member: AdminUser) => string;
  currentUserId?: string;
  onChanged: () => void;
}

const STATUS_OPTIONS: Array<{ value: StatusFilter; label: string }> = [
  { value: "all", label: "Todos" },
  { value: "active", label: "Ativos" },
  { value: "inactive", label: "Inativos" },
];

export function MembersTable({
  members,
  showOrg = false,
  orgs,
  orgFilter = "",
  onOrgFilterChange,
  createPath,
  defaultRole = "org_admin",
  createOpen,
  onCreateOpenChange,
  memberPath,
  passwordPath,
  currentUserId,
  onChanged,
}: Props) {
  const confirm = useConfirm();
  const feedback = useFeedback();
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const roleOptions = useMemo(() => {
    const roles = new Set(members.map((member) => member.role));
    return [
      { value: "", label: "Todos os papéis" },
      ...[...roles].map((role) => ({
        value: role,
        label: roleLabel[role as Role] ?? role,
      })),
    ];
  }, [members]);

  const orgOptions = useMemo(
    () => [
      { value: "", label: "Todas as organizações" },
      ...(orgs ?? []).map((org) => ({ value: org.id, label: org.name })),
    ],
    [orgs],
  );

  const filtered = useMemo(
    () =>
      members.filter((member) => {
        if (orgFilter && member.organization_id !== orgFilter) return false;
        if (roleFilter && member.role !== roleFilter) return false;
        if (statusFilter === "active" && !member.is_active) return false;
        if (statusFilter === "inactive" && member.is_active) return false;
        return matchesAnySearch(search, [
          member.name,
          member.email,
          member.organization_name,
          roleLabel[member.role as Role],
        ]);
      }),
    [members, orgFilter, roleFilter, search, statusFilter],
  );

  const paging = usePagination(filtered, {
    resetKey: `${search}|${orgFilter}|${roleFilter}|${statusFilter}`,
  });

  async function toggleActive(member: AdminUser) {
    const next = !member.is_active;
    const ok = await confirm({
      title: next ? "Reativar conta" : "Desativar conta",
      message: next
        ? `Reativar ${member.name}?`
        : `Desativar ${member.name}? O histórico é mantido; a pessoa deixa de entrar.`,
      confirmLabel: next ? "Reativar" : "Desativar",
      tone: next ? "default" : "danger",
    });
    if (!ok) return;
    try {
      await api.patch(memberPath(member), {
        name: member.name,
        email: member.email,
        whatsapp: member.whatsapp,
        is_active: next,
      });
      feedback.success(next ? `${member.name} reativado(a).` : `${member.name} desativado(a).`);
      onChanged();
    } catch {
      feedback.error("Não foi possível atualizar o status.");
    }
  }

  const columns: DataColumn<AdminUser>[] = [
    {
      id: "name",
      header: "Nome",
      primary: true,
      render: (member) => <span className="table__primary">{member.name}</span>,
    },
    { id: "email", header: "E-mail", render: (member) => member.email },
    {
      id: "role",
      header: "Papel",
      render: (member) => roleLabel[member.role as Role] ?? member.role,
    },
    {
      id: "status",
      header: "Status",
      render: (member) =>
        member.is_active ? (
          <span className="tag tag--brand">Ativo</span>
        ) : (
          <span className="tag tag--inactive">Inativo</span>
        ),
    },
  ];
  if (showOrg) {
    columns.push({
      id: "org",
      header: "Organização",
      render: (member) => member.organization_name || "—",
    });
  }
  columns.push({
    id: "actions",
    header: "",
    card: "actions",
    align: "end",
    render: (member) => {
      const isSelf = member.id === currentUserId;
      const isSuperadmin = member.role === "superadmin";
      return (
        <div className="table__actions">
          {!isSuperadmin && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setResetTarget(member)}
            >
              Atualizar senha
            </button>
          )}
          {!isSuperadmin && !isSelf && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => void toggleActive(member)}
            >
              {member.is_active ? "Desativar" : "Reativar"}
            </button>
          )}
        </div>
      );
    },
  });

  const hasCatalog = members.length > 0;
  const hasResults = filtered.length > 0;

  return (
    <>
      {hasCatalog && (
        <ListToolbar
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder="Buscar por nome ou e-mail"
          searchLabel="Buscar membros"
        >
          {showOrg && onOrgFilterChange && (
            <Select
              id="members-org-filter"
              className="list-toolbar__ui-select"
              value={orgFilter}
              onChange={onOrgFilterChange}
              options={orgOptions}
              aria-label="Filtrar por organização"
            />
          )}
          <Select
            id="members-role-filter"
            className="list-toolbar__ui-select"
            value={roleFilter}
            onChange={setRoleFilter}
            options={roleOptions}
            aria-label="Filtrar por papel"
          />
          <FilterSegment
            value={statusFilter}
            options={STATUS_OPTIONS}
            onChange={setStatusFilter}
            aria-label="Filtrar por status"
          />
        </ListToolbar>
      )}

      {!hasCatalog && (
        <div className="card empty-state">
          <p>Nenhum membro cadastrado.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            Crie o primeiro acesso para esta organização.
          </p>
        </div>
      )}

      {hasCatalog && !hasResults && <ListEmptyFilter />}

      {hasResults && (
        <>
          <DataTable columns={columns} rows={paging.items} rowKey={(member) => member.id} aria-label="Membros" />
          <Pagination
            page={paging.page}
            totalPages={paging.totalPages}
            total={paging.total}
            from={paging.from}
            to={paging.to}
            onPageChange={paging.setPage}
          />
        </>
      )}

      {createPath && (
        <CreateMemberModal
          open={createOpen}
          createPath={createPath}
          defaultRole={defaultRole}
          onClose={() => onCreateOpenChange(false)}
          onCreated={() => onChanged()}
        />
      )}
      {resetTarget && (
        <ResetPasswordModal
          open
          memberName={resetTarget.name}
          passwordPath={passwordPath(resetTarget)}
          onClose={() => setResetTarget(null)}
          onSaved={() => {
            setResetTarget(null);
            onChanged();
          }}
        />
      )}
    </>
  );
}
