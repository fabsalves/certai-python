import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

export interface SelectOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

interface SelectProps {
  id?: string;
  label?: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  required?: boolean;
  className?: string;
  variant?: "default" | "drawer" | "sidebar";
  icon?: ReactNode;
  "aria-label"?: string;
}

function ChevronIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 12.5 9.5 17 19 7"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Select({
  id,
  label,
  value,
  options,
  onChange,
  disabled = false,
  placeholder = "Selecione…",
  required = false,
  className = "",
  variant = "default",
  icon,
  "aria-label": ariaLabel,
}: SelectProps) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});

  const enabledOptions = options.filter((opt) => !opt.disabled);
  const selected = options.find((opt) => opt.value === value);
  const displayLabel = selected?.label ?? placeholder;
  const isPlaceholder = !selected?.value;

  const updateMenuPosition = () => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const matchTrigger = variant === "sidebar";
    setMenuStyle({
      position: "fixed",
      top: rect.bottom + (matchTrigger ? 4 : 6),
      left: rect.left,
      width: matchTrigger ? rect.width : Math.max(rect.width, 260),
      minWidth: rect.width,
      zIndex: 80,
    });
  };

  useLayoutEffect(() => {
    if (!open) return;
    updateMenuPosition();
    // Second measure after paint: scrollbar / font can shift the trigger on first open.
    const raf = requestAnimationFrame(() => updateMenuPosition());
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, variant]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(ev: MouseEvent) {
      const target = ev.target as Node;
      if (rootRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKeyDown(ev: globalThis.KeyboardEvent) {
      if (ev.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, listId]);

  useEffect(() => {
    if (!open) setHighlight(-1);
  }, [open]);

  function openMenu() {
    if (disabled) return;
    // Position before the portal mounts so the first paint is already aligned.
    updateMenuPosition();
    setOpen(true);
    const selectedIndex = enabledOptions.findIndex((opt) => opt.value === value);
    setHighlight(selectedIndex >= 0 ? selectedIndex : 0);
  }

  function choose(nextValue: string) {
    onChange(nextValue);
    setOpen(false);
    triggerRef.current?.focus();
  }

  function moveHighlight(delta: number) {
    if (enabledOptions.length === 0) return;
    setHighlight((prev) => {
      const start = prev < 0 ? 0 : prev;
      let next = start;
      for (let i = 0; i < enabledOptions.length; i += 1) {
        next = (next + delta + enabledOptions.length) % enabledOptions.length;
        if (!enabledOptions[next]?.disabled) return next;
      }
      return start;
    });
  }

  function onTriggerKeyDown(ev: KeyboardEvent<HTMLButtonElement>) {
    if (disabled) return;
    switch (ev.key) {
      case "ArrowDown":
      case "ArrowUp":
        ev.preventDefault();
        if (!open) openMenu();
        else moveHighlight(ev.key === "ArrowDown" ? 1 : -1);
        break;
      case "Enter":
      case " ":
        ev.preventDefault();
        if (!open) openMenu();
        else if (highlight >= 0 && enabledOptions[highlight]) {
          choose(enabledOptions[highlight].value);
        }
        break;
      case "Escape":
        setOpen(false);
        break;
      default:
        break;
    }
  }

  const fieldClass = variant === "drawer" ? "drawer-field" : "field";
  const labelClass = variant === "drawer" ? "drawer-field__label" : undefined;
  const selectClass = [
    "ui-select",
    variant === "drawer" ? "ui-select--drawer" : "",
    variant === "sidebar" ? "ui-select--sidebar" : "",
  ]
    .filter(Boolean)
    .join(" ");
  // className must land on the outermost node — otherwise flex grow in toolbars is ignored.
  const wrapperClass = [label ? fieldClass : null, className].filter(Boolean).join(" ") || undefined;

  const menu =
    open &&
    createPortal(
      <ul
        ref={menuRef}
        id={listId}
        className={`ui-select__menu${variant === "sidebar" ? " ui-select__menu--sidebar" : ""}`}
        role="listbox"
        aria-labelledby={label ? id : undefined}
        aria-label={label ? undefined : ariaLabel}
        style={menuStyle}
      >
        {options.map((opt) => {
          const enabledIndex = enabledOptions.indexOf(opt);
          const isSelected = opt.value === value;
          const isHighlighted = enabledIndex === highlight;
          return (
            <li
              key={opt.value || opt.label}
              role="option"
              aria-selected={isSelected}
              aria-disabled={opt.disabled || undefined}
              className={[
                "ui-select__option",
                isSelected ? "is-selected" : "",
                isHighlighted ? "is-highlighted" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onMouseEnter={() => {
                if (enabledIndex >= 0) setHighlight(enabledIndex);
              }}
              onMouseDown={(ev) => ev.preventDefault()}
              onClick={() => {
                if (!opt.disabled) choose(opt.value);
              }}
            >
              <span className="ui-select__option-copy">
                <span className="ui-select__option-label">{opt.label}</span>
                {opt.description && (
                  <span className="ui-select__option-desc">{opt.description}</span>
                )}
              </span>
              {variant === "sidebar" && isSelected && (
                <span className="ui-select__option-check" aria-hidden>
                  <CheckIcon />
                </span>
              )}
            </li>
          );
        })}
      </ul>,
      document.body,
    );

  return (
    <div ref={rootRef} className={wrapperClass}>
      {label && (
        <label className={labelClass} htmlFor={id}>
          {label}
        </label>
      )}
      <div className={selectClass}>
        <button
          ref={triggerRef}
          id={id}
          type="button"
          className={`ui-select__trigger${open ? " is-open" : ""}`}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-required={required || undefined}
          aria-label={label ? undefined : ariaLabel}
          title={displayLabel}
          onClick={() => (open ? setOpen(false) : openMenu())}
          onKeyDown={onTriggerKeyDown}
        >
          {icon && (
            <span className="ui-select__icon" aria-hidden>
              {icon}
            </span>
          )}
          <span className={`ui-select__value${isPlaceholder ? " is-placeholder" : ""}`}>
            {displayLabel}
          </span>
          <span className="ui-select__chevron" aria-hidden>
            <ChevronIcon />
          </span>
        </button>
      </div>
      {menu}
    </div>
  );
}
