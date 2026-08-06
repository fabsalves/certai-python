import { type FormEvent, useState } from "react";
import type {
  Enrollment,
  ModuleAssignments,
  ModuleClassDraft,
  ProfessorOption,
} from "../../lib/cohorts";
import { unassignedStudentIds } from "../../lib/cohorts";
import { levelLabel, type Module } from "../../lib/tracks";
import { Select } from "../ui/Select";
import { ModuleClassDivisionModal } from "./ModuleClassDivisionModal";

interface Props {
  modules: Module[];
  professors: ProfessorOption[];
  assignments: ModuleAssignments;
  enrollments: Enrollment[];
  trackTitle?: string;
  isNew?: boolean;
  saving?: boolean;
  dirty?: boolean;
  error?: string;
  onProfessorChange: (moduleId: string, index: number, professorId: string) => void;
  onAddProfessor: (moduleId: string) => void;
  onRemoveProfessor: (moduleId: string, index: number) => void;
  /** Apply division locally (new cohort) or persist (existing). Return false to keep modal open. */
  onApplyDivision: (
    moduleId: string,
    classes: ModuleClassDraft[],
  ) => boolean | Promise<boolean>;
  onCreateProfessor: () => void;
  onSubmit: (e?: FormEvent) => void;
}

function professorLabel(
  professors: ProfessorOption[],
  professorId: string,
): string {
  return professors.find((item) => item.id === professorId)?.name ?? "Professor";
}

export function CohortModuleProfessors({
  modules,
  professors,
  assignments,
  enrollments,
  trackTitle,
  isNew = false,
  saving = false,
  dirty = false,
  error,
  onProfessorChange,
  onAddProfessor,
  onRemoveProfessor,
  onApplyDivision,
  onCreateProfessor,
  onSubmit,
}: Props) {
  const enrolledIds = enrollments.map((item) => item.student_id);
  const allAssigned = modules.every((mod) =>
    (assignments[mod.id] ?? []).some((item) => Boolean(item.professorId)),
  );
  const professorOptions = professors.map((prof) => ({
    value: prof.id,
    label: prof.name,
  }));

  const [divisionModuleId, setDivisionModuleId] = useState<string | null>(null);
  const divisionModule = modules.find((mod) => mod.id === divisionModuleId) ?? null;
  const divisionIndex = divisionModule
    ? modules.findIndex((mod) => mod.id === divisionModule.id)
    : -1;
  const previousModuleId =
    divisionIndex > 0 ? modules[divisionIndex - 1].id : null;

  return (
    <form className="cohort-professors" onSubmit={onSubmit}>
      <div className="cohort-professors__toolbar">
        <p className="muted cohort-professors__hint">
          {trackTitle
            ? `Trilha «${trackTitle}» · ao menos um professor por módulo ativo.`
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
          {modules.map((mod) => {
            const classes = assignments[mod.id] ?? [];
            const split = classes.length > 1;
            const pending = unassignedStudentIds(classes, enrolledIds);
            const assignedCount = enrolledIds.length - pending.length;

            return (
              <li key={mod.id} className="cohort-professors__item">
                <div className="cohort-professors__item-head">
                  <div className="cohort-professors__item-main">
                    <span className="cohort-professors__module-name">{mod.title}</span>
                    <span className="muted cohort-professors__module-level">
                      {levelLabel(mod.level)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => onAddProfessor(mod.id)}
                    disabled={professors.length <= classes.length}
                  >
                    + Professor
                  </button>
                </div>

                <div className="cohort-professors__classes">
                  {classes.map((item, index) => (
                    <div key={`${mod.id}-${index}`} className="cohort-professors__class">
                      <Select
                        value={item.professorId}
                        options={professorOptions}
                        onChange={(professorId) =>
                          onProfessorChange(mod.id, index, professorId)
                        }
                        disabled={professors.length === 0}
                        placeholder="Selecione o professor…"
                        required
                        className="cohort-professors__select"
                        aria-label={`Professor ${index + 1} do módulo ${mod.title}`}
                      />
                      {split && (
                        <span className="muted cohort-professors__class-count">
                          {item.studentIds.length} aluno(s)
                        </span>
                      )}
                      {classes.length > 1 && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => onRemoveProfessor(mod.id, index)}
                          aria-label={`Remover professor ${index + 1} do módulo ${mod.title}`}
                        >
                          Remover
                        </button>
                      )}
                    </div>
                  ))}
                </div>

                {split && (
                  <div className="cohort-professors__division">
                    {enrollments.length === 0 ? (
                      <p className="muted">
                        Sem alunos matriculados. Faça a divisão depois de matricular.
                      </p>
                    ) : (
                      <>
                        <div className="cohort-professors__division-summary">
                          <p className="muted cohort-professors__division-title">
                            {assignedCount}/{enrollments.length} aluno(s) divididos
                            {pending.length > 0
                              ? ` · ${pending.length} sem grupo`
                              : ""}
                          </p>
                          <ul className="cohort-professors__division-counts">
                            {classes
                              .filter((item) => item.professorId)
                              .map((item) => (
                                <li key={item.professorId}>
                                  <span>
                                    {professorLabel(professors, item.professorId)}
                                  </span>
                                  <span className="muted">
                                    {item.studentIds.length}
                                  </span>
                                </li>
                              ))}
                          </ul>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => setDivisionModuleId(mod.id)}
                          >
                            Dividir alunos
                          </button>
                        </div>
                        {pending.length > 0 && (
                          <p className="cohort-professors__warning">
                            {pending.length} aluno(s) sem professor. O encerramento das
                            aulas deste módulo fica bloqueado até a divisão terminar.
                          </p>
                        )}
                      </>
                    )}
                  </div>
                )}
              </li>
            );
          })}
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

      {divisionModule && (
        <ModuleClassDivisionModal
          open
          moduleTitle={divisionModule.title}
          classes={assignments[divisionModule.id] ?? []}
          enrollments={enrollments}
          professors={professors}
          previousClasses={
            previousModuleId ? (assignments[previousModuleId] ?? []) : []
          }
          persist={!isNew}
          busy={saving}
          onClose={() => setDivisionModuleId(null)}
          onApply={async (next) => {
            const ok = await onApplyDivision(divisionModule.id, next);
            if (ok) setDivisionModuleId(null);
          }}
        />
      )}
    </form>
  );
}
