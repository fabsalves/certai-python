import { type ChangeEvent, type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Modal } from "../ui/Modal";
import { api } from "../../lib/api";
import { downloadStudentCsvTemplate, parseStudentsCsv } from "../../lib/csv";
import type { StudentBulkResult, UserCreateInput, UserOption } from "../../lib/users";
import { emptyStudentDraft } from "../../lib/users";
import { useFeedback } from "../../lib/feedback";
import { useApiAction } from "../../lib/useApiAction";
import {
  isNonEmpty,
  isValidPhoneBR,
  maskPhoneBR,
  normalizedEmail,
  normalizePhoneForApi,
  trimmed,
} from "../../lib/validation";
import {
  allDraftsValid,
  draftsFromBulkItems,
  nonEmptyRows,
  StudentRowsEditor,
} from "./StudentRowsEditor";
import type { StudentDraft } from "../../lib/users";

interface Props {
  open: boolean;
  onClose: () => void;
  cohortId: string;
  enrolledIds: Set<string>;
  canCreate: boolean;
  onEnrolled: () => void;
}

type CreateMode = "single" | "batch";

interface EnrollmentBulkResult {
  enrolled_count: number;
  skipped_count: number;
}

function buildBulkSuccessMessage(
  bulk: StudentBulkResult,
  enrolledCount: number,
  skippedEnroll: number,
): string {
  const parts: string[] = [];
  if (bulk.created.length > 0) parts.push(`${bulk.created.length} criado(s)`);
  if (bulk.reused_ids.length > 0) parts.push(`${bulk.reused_ids.length} já existente(s)`);
  if (bulk.skipped.length > 0) parts.push(`${bulk.skipped.length} ignorado(s)`);
  if (enrolledCount > 0) parts.push(`${enrolledCount} matriculado(s)`);
  if (skippedEnroll > 0) parts.push(`${skippedEnroll} já matriculado(s)`);
  return parts.length > 0 ? `${parts.join(", ")}.` : "Nenhuma alteração realizada.";
}

