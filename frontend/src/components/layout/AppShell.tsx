import { Outlet, Link, useLocation } from "react-router-dom";
import { roleLabel, useAuth } from "../../lib/auth";
import { navForRole, navItemForPath } from "./nav";
import { NavIcon } from "./NavIcon";

function initials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

export function AppShell() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();

  if (!user) return <Outlet />;

  const items = navForRole(user.role);
  const current = navItemForPath(pathname, user.role);
  const isPlayground = pathname.startsWith("/admin/playground");

  return (
    <div className="shell">
      <aside className="shell-sidebar">
        <div className="shell-brand">
          <span className="shell-brand-text">CertAI</span>
        </div>

        <nav className="shell-nav" aria-label="Principal">
          {items.map((n) => {
            const active = n.to === "/" ? pathname === "/" : pathname.startsWith(n.to);
            return (
              <Link
                key={n.to}
                to={n.to}
                className={`shell-nav-link${active ? " shell-nav-link--active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <NavIcon icon={n.icon} />
                {n.label}
              </Link>
            );
          })}
        </nav>

        <div className="shell-user">
          <div className="shell-user-info">
            <span className="shell-user-avatar" aria-hidden>
              {initials(user.name)}
            </span>
            <div style={{ minWidth: 0 }}>
              <div className="shell-user-name">{user.name}</div>
              <div className="shell-user-role">{roleLabel[user.role]}</div>
            </div>
          </div>
          <button type="button" className="btn btn-ghost shell-logout" onClick={logout}>
            Sair
          </button>
        </div>
      </aside>

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
            <span className="shell-topbar-title">{roleLabel[user.role]}</span>
          </header>
        )}

        <div className={`shell-content${isPlayground ? " shell-content--immersive" : ""}`}>
          <Outlet />
        </div>
      </div>
    </div>
  );
}
