import { useEffect, useMemo, useState } from "react";
import { PAGE_SIZE, paginate, type PageSlice } from "./pagination";

type Options = {
  pageSize?: number;
  /** Change this when the filtered dataset identity changes (e.g. search). */
  resetKey?: string | number;
};

type PaginationControls<T> = PageSlice<T> & {
  setPage: (page: number) => void;
};

export function usePagination<T>(
  items: readonly T[] | null | undefined,
  options: Options = {},
): PaginationControls<T> {
  const pageSize = options.pageSize ?? PAGE_SIZE;
  const resetKey = options.resetKey ?? "";
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [resetKey, pageSize]);

  const slice = useMemo(
    () => paginate(items ?? [], page, pageSize),
    [items, page, pageSize],
  );

  useEffect(() => {
    if (slice.page !== page) setPage(slice.page);
  }, [slice.page, page]);

  return {
    ...slice,
    setPage,
  };
}