export function StudentEnrollModal({
  open,
  onClose,
  cohortId,
  enrolledIds,
  canCreate,
  onEnrolled,
}: Props) {
  const runAction = useApiAction();
  const feedback = useFeedback();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [students, setStudents] = useState<UserOption[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [mode, setMode] = useState<"enroll" | "create">("enroll");
  const [createMode, setCreateMode] = useState<CreateMode>("single");

  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newWhatsapp, setNewWhatsapp] = useState("");
  const [batchPassword, setBatchPassword] = useState("");
  const [batchRows, setBatchRows] = useState<StudentDraft[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMode("enroll");
    setCreateMode("single");
    setQuery("");
    setSelectedIds(new Set());
    setBatchRows([]);
    setBatchPassword("");
    setNewName("");
    setNewEmail("");
    setNewPassword("");
    setNewWhatsapp("");
    setLoadingStudents(true);
    api
      .get<UserOption[]>("/users", { params: { role: "student" } })
      .then(({ data }) => setStudents(data))
      .finally(() => setLoadingStudents(false));
  }, [open]);

  function resetAndClose() {
    setNewName("");
    setNewEmail("");
    setNewPassword("");
    setNewWhatsapp("");
    setBatchPassword("");
    setBatchRows([]);
    setQuery("");
    setSelectedIds(new Set());
    onClose();
  }

  function switchCreateMode(next: CreateMode) {
    setCreateMode(next);
  }

  function appendBatchRow() {
    setBatchRows((current) => [...current, emptyStudentDraft()]);
  }

  const availableStudents = useMemo(
    () =>
      students
        .filter((s) => !enrolledIds.has(s.id))
        .sort((a, b) => a.name.localeCompare(b.name, "pt-BR")),
    [students, enrolledIds],
  );

  const filteredStudents = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? availableStudents.filter(
          (s) => s.name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q),
        )
      : availableStudents;
    return list;
  }, [availableStudents, query]);

  const allFilteredSelected =
    filteredStudents.length > 0 &&
    filteredStudents.every((s) => selectedIds.has(s.id));

  const singleWhatsappValid = isNonEmpty(newWhatsapp) && isValidPhoneBR(newWhatsapp);
  const batchFilledCount = nonEmptyRows(batchRows).length;
  const batchReady = batchPassword.length >= 8 && allDraftsValid(batchRows);

  function toggleStudent(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllFiltered() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        filteredStudents.forEach((s) => next.delete(s.id));
      } else {
        filteredStudents.forEach((s) => next.add(s.id));
      }
      return next;
    });
  }

  async function enrollSelected(e: FormEvent) {
    e.preventDefault();
    const ids = [...selectedIds];
    if (ids.length === 0) return;

    setEnrolling(true);
    await runAction({
      run: () => api.post(`/cohorts/${cohortId}/enrollments/bulk`, { student_ids: ids }),
      successMessage:
        ids.length > 1 ? `${ids.length} alunos matriculados.` : "Aluno matriculado.",
      errorMessage: "Não foi possível matricular os alunos selecionados.",
      onSuccess: () => {
        onEnrolled();
        resetAndClose();
      },
    });
    setEnrolling(false);
  }

  async function createAndEnroll(e: FormEvent) {
    e.preventDefault();
    const nextName = trimmed(newName);
    if (!nextName) {
      feedback.error("Informe o nome do aluno.");
      return;
    }
    const whatsapp = normalizePhoneForApi(newWhatsapp);
    if (!whatsapp || !isValidPhoneBR(whatsapp)) {
      feedback.error("Informe um WhatsApp válido (DDD + número).");
      return;
    }
    setCreating(true);
    await runAction({
      run: async () => {
        const body: UserCreateInput = {
          email: normalizedEmail(newEmail),
          name: nextName,
          password: newPassword,
          role: "student",
          whatsapp,
        };
        const { data: created } = await api.post<UserOption>("/users", body);
        await api.post(`/cohorts/${cohortId}/enrollments`, { student_id: created.id });
        return created;
      },
      successMessage: `${nextName} cadastrado(a) e matriculado(a).`,
      errorMessage: "Não foi possível cadastrar o aluno. Verifique se o e-mail já existe.",
      onSuccess: () => {
        onEnrolled();
        resetAndClose();
      },
    });
    setCreating(false);
  }

  async function bulkCreateAndEnroll(e: FormEvent) {
    e.preventDefault();
    if (batchPassword.length < 8) {
      feedback.error("Senha inicial deve ter ao menos 8 caracteres.");
      return;
    }
    if (!allDraftsValid(batchRows)) {
      feedback.error("Corrija os alunos com pendência antes de continuar.");
      return;
    }

    setCreating(true);
    await runAction({
      run: async () => {
        const studentsPayload = nonEmptyRows(batchRows).map((row) => ({
          name: trimmed(row.name),
          email: normalizedEmail(row.email),
          whatsapp: normalizePhoneForApi(row.whatsapp)!,
        }));
        const { data: bulk } = await api.post<StudentBulkResult>("/users/bulk", {
          password: batchPassword,
          students: studentsPayload,
        });
        const studentIds = [...bulk.created.map((user) => user.id), ...bulk.reused_ids];
        let enrolledCount = 0;
        let skippedEnroll = 0;
        if (studentIds.length > 0) {
          const { data: enrollResult } = await api.post<EnrollmentBulkResult>(
            `/cohorts/${cohortId}/enrollments/bulk`,
            { student_ids: studentIds },
          );
          enrolledCount = enrollResult.enrolled_count;
          skippedEnroll = enrollResult.skipped_count;
        }
        return { bulk, enrolledCount, skippedEnroll };
      },
      successMessage: "",
      errorMessage: "Não foi possível cadastrar os alunos em lote.",
      onSuccess: (result) => {
        if (!result) return;
        feedback.success(
          buildBulkSuccessMessage(result.bulk, result.enrolledCount, result.skippedEnroll),
        );
        onEnrolled();
        resetAndClose();
      },
    });
    setCreating(false);
  }

  function handleCsvUpload(ev: ChangeEvent<HTMLInputElement>) {
    const file = ev.target.files?.[0];
    ev.target.value = "";
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      const parsed = parseStudentsCsv(text);
      if (parsed.length === 0) {
        feedback.error("Nenhum aluno encontrado no arquivo CSV.");
        return;
      }
      setMode("create");
      setCreateMode("batch");
      setBatchRows(draftsFromBulkItems(parsed));
      feedback.success(`${parsed.length} linha(s) importada(s). Revise antes de confirmar.`);
    };
    reader.onerror = () => feedback.error("Não foi possível ler o arquivo CSV.");
    reader.readAsText(file, "utf-8");
  }

  const selectedCount = selectedIds.size;
  const createTitle =
    createMode === "single" ? "Cadastrar aluno" : "Cadastrar alunos em lote";

  return (
    <Modal
      open={open}
      onClose={resetAndClose}
      title={mode === "enroll" ? "Matricular alunos" : createTitle}
      wide
    >
      {mode === "enroll" ? (
        <form className="modal-form" onSubmit={enrollSelected}>
          <div className="modal-form__body">
            <div className="modal-form__content">
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Selecione um ou mais alunos já cadastrados no sistema.
            </p>

            {loadingStudents ? (
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                Carregando…
              </p>
            ) : availableStudents.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>
                Nenhum aluno disponível para matricular.
              </p>
            ) : (
              <>
                <div className="field">
                  <label htmlFor="enroll-search">Buscar</label>
                  <input
                    id="enroll-search"
                    className="input"
                    value={query}
                    onChange={(ev) => setQuery(ev.target.value)}
                    placeholder="Nome ou e-mail…"
                  />
                </div>

                <div className="enroll-picker">
                  <div className="enroll-picker__toolbar">
                    <span className="enroll-picker__count">
                      {selectedCount} selecionado(s)
                    </span>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={toggleAllFiltered}
                      disabled={filteredStudents.length === 0}
                    >
                      {allFilteredSelected ? "Limpar filtro" : "Selecionar filtrados"}
                    </button>
                  </div>

                  <ul className="enroll-picker__list">
                    {filteredStudents.length === 0 ? (
                      <li className="enroll-picker__empty muted">Nenhum aluno encontrado.</li>
                    ) : (
                      filteredStudents.map((student) => {
                        const checked = selectedIds.has(student.id);
                        return (
                          <li key={student.id}>
                            <label className={`enroll-picker__item${checked ? " is-selected" : ""}`}>
                              <input
                                type="checkbox"
                                className="enroll-picker__check"
                                checked={checked}
                                onChange={() => toggleStudent(student.id)}
                              />
                              <span className="enroll-picker__item-main">
                                <span className="enroll-picker__name">{student.name}</span>
                                <span className="muted enroll-picker__email">{student.email}</span>
                              </span>
                            </label>
                          </li>
                        );
                      })
                    )}
                  </ul>
                </div>
              </>
            )}
            </div>
          </div>

          <footer className="modal-form__footer">
            {canCreate && (
              <button type="button" className="modal-form__back" onClick={() => setMode("create")}>
                + Cadastrar novo aluno
              </button>
            )}
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={enrolling || selectedCount === 0}
              >
                {enrolling
                  ? "Matriculando…"
                  : selectedCount > 1
                    ? `Matricular (${selectedCount})`
                    : "Matricular"}
              </button>
            </div>
          </footer>
        </form>
      ) : (
        <form
          className={`modal-form${createMode !== "single" ? " modal-form--batch" : ""}`}
          onSubmit={createMode === "single" ? createAndEnroll : bulkCreateAndEnroll}
        >
          <div className="modal-form__body">
            <div className="modal-form__content">
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>
              Cria a(s) conta(s) e matricula automaticamente nesta turma.
            </p>

            <div className="modal-segment" role="radiogroup" aria-label="Forma de cadastro">
              <button
                type="button"
                className={`modal-segment__btn${createMode === "single" ? " is-active" : ""}`}
                onClick={() => switchCreateMode("single")}
              >
                Um aluno
              </button>
              <button
                type="button"
                className={`modal-segment__btn${createMode === "batch" ? " is-active" : ""}`}
                onClick={() => switchCreateMode("batch")}
              >
                Vários alunos
              </button>
            </div>

          {createMode === "single" ? (
            <>
              <div className="field">
                <label htmlFor="student-name">Nome</label>
                <input
                  id="student-name"
                  className="input"
                  value={newName}
                  onChange={(ev) => setNewName(ev.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="student-email">E-mail</label>
                <input
                  id="student-email"
                  type="email"
                  className="input"
                  value={newEmail}
                  onChange={(ev) => setNewEmail(ev.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="student-password">Senha inicial</label>
                <input
                  id="student-password"
                  type="password"
                  className="input"
                  minLength={8}
                  value={newPassword}
                  onChange={(ev) => setNewPassword(ev.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="student-whatsapp">WhatsApp</label>
                <input
                  id="student-whatsapp"
                  type="tel"
                  className="input"
                  inputMode="numeric"
                  autoComplete="tel"
                  value={newWhatsapp}
                  onChange={(ev) => setNewWhatsapp(maskPhoneBR(ev.target.value))}
                  placeholder="(11) 98765-4321"
                  required
                />
              </div>
            </>
          ) : (
            <div className="student-batch">
              <div className="student-batch__import">
                <div className="student-batch__import-head">
                  <span className="student-batch__import-title">Importar planilha</span>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  className="student-csv-upload__input"
                  onChange={handleCsvUpload}
                />
                <div className="student-batch__import-actions">
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Escolher arquivo CSV
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={downloadStudentCsvTemplate}
                  >
                    Baixar modelo
                  </button>
                </div>
                <p className="muted student-batch__import-hint">
                  Colunas: nome, email, whatsapp
                </p>
              </div>

              <div className="student-batch__divider" role="separator">
                ou preencha manualmente
              </div>

              <div className="field student-batch__password">
                <label htmlFor="batch-password">Senha inicial (todos os alunos)</label>
                <input
                  id="batch-password"
                  type="password"
                  className="input"
                  minLength={8}
                  value={batchPassword}
                  onChange={(ev) => setBatchPassword(ev.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  required
                />
              </div>

              <StudentRowsEditor
                rows={batchRows}
                onChange={setBatchRows}
                onAddRow={appendBatchRow}
                emptyLabel="Importe um CSV ou adicione linhas na tabela."
              />
            </div>
          )}
            </div>
          </div>

          <footer className="modal-form__footer">
            <button type="button" className="modal-form__back" onClick={() => setMode("enroll")}>
              ← Alunos existentes
            </button>
            <div className="modal-form__actions">
              <button type="button" className="btn btn-ghost" onClick={resetAndClose}>
                Cancelar
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={
                  creating ||
                  (createMode === "single"
                    ? !isNonEmpty(newName) || !singleWhatsappValid
                    : !batchReady)
                }
              >
                {creating
                  ? "Cadastrando…"
                  : createMode === "single"
                    ? "Cadastrar"
                    : `Cadastrar (${batchFilledCount})`}
              </button>
            </div>
          </footer>
        </form>
      )}
    </Modal>
  );
}
