import { type ReactNode, useCallback, useEffect, useState } from "react";
import { fetchPlaygroundScores, type PlaygroundMicroScore, type PlaygroundScores } from "../../lib/playground";

interface Props {
  cohortId: string;
  studentId: string;
  lessonId: string | null;
  refreshKey?: number;
}

const LEVEL_LABELS: Record<string, string> = {
  very_low: "Muito baixo",
  low: "Baixo",
  medium: "Médio",
  high: "Alto",
};

function levelLabel(level: string): string {
  return LEVEL_LABELS[level] ?? level;
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function ScoresSection({
  title,
  badge,
  defaultOpen = true,
  children,
}: {
  title: string;
  badge?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="playground-context__section">
      <button
        type="button"
        className="playground-context__section-head"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span>{title}</span>
        {badge !== undefined && <span className="playground-context__badge">{badge}</span>}
        <span className="playground-context__chevron" aria-hidden>
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && <div className="playground-context__section-body">{children}</div>}
    </section>
  );
}

function TextBlock({ label, value }: { label: string; value: string }) {
  if (!value.trim()) {
    return (
      <div className="playground-context__field">
        <span className="playground-context__label">{label}</span>
        <p className="muted playground-context__empty-value">—</p>
      </div>
    );
  }
  return (
    <div className="playground-context__field">
      <span className="playground-context__label">{label}</span>
      <pre className="playground-context__pre">{value.trim()}</pre>
    </div>
  );
}

function ScoreCard({ score }: { score: PlaygroundMicroScore }) {
  return (
    <article className="playground-context__note">
      <div className="playground-context__note-head">
        <strong>{score.competency || "Sem competência"}</strong>
        <span className="playground-context__status is-active">{levelLabel(score.level)}</span>
      </div>
      {score.lesson_title && (
        <p className="playground-context__meta">{score.lesson_title}</p>
      )}
      <p className="playground-context__meta">{formatWhen(score.created_at)}</p>
      <TextBlock label="Evidência" value={score.evidence} />
    </article>
  );
}

export function PlaygroundScoresPanel({
  cohortId,
  studentId,
  lessonId,
  refreshKey = 0,
}: Props) {
  const [scores, setScores] = useState<PlaygroundScores | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!cohortId || !studentId || !lessonId) {
      setScores(null);
      return;
    }
    setLoading(true);
    setError("");
    fetchPlaygroundScores(cohortId, studentId, lessonId)
      .then(setScores)
      .catch(() => {
        setScores(null);
        setError("Não foi possível carregar os scores.");
      })
      .finally(() => setLoading(false));
  }, [cohortId, studentId, lessonId]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  if (!studentId) {
    return (
      <div className="playground-context">
        <p className="muted playground-context__hint">Selecione um aluno para ver os scores.</p>
      </div>
    );
  }

  if (!lessonId) {
    return (
      <div className="playground-context">
        <p className="muted playground-context__hint">Selecione uma aula para ver os scores.</p>
      </div>
    );
  }

  return (
    <div className="playground-context">
      <header className="playground-context__head">
        <h2 className="playground-context__title">Scores do aluno</h2>
        <button type="button" className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          {loading ? "Atualizando…" : "Atualizar"}
        </button>
      </header>

      {error && <p className="form-error playground-context__error">{error}</p>}

      {loading && !scores && !error && (
        <p className="muted playground-context__hint">Carregando scores…</p>
      )}

      {scores && (
        <div className="playground-context__scroll">
          <ScoresSection title="Competência da trilha">
            <TextBlock label="Macro" value={scores.track_competency} />
          </ScoresSection>

          <ScoresSection
            title="Nesta aula"
            badge={String(scores.scores_in_lesson.length)}
          >
            <p className="playground-context__meta">
              {scores.lesson_focus.lesson_title}
            </p>
            {scores.scores_in_lesson.length === 0 ? (
              <p className="muted playground-context__empty-value">
                Nenhum score nesta aula. A Lira registra via tool quando há demonstração
                na conversa — não a cada mensagem.
              </p>
            ) : (
              scores.scores_in_lesson.map((score) => (
                <ScoreCard key={score.id} score={score} />
              ))
            )}
          </ScoresSection>

          <ScoresSection
            title="Outras aulas"
            badge={String(scores.scores_other_lessons.length)}
            defaultOpen={false}
          >
            {scores.scores_other_lessons.length === 0 ? (
              <p className="muted playground-context__empty-value">—</p>
            ) : (
              scores.scores_other_lessons.map((score) => (
                <ScoreCard key={score.id} score={score} />
              ))
            )}
          </ScoresSection>
        </div>
      )}
    </div>
  );
}
