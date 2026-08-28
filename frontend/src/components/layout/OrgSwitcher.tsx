import type { ReactNode } from "react";
import { useAuth } from "../../lib/auth";
import { useOrg } from "../../lib/orgContext";
import { Select } from "../ui/Select";
import { Tooltip } from "../ui/Tooltip";

interface Props {
  variant?: "rail" | "bar" | "page";
  collapsed?: boolean;
}

function BuildingIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <path d="M3 21h18" />
      <path d="M5 21V8l7-4 7 4v13" />
      <path d="M9 21v-6h6v6" />
      <path d="M9 10h2" />
      <path d="M13 10h2" />
      <path d="M9 14h2" />
      <path d="M13 14h2" />
    </svg>
  );
}

export function OrgSwitcher({ variant = "rail", collapsed = false }: Props) {
  const { orgs, orgsLoading, selectedOrgId, setSelectedOrgId } = useOrg();
  const selected = orgs.find((org) => org.id === selectedOrgId);
  const options = orgs.map((org) => ({
    value: org.id,
    label: org.name,
    description: org.slug,
  }));
  const placeholder = orgsLoading ? "Carregando…" : "Selecionar organização";
  const sidebar = variant !== "page";

  const select = (
    <Select
      id={`org-switcher-${variant}`}
      label={variant === "page" ? "Organização" : undefined}
      aria-label={variant === "page" ? undefined : "Organização"}
      variant={sidebar ? "sidebar" : "default"}
      icon={sidebar ? <BuildingIcon /> : undefined}
      value={selectedOrgId ?? ""}
      placeholder={placeholder}
      options={options}
      disabled={orgsLoading || orgs.length === 0}
      onChange={(value) => setSelectedOrgId(value || null)}
    />
  );

  if (variant === "page") {
    return <div className="org-switcher org-switcher--page">{select}</div>;
  }

  const body = (
    <div className={`shell-org shell-org--${variant}${collapsed ? " is-collapsed" : ""}`}>
      {variant === "rail" && !collapsed && (
        <span className="shell-org__label">Organização</span>
      )}
      {select}
    </div>
  );

  if (collapsed && variant === "rail") {
    return <Tooltip content={selected?.name ?? "Selecionar organização"}>{body}</Tooltip>;
  }

  return body;
}

export function OrgLensGate({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { hasOrgLens, orgs, orgsLoading } = useOrg();
  if (user?.role === "superadmin" && !hasOrgLens) {
    return (
      <div className="card empty-state">
        <p>Selecione a organização para ver custos e o playground.</p>
        {orgsLoading ? (
          <p className="muted" style={{ marginTop: 8 }}>
            Carregando organizações…
          </p>
        ) : orgs.length === 0 ? (
          <p className="muted" style={{ marginTop: 8 }}>
            Nenhuma organização cadastrada.
          </p>
        ) : (
          <OrgSwitcher variant="page" />
        )}
      </div>
    );
  }
  return <>{children}</>;
}
