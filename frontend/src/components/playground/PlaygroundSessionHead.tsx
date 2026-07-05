import type { ReactNode } from "react";

interface PlaygroundSessionHeadProps {
  title: string;
  participantName: string;
  roleLabel?: string;
  actions?: ReactNode;
}

export function PlaygroundSessionHead({
  title,
  participantName,
  roleLabel,
  actions,
}: PlaygroundSessionHeadProps) {
  return (
    <header className="playground-session-head">
      <div className="playground-session-head__copy">
        <h1 className="playground-session-head__title" title={title}>
          {title}
        </h1>
        <p className="playground-session-head__meta">
          {participantName}
          {roleLabel ? ` · ${roleLabel}` : ""}
        </p>
      </div>
      {actions && <div className="playground-session-head__actions">{actions}</div>}
    </header>
  );
}
