import { useCallback, useEffect, useMemo, useState } from "react";
import { maskPhoneBR } from "../../lib/validation";
import { api } from "../../lib/api";
import type { Enrollment } from "../../lib/cohorts";
import { useAuth } from "../../lib/auth";
import { useConfirm } from "../../lib/confirm";
import { useApiAction } from "../../lib/useApiAction";
import { StudentEnrollModal } from "./StudentEnrollModal";

interface Props {
  cohortId: string;
  onChanged: () => void;
}

export function CohortEnrollments({ cohortId, onChanged }: Props) {
  const { user } = useAuth();
  const confirm = useConfirm();
  const runAction = useApiAction();
  const canCreate = user?.role === "admin" || user?.role === "designer";

  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

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

  const sortedEnrollments = useMemo(
    () =>
      [...enrollments].sort((a, b) =>
        a.student_name.localeCompare(b.student_name, "pt-BR"),
      ),
    [enrollments],
  );

  const enrolledIds = new Set(sortedEnrollments.map((e) => e.student_id));

  const filteredEnrollments = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sortedEnrollments;
    return sortedEnrollments.filter(
      (e) =>
        e.student_name.toLowerCase().includes(q) ||
        e.student_email.toLowerCase().includes(q),
    );
  }, [sortedEnrollments, query]);

  async function removeEnrollment(studentIdToRemove: string) {
    const enrollment = sortedEnrollments.find((e) => e.student_id === studentIdToRemove);
    const ok = await confirm({
      title: "Remover aluno",
      message: "Remover este aluno da turma?",
      confirmLabel: "Remover",
      tone: "danger",
    });
    if (!ok) return;
    setRemovingId(studentIdToRemove);
    await runAction({
      run: () => api.delete(`/cohorts/${cohortId}/enrollments/${studentIdToRemove}`),
      successMessage: enrollment
        ? `${enrollment.student_name} removido(a) da turma.`
        : "Aluno removido da turma.",
      errorMessage: "Não foi possível remover o aluno.",
      onSuccess: async () => {
        await load();
        onChanged();
      },
    });
    setRemovingId(null);
  }

  if (loading) return <p className="muted">Carregando alunos…</p>;

  return (
    <section className="cohort-students">
      <div className="cohort-students__toolbar">
        <p className="muted cohort-students__hint">
          Alunos matriculados nesta turma. O andamento na trilha é compartilhado por todos.
        </p>
        <button type="button" className="btn btn-primary" onClick={() => setModalOpen(true)}>
          Adicionar alunos
        </button>
      </div>

      {sortedEnrollments.length === 0 ? (
        <div className="empty-state cohort-students__empty">
          <p>Nenhum aluno matriculado ainda.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            Use o botão acima para matricular ou cadastrar alunos.
          </p>
        </div>
      ) : (
        <>
          <div className="field cohort-students__search">
            <label htmlFor="cohort-students-search">Buscar</label>
            <input
              id="cohort-students-search"
              className="input"
              value={query}
              onChange={(ev) => setQuery(ev.target.value)}
              placeholder="Nome ou e-mail…"
            />
          </div>

          {filteredEnrollments.length === 0 ? (
            <p className="muted cohort-students__filter-empty">Nenhum aluno encontrado.</p>
          ) : (
            <ul className="cohort-students__list">
              {filteredEnrollments.map((e) => (
                <li key={e.id} className="cohort-students__item">
                  <div className="cohort-students__item-main">
                    <span className="cohort-students__name">{e.student_name}</span>
                    <span className="muted cohort-students__email">{e.student_email}</span>
                    {e.student_whatsapp && (
                      <span className="muted cohort-students__email">
                        WhatsApp: {maskPhoneBR(e.student_whatsapp.replace(/^55/, ""))}
                      </span>
                    )}
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
        </>
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
