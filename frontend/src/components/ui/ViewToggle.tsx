import type { ListViewMode } from "../../lib/useListView";

interface Props {
  value: ListViewMode;
  onChange: (value: ListViewMode) => void;
}

export function ViewToggle({ value, onChange }: Props) {
  return (
    <div className="view-toggle" role="group" aria-label="Modo de visualização">
      <button
        type="button"
        className={`view-toggle__btn${value === "table" ? " view-toggle__btn--active" : ""}`}
        aria-pressed={value === "table"}
        onClick={() => onChange("table")}
      >
        Tabela
      </button>
      <button
        type="button"
        className={`view-toggle__btn${value === "cards" ? " view-toggle__btn--active" : ""}`}
        aria-pressed={value === "cards"}
        onClick={() => onChange("cards")}
      >
        Cards
      </button>
    </div>
  );
}
