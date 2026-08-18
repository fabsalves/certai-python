import { pageWindow } from "../../lib/pagination";

type PaginationProps = {
  page: number;
  totalPages: number;
  total: number;
  from: number;
  to: number;
  onPageChange: (page: number) => void;
  className?: string;
};

export function Pagination({
  page,
  totalPages,
  total,
  from,
  to,
  onPageChange,
  className = "",
}: PaginationProps) {
  if (total === 0 || totalPages <= 1) return null;

  const pages = pageWindow(page, totalPages);

  return (
    <nav className={`pager ${className}`.trim()} aria-label="Paginação">
      <p className="pager__meta">
        <span className="pager__range">
          {from}–{to}
        </span>
        <span className="pager__sep" aria-hidden="true">
          ·
        </span>
        <span className="pager__total">{total} no total</span>
      </p>

      <div className="pager__controls">
        <button
          type="button"
          className="pager__btn"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Página anterior"
          title="Anterior"
        >
          <IconChevron direction="left" />
        </button>

        {pages.map((entry, index) =>
          entry === "gap" ? (
            <span key={`gap-${index}`} className="pager__gap" aria-hidden="true">
              …
            </span>
          ) : (
            <button
              key={entry}
              type="button"
              className="pager__btn pager__page"
              data-active={entry === page ? "true" : undefined}
              onClick={() => onPageChange(entry)}
              aria-label={`Página ${entry}`}
              aria-current={entry === page ? "page" : undefined}
            >
              {entry}
            </button>
          ),
        )}

        <button
          type="button"
          className="pager__btn"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Próxima página"
          title="Próxima"
        >
          <IconChevron direction="right" />
        </button>
      </div>
    </nav>
  );
}

function IconChevron({ direction }: { direction: "left" | "right" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="pager__chevron"
      aria-hidden="true"
    >
      {direction === "left" ? (
        <path d="m15 6-6 6 6 6" />
      ) : (
        <path d="m9 6 6 6-6 6" />
      )}
    </svg>
  );
}
