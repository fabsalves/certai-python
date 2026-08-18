import type { ReactNode } from "react";

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  searchLabel?: string;
  children?: ReactNode;
}

export function ListToolbar({
  search,
  onSearchChange,
  searchPlaceholder = "Buscar…",
  searchLabel = "Buscar",
  children,
}: Props) {
  return (
    <div className="list-toolbar">
      <input
        type="search"
        className="list-toolbar__search input"
        placeholder={searchPlaceholder}
        value={search}
        onChange={(event) => onSearchChange(event.target.value)}
        aria-label={searchLabel}
        autoComplete="off"
      />
      {children && <div className="list-toolbar__filters">{children}</div>}
    </div>
  );
}

interface SegmentOption<T extends string> {
  value: T;
  label: string;
}

interface FilterSegmentProps<T extends string> {
  value: T;
  options: SegmentOption<T>[];
  onChange: (value: T) => void;
  "aria-label": string;
}

export function FilterSegment<T extends string>({
  value,
  options,
  onChange,
  "aria-label": ariaLabel,
}: FilterSegmentProps<T>) {
  return (
    <div className="filter-segment" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`filter-segment__btn${
            option.value === value ? " filter-segment__btn--active" : ""
          }`}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

interface ListFilterSelectProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  "aria-label": string;
}

export function ListFilterSelect({
  id,
  value,
  onChange,
  options,
  "aria-label": ariaLabel,
}: ListFilterSelectProps) {
  return (
    <select
      id={id}
      className="list-toolbar__select input"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      aria-label={ariaLabel}
    >
      {options.map((option) => (
        <option key={option.value || option.label} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export function ListEmptyFilter({ message = "Nenhum resultado para os filtros atuais." }) {
  return (
    <div className="card empty-state">
      <p>{message}</p>
      <p className="muted" style={{ marginTop: 6 }}>
        Tente outras palavras ou limpe os filtros.
      </p>
    </div>
  );
}
