import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { AccountEditModal } from "../account/AccountEditModal";
import { roleLabel, useAuth, type Role } from "../../lib/auth";
import { isNavActive, navForRole, navItemForPath } from "./nav";
import { NavIcon } from "./NavIcon";
import { OrgSwitcher } from "./OrgSwitcher";
import { ShellAccountMenu } from "./ShellAccountMenu";
import { Tooltip } from "../ui/Tooltip";

const NAV_COLLAPSED_KEY = "certai.nav.collapsed";
const MOBILE_BREAKPOINT = 860;

function NavLinks({
  items,
  pathname,
  role,
  collapsed,
  mobile,
}: {
  items: ReturnType<typeof navForRole>;
  pathname: string;
  role: Role;
  collapsed: boolean;
  mobile: boolean;
}) {
  return (
    <>
      {items.map((n) => {
        const active = isNavActive(pathname, n.to, role);
        const link = (
          <Link
            key={n.to}
            to={n.to}
            className={`shell-nav-link${active ? " shell-nav-link--active" : ""}${
              mobile ? " shell-nav-link--mobile" : ""
            }`}
            aria-current={active ? "page" : undefined}
          >
            <NavIcon icon={n.icon} />
            <span className="shell-nav-link__label">{n.label}</span>
          </Link>
        );

        if (collapsed && !mobile) {
          return (
            <Tooltip key={n.to} content={n.label}>
              {link}
            </Tooltip>
          );
        }

        return link;
      })}
    </>
  );
}

export function AppShell() {
  const { user, logout, refreshUser } = useAuth();
  const { pathname } = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(NAV_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [narrow, setNarrow] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches
      : false,
  );
  const [editOpen, setEditOpen] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
    const onChange = () => setNarrow(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(NAV_COLLAPSED_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  if (!user) return <Outlet />;

  const items = navForRole(user.role);
  const current = navItemForPath(pathname, user.role);
  const isPlayground = pathname.startsWith("/admin/playground");
  const showOrgSwitcher = user.role === "superadmin";
  const shellClass = [
    "shell",
    !narrow && collapsed ? "is-collapsed" : "",
    narrow ? "is-narrow" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={shellClass}>
      {narrow && (
        <header className="shell-mobile-bar">
          <Link to="/" className="shell-brand">
            <span className="shell-brand-text">CertAI</span>
          </Link>
          {showOrgSwitcher && <OrgSwitcher variant="bar" />}
          <ShellAccountMenu
            variant="bar"
            user={user}
            onEditAccount={() => setEditOpen(true)}
            onLogout={logout}
          />
        </header>
      )}

      {!narrow && (
        <aside className="shell-sidebar">
          <div className="shell-brand-row">
            <Link to="/" className="shell-brand">
              <span className="shell-brand-text">CertAI</span>
              <span className="shell-brand-compact" aria-hidden>
                C
              </span>
            </Link>
            {!collapsed && (
              <button
                type="button"
                className="shell-collapse shell-collapse--header btn btn-ghost btn-sm"
                onClick={() => setCollapsed(true)}
                aria-expanded
                aria-label="Recolher menu"
              >
                «
              </button>
            )}
          </div>

          <nav className="shell-nav" aria-label="Principal">
            {collapsed && (
              <button
                type="button"
                className="shell-collapse shell-collapse--nav btn btn-ghost btn-sm"
                onClick={() => setCollapsed(false)}
                aria-expanded={false}
                aria-label="Expandir menu"
              >
                »
              </button>
            )}
            {showOrgSwitcher && <OrgSwitcher variant="rail" collapsed={collapsed} />}
            <NavLinks
              items={items}
              pathname={pathname}
              role={user.role}
              collapsed={collapsed}
              mobile={false}
            />
          </nav>

          <div className="shell-nav-foot">
            <ShellAccountMenu
              variant="rail"
              user={user}
              collapsed={collapsed}
              onEditAccount={() => setEditOpen(true)}
              onLogout={logout}
            />
          </div>
        </aside>
      )}

      <div className={`shell-main${isPlayground ? " shell-main--immersive" : ""}`}>
        {!isPlayground && (
          <header className="shell-topbar">
            <div className="shell-topbar-breadcrumb">
              CertAI
              {current && (
                <>
                  <span aria-hidden>/</span>
                  <strong>{current.label}</strong>
                </>
              )}
            </div>
            <div className="shell-topbar-end">
              <span className="shell-topbar-title">{roleLabel[user.role]}</span>
            </div>
          </header>
        )}

        <div className={`shell-content${isPlayground ? " shell-content--immersive" : ""}`}>
          <Outlet />
        </div>
      </div>

      {narrow && (
        <nav className="shell-nav shell-nav--bottom" aria-label="Principal">
          <NavLinks
            items={items}
            pathname={pathname}
            role={user.role}
            collapsed={false}
            mobile
          />
        </nav>
      )}

      <AccountEditModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        userId={user.id}
        userName={user.name}
        userEmail={user.email}
        userRole={user.role}
        userWhatsapp={user.whatsapp}
        onUpdated={() => void refreshUser()}
      />
    </div>
  );
}
