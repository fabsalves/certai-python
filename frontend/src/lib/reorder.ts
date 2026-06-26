export function reorderByIndex<T>(items: T[], fromIndex: number, toIndex: number): T[] {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return items;
  const next = [...items];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

/** Evita violação de unique (track_id, position) / (module_id, position) ao reordenar. */
export async function persistSequentialPositions(
  items: { id: string; position: number }[],
  patchPosition: (id: string, position: number) => Promise<unknown>,
): Promise<void> {
  const needsReorder = items.some((item, index) => item.position !== index + 1);
  if (!needsReorder) return;

  await Promise.all(items.map((item, index) => patchPosition(item.id, -(index + 1))));
  await Promise.all(items.map((item, index) => patchPosition(item.id, index + 1)));
}
