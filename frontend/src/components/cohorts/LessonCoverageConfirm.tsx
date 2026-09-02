import { useState } from "react";
import {
  COVERAGE_TEXT_MAX,
  type CoverageCandidate,
  type CoverageExtent,
  type CoverageSegment,
  extentLabel,
  isPlainCoverage,
  originLabel,
} from "../../lib/coverage";

interface Props {
  segments: CoverageSegment[];
  candidates: CoverageCandidate[];
  anchorLessonId: string;
  loading: boolean;
  /** The AI proposal did not come back; the anchor-only default is in place. */
  failed: boolean;
  disabled: boolean;
  onChange: (segments: CoverageSegment[]) => void;
}

/** What the session actually covered: the AI proposes, the professor confirms.
 *
 * Read-only until "Ajustar" — the normal flow is one glance and submit. Editing
 * is there so a scenario the AI missed can still be recorded, which is the point
 * of not depending on a heavy manual procedure. */
export function LessonCoverageConfirm({
  segments,
  candidates,
  anchorLessonId,
  loading,
  failed,
  disabled,
  onChange,
}: Props) {
  const [editing, setEditing] = useState(false);

  function update(lessonId: string, patch: Partial<CoverageSegment>) {
    onChange(
      segments.map((item) =>
        item.lesson_id === lessonId
          ? { ...item, ...patch, source: "professor" }
          : item,
      ),
    );
  }

  function setExtent(lessonId: string, extent: CoverageExtent) {
    // A fully covered lesson owes nothing — mirrors the server-side rule.
    update(lessonId, extent === "full" ? { extent, pending: "" } : { extent });
  }

  function remove(lessonId: string) {
    onChange(segments.filter((item) => item.lesson_id !== lessonId));
  }

  function add(candidate: CoverageCandidate) {
    const anchorIndex = candidates.findIndex((item) => item.is_anchor);
    const index = candidates.findIndex(
      (item) => item.lesson_id === candidate.lesson_id,
    );
    const next: CoverageSegment = {
      lesson_id: candidate.lesson_id,
      kind:
        index < anchorIndex
          ? "carryover"
          : index > anchorIndex
            ? "advance"
            : "planned",
      extent: "partial",
      covered: "",
      pending: candidate.standing_pending,
      source: "professor",
      lesson_title: candidate.lesson_title,
    };
    const merged = [...segments, next];
    const order = new Map(candidates.map((item, at) => [item.lesson_id, at]));
    merged.sort(
      (a, b) => (order.get(a.lesson_id) ?? 0) - (order.get(b.lesson_id) ?? 0),
    );
    onChange(merged);
  }

  const available = candidates.filter(
    (candidate) => !segments.some((item) => item.lesson_id === candidate.lesson_id),
  );

  if (loading) {
    return (
      <div className="coverage" aria-live="polite">
        <p className="coverage__head">
          <span className="coverage__title">Cobertura desta aula</span>
          <span className="muted">lendo o relato…</span>
        </p>
      </div>
    );
  }

  return (
    <div className="coverage">
      <p className="coverage__head">
        <span className="coverage__title">Cobertura desta aula</span>
        {!disabled && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setEditing((value) => !value)}
          >
            {editing ? "Pronto" : "Ajustar"}
          </button>
        )}
      </p>

      {failed && (
        <p className="coverage__note">
          Não foi possível ler o relato para sugerir a cobertura. Segue como aula do
          dia completa. Ajuste se a aula desviou do plano.
        </p>
      )}

      {!editing && isPlainCoverage(segments) ? (
        <p className="coverage__plain">
          A aula seguiu o conteúdo planejado. Ajuste se ficou incompleta, avançou
          na aula seguinte ou fechou pendência da anterior.
        </p>
      ) : (
        <ul className="coverage__list">
          {segments.map((segment) => (
            <li key={segment.lesson_id} className="coverage__item">
              <div className="coverage__item-head">
                <span className="coverage__lesson">{segment.lesson_title}</span>
                <span className={`coverage__tag coverage__tag--${segment.kind}`}>
                  {originLabel(segment.kind)}
                </span>
                {!editing && (
                  <span className="muted">{extentLabel(segment.extent)}</span>
                )}
              </div>

              {editing ? (
                <div className="coverage__edit">
                  <div className="coverage__extent" role="group" aria-label="Cobertura">
                    {(["full", "partial"] as CoverageExtent[]).map((value) => (
                      <label key={value} className="coverage__radio">
                        <input
                          type="radio"
                          name={`extent-${segment.lesson_id}`}
                          checked={segment.extent === value}
                          onChange={() => setExtent(segment.lesson_id, value)}
                        />
                        {extentLabel(value)}
                      </label>
                    ))}
                  </div>
                  <label className="coverage__field">
                    <span>O que foi dado</span>
                    <textarea
                      className="input"
                      rows={2}
                      maxLength={COVERAGE_TEXT_MAX}
                      value={segment.covered}
                      onChange={(ev) =>
                        update(segment.lesson_id, { covered: ev.target.value })
                      }
                    />
                  </label>
                  {segment.extent === "partial" && (
                    <label className="coverage__field">
                      <span>O que ficou pendente</span>
                      <textarea
                        className="input"
                        rows={2}
                        maxLength={COVERAGE_TEXT_MAX}
                        value={segment.pending}
                        onChange={(ev) =>
                          update(segment.lesson_id, { pending: ev.target.value })
                        }
                      />
                    </label>
                  )}
                  {segment.lesson_id !== anchorLessonId && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => remove(segment.lesson_id)}
                    >
                      Remover esta aula
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {segment.covered.trim() && (
                    <p className="coverage__text">{segment.covered}</p>
                  )}
                  {segment.pending.trim() && (
                    <p className="coverage__pending">
                      Pendente: {segment.pending}
                    </p>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {editing && available.length > 0 && (
        <div className="coverage__add">
          <span className="muted">Incluir aula tocada nesta sessão:</span>
          {available.map((candidate) => (
            <button
              key={candidate.lesson_id}
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => add(candidate)}
            >
              + {candidate.lesson_title}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
