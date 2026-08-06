import type { CSSProperties, ReactNode } from "react";

type SkeletonVariant = "text" | "rect" | "circle";

interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  className?: string;
}

function toCssSize(value: string | number | undefined): string | undefined {
  if (value == null) return undefined;
  return typeof value === "number" ? `${value}px` : value;
}

export function Skeleton({
  variant = "rect",
  width,
  height,
  className = "",
}: SkeletonProps) {
  const style: CSSProperties = {
    width: toCssSize(width),
    height: toCssSize(height),
  };

  return (
    <span
      className={`skeleton skeleton--${variant}${className ? ` ${className}` : ""}`}
      style={style}
      aria-hidden
    />
  );
}

interface SkeletonStatusProps {
  label?: string;
  className?: string;
  children: ReactNode;
}

export function SkeletonStatus({
  label = "Carregando…",
  className = "",
  children,
}: SkeletonStatusProps) {
  return (
    <div
      className={className}
      aria-busy="true"
      aria-live="polite"
      role="status"
    >
      {children}
      <span className="sr-only">{label}</span>
    </div>
  );
}
