import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { ProfessorCreateModal } from "../components/cohorts/ProfessorCreateModal";
import { ProfessorEditModal } from "../components/cohorts/ProfessorEditModal";
import { ProfessorsListSkeleton } from "../components/professors/ProfessorsListSkeleton";
import { PageHeader } from "../components/layout/PageHeader";
import type { UserOption } from "../lib/users";

export function Professors() {
  const [professors, setProfessors] = useState<UserOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProfessor, setEditingProfessor] = useState<UserOption | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<UserOption[]>("/users", { params: { role: "professor" } })
      .then(({ data }) => setProfessors(data))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return <ProfessorsListSkeleton />;
  }

  return (
    <>
      <PageHeader
        title="Professores"
        description="Contas de quem leciona e encerra aulas das turmas."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setModalOpen(true)}>
            Novo professor
          </button>
        }
      />

      {professors.length === 0 && (
        <div className="card empty-state">
          <p>Nenhum professor cadastrado.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            Crie a conta para atribuir às turmas.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            style={{ marginTop: 20 }}
            onClick={() => setModalOpen(true)}
          >
            Novo professor
          </button>
        </div>
      )}

      {professors.length > 0 && (
        <ul className="professors-list">
          {professors.map((p) => (
            <li key={p.id} className="card professors-list__item">
              <div>
                <div className="professors-list__name">{p.name}</div>
                <div className="muted professors-list__email">{p.email}</div>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm professors-list__edit"
                onClick={() => setEditingProfessor(p)}
              >
                Editar
              </button>
            </li>
          ))}
        </ul>
      )}

      <ProfessorCreateModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={() => load()}
      />

      {editingProfessor && (
        <ProfessorEditModal
          open={Boolean(editingProfessor)}
          onClose={() => setEditingProfessor(null)}
          professorId={editingProfessor.id}
          professorName={editingProfessor.name}
          professorEmail={editingProfessor.email}
          onUpdated={(updated) => {
            setProfessors((current) =>
              current.map((p) => (p.id === updated.id ? updated : p)),
            );
            setEditingProfessor(null);
          }}
        />
      )}
    </>
  );
}
