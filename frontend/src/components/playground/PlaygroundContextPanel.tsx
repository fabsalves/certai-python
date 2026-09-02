import { type ReactNode, useCallback, useEffect, useState } from "react";
import { extentLabel, originLabel } from "../../lib/coverage";
import { fetchPlaygroundContext, type PlaygroundContext } from "../../lib/playground";
import { PlaygroundPanelSkeleton } from "./PlaygroundPanelSkeleton";

interface Props {
  cohortId: string;
  lessonId: string | null;
  /** O contexto é sempre o de um aluno: a turma dele define o que está liberado. */
  studentId: string | null;
  refreshKey?: number;
}

const INGESTION_LABELS: Record<string, string> = {
  pending: "Aguardando",
  processing: "Processando",
  done: "Pronto",
  failed: "Falhou",
  unsupported: "Não suportado",
};

function ContextSection({
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
        {badge && <span className="playground-context__badge">{badge}</span>}
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
        <p className="muted playground-context__empty-value">Nenhum</p>
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

function ingestionLabel(status: string | null | undefined): string {
  if (!status) return "Sem relato";
  return INGESTION_LABELS[status] ?? status;
}

export function PlaygroundContextPanel({
  cohortId,
  lessonId,
  studentId,
  refreshKey = 0,
}: Props) {
  const [context, setContext] = useState<PlaygroundContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (!cohortId || !lessonId || !studentId) {
      setContext(null);
      return;
    }
    setLoading(true);
    setError("");
    fetchPlaygroundContext(cohortId, lessonId, studentId)
      .then(setContext)
      .catch(() => {
        setContext(null);
        setError("Não foi possível carregar o contexto da Lira.");
      })
      .finally(() => setLoading(false));
  }, [cohortId, lessonId, studentId]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const hasIngesting =
    context?.lesson_notes.some(
      (n) => n.ingestion_status === "pending" || n.ingestion_status === "processing",
    ) ||
    context?.track_material.ingestion_status === "pending" ||
    context?.track_material.ingestion_status === "processing";

  useEffect(() => {
    if (!hasIngesting) return;
    const timer = window.setInterval(load, 4000);
    return () => window.clearInterval(timer);
  }, [hasIngesting, load]);

  if (!lessonId || !studentId) {
    return (
      <div className="playground-context">
        <p className="muted playground-context__hint">
          {lessonId
            ? "Selecione um aluno para ver o contexto da turma dele."
            : "Selecione uma aula para ver o contexto."}
        </p>
      </div>
    );
  }

  return (
    <div className="playground-context">
      <header className="playground-context__head">
        <h2 className="playground-context__title">Contexto da Lira</h2>
        <button type="button" className="btn btn-ghost btn-sm" onClick={load} disabled={loading}>
          {loading ? "Atualizando…" : "Atualizar"}
        </button>
      </header>

      {error && <p className="form-error playground-context__error">{error}</p>}

      {loading && !context && !error && (
        <PlaygroundPanelSkeleton label="Carregando contexto…" rows={3} />
      )}

      {context && (
        <div className="playground-context__scroll">
          <ContextSection
            title="Posição do aluno"
            badge={context.current_position?.lesson ?? "N/D"}
          >
            {context.current_position ? (
              <p className="playground-context__meta">
                {context.current_position.module} → {context.current_position.lesson}
              </p>
            ) : (
              <p className="muted playground-context__empty-value">Sem posição definida</p>
            )}
          </ContextSection>

          {context.taught_scope.length > 0 && (
            <ContextSection
              title="Escopo realmente ministrado"
              badge={String(context.taught_scope.length)}
            >
              <p className="muted playground-context__empty-value">
                A aula desviou do plano. É este escopo que a Lira explora e que a
                avaliação cobra — o conteúdo planejado abaixo vira referência.
              </p>
              {context.taught_scope.map((item, index) => (
                <article
                  key={`taught-${item.lesson}-${index}`}
                  className="playground-context__note"
                >
                  <div className="playground-context__note-head">
                    <strong>{item.lesson}</strong>
                    <span className="playground-context__status is-active">
                      {originLabel(item.origin)} · {extentLabel(item.extent)}
                    </span>
                  </div>
                  <TextBlock label="Ministrado ao aluno" value={item.covered} />
                  {item.pending.trim() && (
                    <TextBlock label="NÃO ministrado" value={item.pending} />
                  )}
                </article>
              ))}
            </ContextSection>
          )}

          <ContextSection
            title="Conteúdo desbloqueado"
            badge={String(context.unlocked_content.length)}
            defaultOpen={context.unlocked_content.length > 0}
          >
            {context.unlocked_content.length === 0 ? (
              <p className="muted playground-context__empty-value">
                Nenhuma aula liberada ainda. A Lira só enxerga conteúdo das aulas que a turma já concluiu.
              </p>
            ) : (
              context.unlocked_content.map((item, index) =>
                item.module != null && item.description != null ? (
                  <TextBlock
                    key={`module-${item.module}-${index}`}
                    label={`Módulo: ${item.module}`}
                    value={item.description}
                  />
                ) : (
                  <TextBlock
                    key={`lesson-${item.lesson}-${index}`}
                    label={item.lesson || "Aula"}
                    value={item.content || ""}
                  />
                ),
              )
            )}
          </ContextSection>

          <ContextSection
            title="Relatos da turma"
            badge={String(context.lesson_notes.length)}
          >
            {context.lesson_notes.length === 0 ? (
              <p className="muted playground-context__empty-value">Nenhuma aula concluída.</p>
            ) : (
              context.lesson_notes.map((note) => (
                <article key={note.lesson_id} className="playground-context__note">
                  <div className="playground-context__note-head">
                    <strong>{note.lesson_title}</strong>
                    <span
                      className={`playground-context__status${
                        note.in_ai_bundle ? " is-active" : ""
                      }`}
                    >
                      {ingestionLabel(note.ingestion_status)}
                      {note.in_ai_bundle ? " · na Lira" : ""}
                    </span>
                  </div>
                  {note.has_attachment && (
                    <p className="playground-context__meta">Anexo: {note.attachment_filename}</p>
                  )}
                  <TextBlock label="Resumo" value={note.summary} />
                  <TextBlock label="Pontos pouco claros" value={note.unclear_points} />
                  <TextBlock label="Base de conhecimento (anexo)" value={note.knowledge_base} />
                </article>
              ))
            )}
          </ContextSection>

          <ContextSection
            title="Guia da trilha"
            badge={ingestionLabel(context.track_material.ingestion_status)}
          >
            {context.track_material.filename && (
              <p className="playground-context__meta">
                Arquivo: {context.track_material.filename}
                {context.track_material.in_ai_bundle ? " · enviado à Lira" : ""}
              </p>
            )}
            <TextBlock label="Guia macro" value={context.track_material.guide} />
          </ContextSection>

          <ContextSection title="Bloco enviado ao modelo" defaultOpen={false}>
            <pre className="playground-context__pre playground-context__pre--system">
              {context.system_blocks}
            </pre>
          </ContextSection>
        </div>
      )}
    </div>
  );
}
