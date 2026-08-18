import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";
import { CountryFlag } from "./CountryFlag";
import {
  maskNationalNumber,
  nationalPlaceholder,
  parsePhoneParts,
  phoneDigits,
} from "../../lib/validation";
import {
  DEFAULT_DIAL_CODE,
  PHONE_COUNTRY_OPTIONS,
  phoneCountryByDialCode,
} from "../../lib/phoneCountries";

function ChevronIcon() {
  return (
    <svg className="phone-field__chevron" width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

interface Props {
  id: string;
  dialCode: string;
  national: string;
  onDialCodeChange: (dialCode: string) => void;
  onNationalChange: (national: string) => void;
  required?: boolean;
  error?: string;
  compact?: boolean;
  autoComplete?: string;
}

export function WhatsAppField({
  id,
  dialCode,
  national,
  onDialCodeChange,
  onNationalChange,
  required = false,
  error,
  compact = false,
  autoComplete,
}: Props) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const [menuStyle, setMenuStyle] = useState<CSSProperties>({});

  const errorId = error ? `${id}-error` : undefined;
  const resolvedDialCode = dialCode || DEFAULT_DIAL_CODE;
  const country = phoneCountryByDialCode(resolvedDialCode);

  const updateMenuPosition = () => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    setMenuStyle({
      position: "fixed",
      top: rect.bottom + 6,
      left: rect.left,
      minWidth: Math.max(rect.width, compact ? 220 : 240),
    });
  };

  useLayoutEffect(() => {
    if (!open) return;
    updateMenuPosition();
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, compact]);

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
  }, [open]);

  function openMenu() {
    setOpen(true);
    const selectedIndex = PHONE_COUNTRY_OPTIONS.findIndex((c) => c.dialCode === resolvedDialCode);
    setHighlight(selectedIndex >= 0 ? selectedIndex : 0);
  }

  function choose(nextDialCode: string) {
    onDialCodeChange(nextDialCode);
    const digits = phoneDigits(national);
    if (digits) {
      onNationalChange(maskNationalNumber(nextDialCode, digits));
    }
    setOpen(false);
    inputRef.current?.focus();
  }

  function onTriggerKeyDown(ev: KeyboardEvent<HTMLButtonElement>) {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      open ? setOpen(false) : openMenu();
    }
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      if (!open) openMenu();
    }
  }

  function onMenuKeyDown(ev: KeyboardEvent<HTMLUListElement>) {
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      setHighlight((prev) => Math.min(prev + 1, PHONE_COUNTRY_OPTIONS.length - 1));
    }
    if (ev.key === "ArrowUp") {
      ev.preventDefault();
      setHighlight((prev) => Math.max(prev - 1, 0));
    }
    if (ev.key === "Enter" && highlight >= 0) {
      ev.preventDefault();
      choose(PHONE_COUNTRY_OPTIONS[highlight].dialCode);
    }
  }

  function handleNationalInput(raw: string) {
    const digits = phoneDigits(raw);
    if (digits.length > 11) {
      const parsed = parsePhoneParts(digits, resolvedDialCode);
      onDialCodeChange(parsed.dialCode);
      onNationalChange(maskNationalNumber(parsed.dialCode, parsed.national));
      return;
    }
    onNationalChange(maskNationalNumber(resolvedDialCode, raw));
  }

  return (
    <div
      ref={rootRef}
      className={`phone-field${compact ? " phone-field--compact" : ""}${error ? " is-invalid" : ""}`}
    >
      <button
        ref={triggerRef}
        type="button"
        className="phone-field__ddi"
        aria-label={`Código do país${country ? `: ${country.name}` : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => (open ? setOpen(false) : openMenu())}
        onKeyDown={onTriggerKeyDown}
      >
        <CountryFlag dialCode={resolvedDialCode} />
        <span className="phone-field__code">+{resolvedDialCode}</span>
        <ChevronIcon />
      </button>

      <input
        ref={inputRef}
        id={id}
        type="tel"
        inputMode="tel"
        autoComplete={autoComplete ?? (compact ? "off" : "tel-national")}
        className="input"
        value={national}
        placeholder={nationalPlaceholder(resolvedDialCode)}
        required={required}
        aria-label={compact ? "WhatsApp" : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={errorId}
        onChange={(ev) => handleNationalInput(ev.target.value)}
      />

      {open &&
        createPortal(
          <ul
            ref={menuRef}
            id={listId}
            role="listbox"
            aria-label="País"
            className="phone-field__menu"
            style={menuStyle}
            onKeyDown={onMenuKeyDown}
          >
            {PHONE_COUNTRY_OPTIONS.map((option, index) => {
              const selected = option.dialCode === resolvedDialCode;
              const active = index === highlight;
              return (
                <li key={option.dialCode} role="presentation">
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={`phone-field__menu-option${selected ? " is-selected" : ""}${active ? " is-active" : ""}`}
                    onMouseEnter={() => setHighlight(index)}
                    onClick={() => choose(option.dialCode)}
                  >
                    <CountryFlag dialCode={option.dialCode} />
                    <span className="phone-field__menu-name">{option.name}</span>
                    <span className="phone-field__menu-code">+{option.dialCode}</span>
                  </button>
                </li>
              );
            })}
          </ul>,
          document.body,
        )}
    </div>
  );
}
