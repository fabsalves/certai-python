import type { SortableRenderProps } from "./SortableList";

interface Props {
  dragHandle: SortableRenderProps["dragHandle"];
  label?: string;
  className?: string;
}

export function DragHandle({ dragHandle, label = "Reordenar", className = "" }: Props) {
  const { onPointerDown, ...listeners } = dragHandle.listeners ?? {};

  return (
    <span
      className={`drag-handle${className ? ` ${className}` : ""}`}
      ref={dragHandle.ref}
      {...dragHandle.attributes}
      {...listeners}
      aria-label={label}
      title={label}
      onPointerDown={(event) => {
        onPointerDown?.(event);
        event.stopPropagation();
      }}
      onClick={(event) => event.stopPropagation()}
    >
      <span className="drag-handle__grip" aria-hidden>
        {Array.from({ length: 6 }, (_, index) => (
          <span key={index} className="drag-handle__dot" />
        ))}
      </span>
    </span>
  );
}
