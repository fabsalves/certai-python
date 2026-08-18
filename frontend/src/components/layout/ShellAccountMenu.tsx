import { useEffect, useId, useState } from "react";
import { roleLabel, type User } from "../../lib/auth";
import { Tooltip } from "../ui/Tooltip";

function initials(name: string): string {
  return name
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

interface Props {
  user: User;
  variant: "rail" | "bar";
  collapsed?: boolean;
  onEditAccount: () => void;
  onLogout: () => void;
}

export function ShellAccountMenu({
  user,
  variant,
  collapsed = false,
  onEditAccount,
  onLogout,
}: Props) {
  const menuId = useId();
  const [open, setOpen] = useState(false);
  const showName = variant === "rail" && !collapsed;

  useEffect(() => {
    setOpen(false);
  }, [collapsed, variant]);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      const target = event.target as Element | null;
      if (!target?.closest("[data-shell-account]")) {
        setOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function closeMenu() {
    setOpen(false);
  }

  const whoami = (
    <button
      type="button"
      className="shell-account__trigger"
      onClick={() => setOpen((current) => !current)}
      aria-haspopup="menu"
      aria-expanded={open}
      aria-controls={menuId}
      aria-label="Conta e opções"
    >
      <span className="shell-account__avatar" aria-hidden>
        {initials(user.name)}
      </span>
      {showName && (
        <span className="shell-account__text">
          <strong>{user.name}</strong>
          <span>{roleLabel[user.role]}</span>
        </span>
      )}
    </button>
  );

  return (
    <div
      className={`shell-account${variant === "bar" ? " shell-account--bar" : ""}`}
      data-shell-account
    >
      {variant === "rail" && collapsed && !open ? (
        <Tooltip content="Conta">{whoami}</Tooltip>
      ) : (
        whoami
      )}

      {open && (
        <div className="shell-account__menu" id={menuId} role="menu">
          {(variant === "bar" || collapsed) && (
            <div className="shell-account__menu-head">{user.name}</div>
          )}
          <button
            type="button"
            role="menuitem"
            className="shell-account__menu-item"
            onClick={() => {
              closeMenu();
              onEditAccount();
            }}
          >
            Editar conta
          </button>
          <button
            type="button"
            role="menuitem"
            className="shell-account__menu-item shell-account__menu-item--danger"
            onClick={() => {
              closeMenu();
              onLogout();
            }}
          >
            Sair
          </button>
        </div>
      )}
    </div>
  );
}
