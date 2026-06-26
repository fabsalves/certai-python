import { useMemo, type ReactNode } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DraggableAttributes,
  type DraggableSyntheticListeners,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

export interface SortableDragHandle {
  ref: (element: HTMLElement | null) => void;
  attributes: DraggableAttributes;
  listeners: DraggableSyntheticListeners | undefined;
}

export interface SortableRenderProps {
  dragHandle: SortableDragHandle;
  isDragging: boolean;
}

interface SortableRowProps {
  id: string;
  children: (props: SortableRenderProps) => ReactNode;
}

function SortableRow({ id, children }: SortableRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className={isDragging ? "sortable-item sortable-item--dragging" : "sortable-item"}
    >
      {children({
        dragHandle: { ref: setActivatorNodeRef, attributes, listeners },
        isDragging,
      })}
    </div>
  );
}

interface Props<T extends { id: string }> {
  items: T[];
  onReorder: (items: T[]) => void | Promise<void>;
  renderItem: (item: T, props: SortableRenderProps) => ReactNode;
  className?: string;
}

export function SortableList<T extends { id: string }>({
  items,
  onReorder,
  renderItem,
  className,
}: Props<T>) {
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const ids = useMemo(() => items.map((item) => item.id), [items]);

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const fromIndex = items.findIndex((item) => item.id === active.id);
    const toIndex = items.findIndex((item) => item.id === over.id);
    if (fromIndex === -1 || toIndex === -1) return;

    const next = [...items];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    void onReorder(next);
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={ids} strategy={verticalListSortingStrategy}>
        <div className={className}>
          {items.map((item) => (
            <SortableRow key={item.id} id={item.id}>
              {(props) => renderItem(item, props)}
            </SortableRow>
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
