import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import type { ModelOption, ModelSelectIcon } from "../../lib/admin";

interface Props {
  label: string;
  icon: ModelSelectIcon;
  value: string;
  options: ModelOption[];
  platformDefault?: string;
  onChange: (value: string) => void;
}

const GROUP_ORDER = [
  "frontier",
  "professional",
  "production",
  "preview",
  "systems",
  "reasoning",
  "realtime",
  "legacy",
  "custom",
] as const;

const GROUP_LABELS: Record<string, string> = {
  frontier: "Frontier",
  professional: "Profissional",
  production: "Produção",
  preview: "Preview",
  systems: "Sistemas",
  reasoning: "Raciocínio",
  realtime: "Realtime",
  legacy: "Legado",
  custom: "Atual",
};

function providerLabel(provider: string) {
  if (provider === "openai") return "OpenAI";
  if (provider === "groq") return "Groq";
  return provider;
}

function mergeOptions(options: ModelOption[], currentValue: string): ModelOption[] {
  if (!currentValue || options.some((option) => option.id === currentValue)) {
    return options;
  }
  return [
    {
      id: currentValue,
      label: currentValue,
      provider: "custom",
      category: "legacy",
      group: "custom",
      description: "Valor atual, fora do catálogo.",
    },
    ...options,
  ];
}

function groupOptions(options: ModelOption[]) {
  const buckets = new Map<string, ModelOption[]>();
  for (const option of options) {
    const key = option.group || "production";
    buckets.set(key, [...(buckets.get(key) ?? []), option]);
  }
  return GROUP_ORDER.filter((key) => buckets.has(key)).map((key) => ({
    key,
    label: GROUP_LABELS[key] ?? key,
    options: buckets.get(key) ?? [],
  }));
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg className={`model-select__chevron${open ? " is-open" : ""}`} width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M5 12.5 9.5 17 19 7" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TypeIcon({ name }: { name: ModelSelectIcon }) {
  const paths: Record<ModelSelectIcon, ReactNode> = {
    engine: (
      <>
        <rect x="5" y="8" width="14" height="10" rx="2" />
        <path d="M9 8V6h6v2" />
        <path d="M9 13h.01" />
        <path d="M12 13h.01" />
        <path d="M15 13h.01" />
      </>
    ),
    humanizer: (
      <>
        <path d="M5 19V7a2 2 0 0 1 2-2h7l5 5v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2Z" />
        <path d="M14 5v4h4" />
        <path d="M8 13h8" />
        <path d="M8 17h5" />
      </>
    ),
    evaluator: (
      <>
        <path d="M9 5h6" />
        <rect x="6" y="5" width="12" height="16" rx="2" />
        <path d="M9 12l2 2 4-4" />
      </>
    ),
    transcribe: (
      <>
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0" />
        <path d="M12 18v3" />
        <path d="M9 21h6" />
      </>
    ),
    realtime: (
      <>
        <path d="M5 10a7 7 0 0 1 14 0" />
        <path d="M8 12a4 4 0 0 1 8 0" />
        <circle cx="12" cy="16" r="1.5" />
        <path d="M12 17.5V21" />
      </>
    ),
    voice: (
      <>
        <path d="M4 10v4" />
        <path d="M8 7v10" />
        <path d="M12 4v16" />
        <path d="M16 7v10" />
        <path d="M20 10v4" />
      </>
    ),
  };

  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {paths[name]}
    </svg>
  );
}

export function ModelSelect({ label, icon, value, options, platformDefault, onChange }: Props) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const merged = useMemo(() => mergeOptions(options, value), [options, value]);
  const grouped = useMemo(() => groupOptions(merged), [merged]);
  const selected = merged.find((option) => option.id === value) ?? merged[0];

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
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

  return (
    <div className="model-select" ref={rootRef}>
      <div className="model-select__head">
        <span className="model-select__label">{label}</span>
        <span className={`provider-pill provider-pill--${selected?.provider ?? "custom"}`}>
          {providerLabel(selected?.provider ?? "custom")}
        </span>
      </div>
      <button
        type="button"
        className={`model-select__trigger${open ? " is-open" : ""}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="model-select__icon" aria-hidden>
          <TypeIcon name={icon} />
        </span>
        <span className="model-select__copy">
          <strong>{selected?.label ?? value}</strong>
          <small>{selected?.context || "\u00a0"}</small>
        </span>
        <Chevron open={open} />
      </button>

      {open && (
        <ul className="model-select__menu" id={listId} role="listbox">
          {grouped.map((section) => (
            <li key={section.key} className="model-select__group">
              <span className="model-select__group-label">{section.label}</span>
              <ul className="model-select__group-list">
                {section.options.map((option) => {
                  const active = option.id === value;
                  const isDefault = option.id === platformDefault;
                  const badge =
                    isDefault ? "padrão" : option.badge === "fastest" ? "mais rápido" : option.badge === "recommended" ? "recomendado" : null;
                  return (
                    <li key={option.id}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={active}
                        className={`model-select__option${active ? " is-active" : ""}`}
                        onClick={() => {
                          onChange(option.id);
                          setOpen(false);
                        }}
                      >
                        <span className="model-select__option-head">
                          <span className={`provider-pill provider-pill--${option.provider}`}>
                            {providerLabel(option.provider)}
                          </span>
                          <strong>{option.label}</strong>
                          <code className="model-select__id">{option.id}</code>
                          {badge && <span className="model-select__badge">{badge}</span>}
                          {active && (
                            <span className="model-select__check">
                              <CheckIcon />
                            </span>
                          )}
                        </span>
                        <span className="model-select__option-desc">{option.description}</span>
                        {option.context && <span className="model-select__option-meta">{option.context}</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
