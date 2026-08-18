/** Client-side pagination helpers shared by list screens. */

export const PAGE_SIZE = 25;

export type PageSlice<T> = {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  from: number;
  to: number;
};

export function paginate<T>(
  items: readonly T[],
  page: number,
  pageSize: number = PAGE_SIZE,
): PageSlice<T> {
  const size = Math.max(1, pageSize);
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / size) || 1);
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * size;
  const slice = items.slice(start, start + size);

  return {
    items: slice,
    page: safePage,
    pageSize: size,
    total,
    totalPages: total === 0 ? 0 : totalPages,
    from: total === 0 ? 0 : start + 1,
    to: total === 0 ? 0 : start + slice.length,
  };
}

/** Compact window of page numbers with ellipsis gaps. */
export function pageWindow(
  page: number,
  totalPages: number,
): Array<number | "gap"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, totalPages, page]);
  for (let offset = 1; offset <= 1; offset += 1) {
    pages.add(page - offset);
    pages.add(page + offset);
  }
  if (page <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }
  if (page >= totalPages - 2) {
    pages.add(totalPages - 1);
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  }

  const sorted = [...pages]
    .filter((value) => value >= 1 && value <= totalPages)
    .sort((a, b) => a - b);

  const window: Array<number | "gap"> = [];
  for (const value of sorted) {
    const previous = window[window.length - 1];
    if (typeof previous === "number" && value - previous > 1) {
      window.push("gap");
    }
    window.push(value);
  }
  return window;
}
