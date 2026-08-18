import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useListView } from "../lib/useListView";
import { ProfessorCreateModal } from "../components/cohorts/ProfessorCreateModal";
import { ProfessorEditModal } from "../components/cohorts/ProfessorEditModal";
import { ProfessorsListSkeleton } from "../components/professors/ProfessorsListSkeleton";
import { PageHeader } from "../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../components/ui/DataTable";
import { ViewToggle } from "../components/ui/ViewToggle";
import type { UserOption } from "../lib/users";

export function Professors() {
  const [view, setView] = useListView("professors");
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

  const columns = useMemo<DataColumn<UserOption>[]>(
    () => [
      {
        id: "name",
        header: "Nome",
        primary: true,
        render: (professor) => (
          <span className="table__primary">{professor.name}</span>
        ),
      },
      {
        id: "email",
        header: "E-mail",
        render: (professor) => professor.email,
      },
      {
        id: "actions",
        header: "",
        card: "actions",
        align: "end",
        render: (professor) => (
          <div className="table__actions">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setEditingProfessor(professor)}
            >
              Editar
            </button>
          </div>
        ),
      },
    ],
    [],
  );

  if (loading) {
    return <ProfessorsListSkeleton />;
  }

  return (
    <>
      <PageHeader
        title="Professores"
        description="Contas de quem leciona e encerra aulas das turmas."
        actions={
          <>
            {professors.length > 0 && <ViewToggle value={view} onChange={setView} />}
            <button type="button" className="btn btn-primary" onClick={() => setModalOpen(true)}>
              Novo professor
            </button>
          </>
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
        <DataTable
          columns={columns}
          rows={professors}
          rowKey={(professor) => professor.id}
          layout={view}
          aria-label="Professores"
        />
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
