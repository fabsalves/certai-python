import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Enrollment } from "../../lib/cohorts";
import { useAuth } from "../../lib/auth";
import { StudentEnrollModal } from "./StudentEnrollModal";

interface Props {
  cohortId: string;
  onChanged: () => void;
}

export function CohortEnrollments({ cohortId, onChanged }: Props) {
  const { user } = useAuth();
  const canCreate = user?.role === "admin" || user?.role === "designer";

  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<Enrollment[]>(`/cohorts/${cohortId}/enrollments`);
      setEnrollments(data);
    } finally {
      setLoading(false);
    }
  }, [cohortId]);

  useEffect(() => {
    load();
  }, [load]);

  const enrolledIds = new Set(enrollments.map((e) => e.student_id));

  async function removeEnrollment(studentIdToRemove: string) {
    if (!confirm("Remover este aluno da turma?")) return;
    setRemovingId(studentIdToRemove);
    try {
      await api.delete(`/cohorts/${cohortId}/enrollments/${studentIdToRemove}`);
      await load();
      onChanged();
    } finally {
      setRemovingId(null);
    }
  }

  if (loading) return <p className="muted">Carregando alunos…</p>;

  return (
    <section className="cohort-students">
      <div className="cohort-students__toolbar">
        <p className="muted cohort-students__hint">
          Alunos matriculados nesta turma. O andamento na trilha é compartilhado por todos.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => setModalOpen(true)}>
          Adicionar aluno
        </button>
      </div>

      {enrollments.length === 0 ? (
        <div className="empty-state cohort-students__empty">
          <p>Nenhum aluno matriculado ainda.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            Use o botão acima para matricular ou cadastrar alunos.
          </p>
        </div>
      ) : (
        <ul className="cohort-students__list">
          {enrollments.map((e) => (
            <li key={e.id} className="cohort-students__item">
              <div className="cohort-students__item-main">
                <span className="cohort-students__name">{e.student_name}</span>
                <span className="muted cohort-students__email">{e.student_email}</span>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={removingId === e.student_id}
                onClick={() => removeEnrollment(e.student_id)}
              >
                {removingId === e.student_id ? "Removendo…" : "Remover"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <StudentEnrollModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        cohortId={cohortId}
        enrolledIds={enrolledIds}
        canCreate={canCreate}
        onEnrolled={() => {
          load();
          onChanged();
        }}
      />
    </section>
  );
}
