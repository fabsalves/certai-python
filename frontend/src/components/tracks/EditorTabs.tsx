import type { ReactNode } from "react";

export interface EditorTabItem {
  id: string;
  label: string;
  disabled?: boolean;
  count?: number;
}

interface Props {
  tabs: EditorTabItem[];
  active: string;
  onChange: (id: string) => void;
  children: ReactNode;
}

export function EditorTabs({ tabs, active, onChange, children }: Props) {
  return (
    <div className="editor-tabs">
      <div className="editor-tabs__bar" role="tablist" aria-label="Editor de trilha">
        {tabs.map((tab) => {
          const isActive = active === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`track-tab-${tab.id}`}
              aria-selected={isActive}
              aria-controls={`track-panel-${tab.id}`}
              className={`editor-tabs__tab${isActive ? " editor-tabs__tab--active" : ""}`}
              disabled={tab.disabled}
              onClick={() => onChange(tab.id)}
            >
              {tab.label}
              {tab.count != null && tab.count > 0 && (
                <span className="editor-tabs__count">{tab.count}</span>
              )}
            </button>
          );
        })}
      </div>
      {children}
    </div>
  );
}

interface PanelProps {
  id: string;
  labelledBy: string;
  hidden: boolean;
  children: ReactNode;
}

export function EditorTabPanel({ id, labelledBy, hidden, children }: PanelProps) {
  return (
    <div
      role="tabpanel"
      id={`track-panel-${id}`}
      aria-labelledby={labelledBy}
      hidden={hidden}
      className="editor-tabs__panel"
    >
      {!hidden && children}
    </div>
  );
}
