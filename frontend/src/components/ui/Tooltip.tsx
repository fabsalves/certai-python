import {
  Children,
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type FocusEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

const OPEN_DELAY_MS = 200;
const VIEWPORT_PAD = 8;
const GAP = 8;

type Placement = "top" | "bottom";

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  /** Optional class on the floating panel. */
  className?: string;
}

interface Coords {
  top: number;
  left: number;
  placement: Placement;
  arrowLeft: number;
}

function mergeDescribedBy(
  existing: string | undefined,
  tooltipId: string | undefined,
): string | undefined {
  const parts = [existing, tooltipId].filter(Boolean);
  return parts.length > 0 ? parts.join(" ") : undefined;
}

export function Tooltip({ content, children, className }: TooltipProps) {
  const tooltipId = useId();
  const anchorRef = useRef<HTMLSpanElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const openTimerRef = useRef<number | null>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<Coords | null>(null);

  const clearOpenTimer = useCallback(() => {
    if (openTimerRef.current != null) {
      window.clearTimeout(openTimerRef.current);
      openTimerRef.current = null;
    }
  }, []);

  const close = useCallback(() => {
    clearOpenTimer();
    setOpen(false);
  }, [clearOpenTimer]);

  const scheduleOpen = useCallback(() => {
    if (!content) return;
    clearOpenTimer();
    openTimerRef.current = window.setTimeout(() => {
      openTimerRef.current = null;
      setOpen(true);
    }, OPEN_DELAY_MS);
  }, [clearOpenTimer, content]);

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    const panel = panelRef.current;
    if (!anchor || !panel) return;

    const trigger = anchor.getBoundingClientRect();
    const tip = panel.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    let placement: Placement = "top";
    let top = trigger.top - tip.height - GAP;
    if (top < VIEWPORT_PAD) {
      placement = "bottom";
      top = trigger.bottom + GAP;
      if (top + tip.height > vh - VIEWPORT_PAD) {
        // Prefer the side with more room.
        const spaceAbove = trigger.top - VIEWPORT_PAD;
        const spaceBelow = vh - VIEWPORT_PAD - trigger.bottom;
        if (spaceAbove >= spaceBelow) {
          placement = "top";
          top = Math.max(VIEWPORT_PAD, trigger.top - tip.height - GAP);
        } else {
          placement = "bottom";
          top = Math.min(trigger.bottom + GAP, vh - tip.height - VIEWPORT_PAD);
        }
      }
    }

    const idealLeft = trigger.left + trigger.width / 2 - tip.width / 2;
    const left = Math.min(
      Math.max(idealLeft, VIEWPORT_PAD),
      vw - tip.width - VIEWPORT_PAD,
    );
    const arrowLeft = Math.min(
      Math.max(trigger.left + trigger.width / 2 - left, 12),
      tip.width - 12,
    );

    setCoords({ top, left, placement, arrowLeft });
  }, []);

  useLayoutEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    updatePosition();
  }, [open, content, updatePosition]);

  useEffect(() => {
    if (!open) return;
    const onScrollOrResize = () => updatePosition();
    window.addEventListener("resize", onScrollOrResize);
    // Capture scroll from nested overflow containers (e.g. student list).
    window.addEventListener("scroll", onScrollOrResize, true);
    return () => {
      window.removeEventListener("resize", onScrollOrResize);
      window.removeEventListener("scroll", onScrollOrResize, true);
    };
  }, [open, updatePosition]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  useEffect(() => () => clearOpenTimer(), [clearOpenTimer]);

  if (content == null || content === false || content === "") {
    return <>{children}</>;
  }

  const describedBy = open ? tooltipId : undefined;
  let trigger: ReactNode = children;
  if (isValidElement(children) && Children.count(children) === 1) {
    const child = children as ReactElement<{ "aria-describedby"?: string }>;
    trigger = cloneElement(child, {
      "aria-describedby": mergeDescribedBy(child.props["aria-describedby"], describedBy),
    });
  }

  const onBlurCapture = (event: FocusEvent<HTMLSpanElement>) => {
    const next = event.relatedTarget as Node | null;
    if (next && event.currentTarget.contains(next)) return;
    close();
  };

  const panelStyle: CSSProperties | undefined = coords
    ? {
        top: coords.top,
        left: coords.left,
        ["--tooltip-arrow-left" as string]: `${coords.arrowLeft}px`,
      }
    : { top: -9999, left: -9999, visibility: "hidden" };

  return (
    <span
      ref={anchorRef}
      className="ui-tooltip-anchor"
      onMouseEnter={scheduleOpen}
      onMouseLeave={close}
      onFocusCapture={scheduleOpen}
      onBlurCapture={onBlurCapture}
    >
      {trigger}
      {open &&
        createPortal(
          <div
            ref={panelRef}
            id={tooltipId}
            role="tooltip"
            className={`ui-tooltip ui-tooltip--${coords?.placement ?? "top"}${
              className ? ` ${className}` : ""
            }`}
            style={panelStyle}
          >
            <div className="ui-tooltip__content">{content}</div>
            <span className="ui-tooltip__arrow" aria-hidden />
          </div>,
          document.body,
        )}
    </span>
  );
}
