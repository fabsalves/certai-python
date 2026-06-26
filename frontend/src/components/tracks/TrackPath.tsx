import type { PathNodeItem } from "./trackPathUtils";

const W = 320;
const ROW = 108;
const HEADER = 48;
const HEADER_GAP = 56;
const LEFT = 68;
const RIGHT = 252;

interface LayoutNode extends PathNodeItem {
  top: number;
}

function layoutNodes(nodes: PathNodeItem[]): { laid: LayoutNode[]; height: number } {
  let top = 0;
  const laid: LayoutNode[] = [];

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    if (node.moduleLabel) {
      top += i === 0 ? HEADER : HEADER_GAP;
    }
    laid.push({ ...node, top });
    top += ROW;
  }

  return { laid, height: top + 32 };
}

function cx(side: "left" | "right"): number {
  return side === "left" ? LEFT : RIGHT;
}

/** Ancora a curva abaixo do título da aula, não pelo centro da bolha. */
function curve(from: LayoutNode, to: LayoutNode): string {
  const x1 = cx(from.side);
  const y1 = from.top + ROW - 8;
  const x2 = cx(to.side);
  const y2 = to.top + 10;
  const my = (y1 + y2) / 2;
  return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;
}

interface Props {
  nodes: PathNodeItem[];
  selectedId?: string | null;
}

export function TrackPath({ nodes, selectedId }: Props) {
  if (nodes.length === 0) {
    return (
      <div className="track-path track-path--empty">
        <p className="muted">Nenhuma aula no percurso.</p>
      </div>
    );
  }

  const { laid, height } = layoutNodes(nodes);
  const curves = laid.slice(1).map((curr, i) => {
    const prev = laid[i];
    const muted =
      prev.state === "inactive" ||
      prev.state === "locked" ||
      curr.state === "inactive" ||
      curr.state === "locked";
    return { d: curve(prev, curr), muted };
  });

  return (
    <div className="track-path" style={{ height }}>
      <svg
        className="track-path__svg"
        viewBox={`0 0 ${W} ${height}`}
        preserveAspectRatio="xMidYMin meet"
        aria-hidden
      >
        <defs>
          <linearGradient id="path-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.9" />
            <stop offset="100%" stopColor="var(--brand-700)" stopOpacity="0.85" />
          </linearGradient>
        </defs>
        {curves.map((seg, i) => (
          <path
            key={i}
            d={seg.d}
            className={`track-path__curve${seg.muted ? " track-path__curve--muted" : ""}`}
            fill="none"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>

      <div className="track-path__layer">
        {laid.map((node) => {
          const isSelected = selectedId === node.id;
          const stateClass = isSelected ? "selected" : node.state;

          return (
            <div key={node.id} className="track-path__slot" style={{ top: node.top }}>
              {node.moduleLabel && (
                <div className="track-path__module" style={{ top: -HEADER + 4 }}>
                  <span className="track-path__module-line" />
                  <div className="track-path__module-head">
                    <span className="track-path__module-pill">
                      <span className="track-path__module-pill-text">
                        {node.professorLabel
                          ? `${node.moduleLabel} - ${node.professorLabel}`
                          : node.moduleLabel}
                      </span>
                    </span>
                    {node.levelLabel && (
                      <span className="track-path__module-level">{node.levelLabel}</span>
                    )}
                  </div>
                  <span className="track-path__module-line" />
                </div>
              )}

              <div className={`track-path__node track-path__node--${node.side}`}>
                <button
                  type="button"
                  className={`track-path__bubble track-path__bubble--${stateClass}`}
                  onClick={node.onClick}
                  disabled={!node.onClick || node.state === "locked"}
                  aria-current={isSelected ? "step" : undefined}
                  aria-label={node.title}
                >
                  <span className="track-path__ring" aria-hidden />
                  <span className="track-path__bubble-face">
                    {node.state === "done" ? (
                      <svg viewBox="0 0 24 24" className="track-path__check" aria-hidden>
                        <path
                          d="M5 13l4 4L19 7"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    ) : node.step !== null ? (
                      <span className="track-path__num">{node.step}</span>
                    ) : (
                      <span className="track-path__dot">·</span>
                    )}
                  </span>
                </button>

                <div
                  className={`track-path__label track-path__label--${node.side}${node.state === "inactive" ? " track-path__label--muted" : ""}`}
                >
                  <span className="track-path__label-text">{node.title}</span>
                  {node.state === "current" && (
                    <span className="track-path__label-badge">Aula atual</span>
                  )}
                  {node.state === "inactive" && (
                    <span className="track-path__label-badge track-path__label-badge--muted">Desativada</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
