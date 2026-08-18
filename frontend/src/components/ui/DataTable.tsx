import { Fragment, type ReactNode } from "react";
import type { ListViewMode } from "../../lib/useListView";

export type DataColumn<T> = {
  id: string;
  header: string;
  /** Card title on mobile (defaults to the first column). */
  primary?: boolean;
  /**
   * Mobile layout role:
   * - field (default): labeled row in the card
   * - actions: footer strip (no label)
   * - hidden: desktop table only
   */
  card?: "field" | "actions" | "hidden";
  align?: "start" | "end";
  render: (row: T) => ReactNode;
};

type DataTableProps<T> = {
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  layout?: ListViewMode;
  className?: string;
  /** Accessible name for the table / card list. */
  "aria-label"?: string;
};

/**
 * Desktop: classic table (or stacked cards when layout="cards").
 * Mobile: always stacked cards with labeled fields.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  layout = "table",
  className = "",
  "aria-label": ariaLabel,
}: DataTableProps<T>) {
  const primary =
    columns.find((column) => column.primary) ??
    columns.find((column) => column.card !== "actions" && column.card !== "hidden") ??
    columns[0];

  const fieldColumns = columns.filter(
    (column) =>
      column !== primary &&
      column.card !== "actions" &&
      column.card !== "hidden",
  );

  const actionColumns = columns.filter((column) => {
    if (column.card === "actions") return true;
    if (column.card === "hidden" || column.card === "field") return false;
    return !column.header.trim();
  });

  const rootClass = [
    "data-table",
    layout === "cards" ? "data-table--cards" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClass}>
      <div className="data-table__desktop table-wrap">
        <table className="table" aria-label={ariaLabel}>
          <thead>
            <tr>
              {columns.map((column) => (
                <th
                  key={column.id}
                  data-align={column.align === "end" ? "end" : undefined}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((column) => (
                  <td
                    key={column.id}
                    data-align={column.align === "end" ? "end" : undefined}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="data-table__cards" role="list" aria-label={ariaLabel}>
        {rows.map((row) => (
          <article key={rowKey(row)} className="data-card" role="listitem">
            {primary && (
              <div className="data-card__title">{primary.render(row)}</div>
            )}
            {fieldColumns.length > 0 && (
              <dl className="data-card__fields">
                {fieldColumns.map((column) => (
                  <div key={column.id} className="data-card__field">
                    <dt>{column.header}</dt>
                    <dd>{column.render(row)}</dd>
                  </div>
                ))}
              </dl>
            )}
            {actionColumns.length > 0 && (
              <div className="data-card__actions">
                {actionColumns.map((column) => (
                  <Fragment key={column.id}>{column.render(row)}</Fragment>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
