import { useEffect, useState } from "react";

export type ListViewMode = "table" | "cards";

const STORAGE_PREFIX = "certai.listView.";

export function useListView(screenKey: string, defaultMode: ListViewMode = "table") {
  const storageKey = `${STORAGE_PREFIX}${screenKey}`;

  const [view, setView] = useState<ListViewMode>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved === "table" || saved === "cards") return saved;
    } catch {
      /* ignore */
    }
    return defaultMode;
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, view);
    } catch {
      /* ignore */
    }
  }, [storageKey, view]);

  return [view, setView] as const;
}
