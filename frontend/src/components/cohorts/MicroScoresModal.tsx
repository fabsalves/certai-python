import { useEffect, useState } from "react";
import {
  fetchLessonMicroScores,
  formatAssessmentWhen,
  type LessonMicroScore,
  type LessonMicroScores,
} from "../../lib/assessments";
import { Modal } from "../ui/Modal";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";
import { AssessmentLevelBadge } from "./AssessmentLevelBadge";

interface Props {
  open: boolean;
  onClose: () => void;
  cohortId: string;
  studentId: string;
  lessonId: string;
  studentName: string;
  lessonTitle?: string;
}

function MicroScoresSkeleton() {
  return (
    <SkeletonStatus label="Carregando evidências…" className="micro-scores-skeleton">
      {[0, 1, 2].map((key) => (
        <div key={key} className="micro-scores-list__item micro-scores-list__item--skeleton">
          <div className="micro-scores-list__head">
            <Skeleton variant="text" width="55%" height={16} />
            <Skeleton variant="rect" width={52} height={22} />
          </div>
          <Skeleton variant="text" width="100%" height={14} />
          <Skeleton variant="text" width="92%" height={14} />
          <Skeleton variant="text" width={120} height={12} />
        </div>
      ))}
    </SkeletonStatus>
  );
}

export function MicroScoresModal({
  open,
  onClose,
  cohortId,
  studentId,
  lessonId,
  studentName,
  lessonTitle,
}: Props) {
  const [data, setData] = useState<LessonMicroScores | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setData(null);
    fetchLessonMicroScores(cohortId, studentId, lessonId)
      .then(({ data: payload }) => {
        if (!cancelled) setData(payload);
      })
      .catch(() => {
        if (!cancelled) setError("Não foi possível carregar as evidências.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, cohortId, studentId, lessonId]);

  const titleLesson = data?.lesson_title || lessonTitle || "Aula";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Evidências da Lira"
      wide
      className="micro-scores-modal"
    >
      <p className="micro-scores-modal__meta">
        {studentName}
        <span aria-hidden> · </span>
        {titleLesson}
      </p>

      {loading && <MicroScoresSkeleton />}

      {error && !loading && (
        <p className="form-error" style={{ margin: 0 }}>
          {error}
        </p>
      )}

      {!loading && !error && data && data.scores.length === 0 && (
        <p className="muted micro-scores-modal__empty">
          Nenhuma evidência registrada nesta aula.
        </p>
      )}

      {!loading && !error && data && data.scores.length > 0 && (
        <ul className="micro-scores-list">
          {data.scores.map((score) => (
            <MicroScoreItem key={score.id} score={score} />
          ))}
        </ul>
      )}
    </Modal>
  );
}

function MicroScoreItem({ score }: { score: LessonMicroScore }) {
  return (
    <li className="micro-scores-list__item">
      <div className="micro-scores-list__head">
        <strong className="micro-scores-list__competency">
          {score.competency.trim() || "Sem competência"}
        </strong>
        <AssessmentLevelBadge level={score.level} />
      </div>
      {score.evidence.trim() ? (
        <p className="micro-scores-list__evidence">{score.evidence.trim()}</p>
      ) : (
        <p className="muted micro-scores-list__evidence">Sem evidência textual.</p>
      )}
      <p className="muted micro-scores-list__when">{formatAssessmentWhen(score.created_at)}</p>
    </li>
  );
}
