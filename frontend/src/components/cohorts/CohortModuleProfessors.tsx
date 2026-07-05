import type { FormEvent } from "react";
import type { ProfessorOption } from "../../lib/cohorts";
import { levelLabel, type Module } from "../../lib/tracks";
import { Select } from "../ui/Select";

interface Props {
  modules: Module[];
  professors: ProfessorOption[];
  assignments: Record<string, string>;
  trackTitle?: string;
  isNew?: boolean;
  saving?: boolean;
  dirty?: boolean;
  error?: string;
  onAssignmentChange: (moduleId: string, professorId: string) => void;
  onCreateProfessor: () => void;
  onSubmit: (e?: FormEvent) => void;
}

export function CohortModuleProfessors({
  modules,
  professors,
  assignments,
  trackTitle,
  isNew = false,
  saving = false,
  dirty = false,
  error,
  onAssignmentChange,
  onCreateProfessor,
  onSubmit,
}: Props) {
  const allAssigned = modules.every((mod) => Boolean(assignments[mod.id]));

  return (
    <form className="cohort-professors" onSubmit={onSubmit}>
      <div className="cohort-professors__toolbar">
        <p className="muted cohort-professors__hint">
          {trackTitle
            ? `Trilha «${trackTitle}» · um professor por módulo ativo.`
            : "Defina quem leciona cada módulo da trilha."}
        </p>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onCreateProfessor}>
          + Novo professor
        </button>
      </div>

      {modules.length === 0 ? (
        <div className="empty-state cohort-professors__empty">
          <p>A trilha selecionada ainda não possui módulos ativos.</p>
        </div>
      ) : (
        <ul className="cohort-professors__list">
          {modules.map((mod) => (
            <li key={mod.id} className="cohort-professors__item">
              <div className="cohort-professors__item-main">
                <span className="cohort-professors__module-name">{mod.title}</span>
                <span className="muted cohort-professors__module-level">{levelLabel(mod.level)}</span>
              </div>
              <Select
                value={assignments[mod.id] ?? ""}
                options={professors.map((prof) => ({ value: prof.id, label: prof.name }))}
                onChange={(professorId) => onAssignmentChange(mod.id, professorId)}
                disabled={professors.length === 0}
                placeholder="Selecione o professor…"
                required
                className="cohort-professors__select"
                aria-label={`Professor do módulo ${mod.title}`}
              />
            </li>
          ))}
        </ul>
      )}

      {error && <div className="form-error">{error}</div>}

      {(isNew || dirty) && (
        <button
          type="submit"
          className="btn btn-primary"
          disabled={saving || !allAssigned || modules.length === 0}
        >
          {saving ? "Salvando…" : isNew ? "Criar turma" : "Salvar professores"}
        </button>
      )}
    </form>
  );
}
