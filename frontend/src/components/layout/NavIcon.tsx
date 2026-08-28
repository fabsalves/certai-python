import type { ReactNode } from "react";
import type { NavItem } from "./nav";

/** Ícones stroke simples — sem fill decorativo. */
const icons: Record<NavItem["icon"], ReactNode> = {
  overview: (
    <>
      <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-9.5Z" />
      <path d="M9 21V12h6v9" />
    </>
  ),
  tracks: (
    <>
      <path d="M4 7h16" />
      <path d="M4 12h10" />
      <path d="M4 17h14" />
    </>
  ),
  cohorts: (
    <>
      <path d="M16 19a4 4 0 0 0-8 0" />
      <circle cx="12" cy="9" r="3" />
    </>
  ),
  professors: (
    <>
      <path d="M12 12a4 4 0 1 0-4-4" />
      <path d="M6 20v-1a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v1" />
      <path d="M16 3.5a3 3 0 1 1 0 5" />
      <path d="M21 20v-1a3 3 0 0 0-2-2.8" />
    </>
  ),
  learn: (
    <>
      <path d="M4 6.5 12 3l8 3.5v11L12 21 4 17.5V6.5Z" />
      <path d="M12 10.5V21" />
    </>
  ),
  costs: (
    <>
      <path d="M4 20V10" />
      <path d="M10 20V5" />
      <path d="M16 20v-7" />
      <path d="M3 20h18" />
    </>
  ),
  playground: (
    <>
      <path d="M12 3v4" />
      <path d="M8 7h8" />
      <rect x="5" y="9" width="14" height="12" rx="2" />
      <path d="M9 14h.01" />
      <path d="M12 14h.01" />
      <path d="M15 14h.01" />
    </>
  ),
  admin: (
    <>
      <path d="M3 21h18" />
      <path d="M5 21V8l7-4 7 4v13" />
      <path d="M9 21v-6h6v6" />
      <path d="M9 10h2" />
      <path d="M13 10h2" />
      <path d="M9 14h2" />
      <path d="M13 14h2" />
    </>
  ),
  settings: (
    <>
      <path d="M4 7h16" />
      <path d="M4 12h16" />
      <path d="M4 17h16" />
      <circle cx="9" cy="7" r="1.75" />
      <circle cx="15" cy="12" r="1.75" />
      <circle cx="11" cy="17" r="1.75" />
    </>
  ),
};

export function NavIcon({ icon }: { icon: NavItem["icon"] }) {
  return (
    <svg className="shell-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      {icons[icon]}
    </svg>
  );
}
