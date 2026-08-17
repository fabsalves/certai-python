export function reorderByIndex<T>(items: T[], fromIndex: number, toIndex: number): T[] {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return items;
  const next = [...items];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

export function withSequentialPositions<T extends { position: number }>(items: T[]): T[] {
  return items.map((item, index) => ({ ...item, position: index + 1 }));
}

/** Evita violação de unique (track_id, position) / (module_id, position) ao reordenar. */
export async function persistSequentialPositions(
  items: { id: string; position: number }[],
  patchPosition: (id: string, position: number) => Promise<unknown>,
): Promise<void> {
  const needsReorder = items.some((item, index) => item.position !== index + 1);
  if (!needsReorder) return;

  // Sequencial: se um PATCH falhar no meio, não deixa metade em posição negativa.
  for (const [index, item] of items.entries()) {
    await patchPosition(item.id, -(index + 1));
  }
  for (const [index, item] of items.entries()) {
    await patchPosition(item.id, index + 1);
  }
}
