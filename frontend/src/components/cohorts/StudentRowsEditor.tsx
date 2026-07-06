import {
  isNonEmpty,
  isValidPhoneBR,
  maskPhoneBR,
  normalizedEmail,
  trimmed,
} from "../../lib/validation";
import type { StudentDraft } from "../../lib/users";

export interface StudentDraftFieldErrors {
  name?: string;
  email?: string;
  whatsapp?: string;
}

export function isRowEmpty(row: StudentDraft): boolean {
  return !trimmed(row.name) && !trimmed(row.email) && !trimmed(row.whatsapp);
}

export function validateStudentDraftFields(
  row: StudentDraft,
  { allowEmpty = false }: { allowEmpty?: boolean } = {},
): StudentDraftFieldErrors {
  if (allowEmpty && isRowEmpty(row)) return {};

  const errors: StudentDraftFieldErrors = {};
  if (!isNonEmpty(row.name)) errors.name = "Obrigatório";
  if (!isNonEmpty(row.email)) {
    errors.email = "Obrigatório";
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail(row.email))) {
    errors.email = "Inválido";
  }
  if (!isNonEmpty(row.whatsapp)) {
    errors.whatsapp = "Obrigatório";
  } else if (!isValidPhoneBR(row.whatsapp)) {
    errors.whatsapp = "Inválido";
  }
  return errors;
}

export function validateStudentDraft(row: StudentDraft): string[] {
  const fields = validateStudentDraftFields(row);
  return Object.values(fields).filter(Boolean) as string[];
}

export function nonEmptyRows(rows: StudentDraft[]): StudentDraft[] {
  return rows.filter((row) => !isRowEmpty(row));
}

export function allDraftsValid(rows: StudentDraft[]): boolean {
  const filled = nonEmptyRows(rows);
  return filled.length > 0 && filled.every((row) => validateStudentDraft(row).length === 0);
}

interface Props {
  rows: StudentDraft[];
  onChange: (rows: StudentDraft[]) => void;
  onAddRow: () => void;
  emptyLabel?: string;
}

function FieldCell({
  id,
  value,
  type = "text",
  inputMode,
  placeholder,
  error,
  onChange,
}: {
  id: string;
  value: string;
  type?: string;
  inputMode?: "numeric" | "text" | "email" | "tel";
  placeholder?: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="student-rows__cell-field">
      <input
        id={id}
        type={type}
        inputMode={inputMode}
        className={`input student-rows__input${error ? " is-invalid" : ""}`}
        value={value}
        placeholder={placeholder}
        onChange={(ev) => onChange(ev.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error && (
        <span id={`${id}-error`} className="student-rows__field-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

export function StudentRowsEditor({
  rows,
  onChange,
  onAddRow,
  emptyLabel = "Nenhum aluno na lista.",
}: Props) {
  function updateRow(id: string, patch: Partial<StudentDraft>) {
    onChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  function removeRow(id: string) {
    onChange(rows.filter((row) => row.id !== id));
  }

  const filledRows = nonEmptyRows(rows);
  const invalidCount = filledRows.filter(
    (row) => Object.keys(validateStudentDraftFields(row)).length > 0,
  ).length;

  return (
    <div className="student-rows">
      <div className="student-rows__head">
        <h3 className="student-rows__title">Lista de alunos</h3>
        <div className="student-rows__toolbar">
          <span className="student-rows__count">
            {filledRows.length} aluno(s)
            {invalidCount > 0 ? ` · ${invalidCount} com pendência` : ""}
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onAddRow}>
            + Adicionar linha
          </button>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="student-rows__empty">
          <p className="muted">{emptyLabel}</p>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onAddRow}>
            + Adicionar linha
          </button>
        </div>
      ) : (
        <div className="student-rows__table-wrap">
          <table className="student-rows__table">
            <thead>
              <tr>
                <th scope="col" className="student-rows__col-index" aria-label="Linha" />
                <th scope="col">Nome</th>
                <th scope="col">E-mail</th>
                <th scope="col">WhatsApp</th>
                <th scope="col" className="student-rows__col-action" aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const errors = validateStudentDraftFields(row, { allowEmpty: true });
                const hasErrors = Object.keys(errors).length > 0;
                return (
                  <tr key={row.id} className={hasErrors ? "has-error" : undefined}>
                    <td className="student-rows__col-index">{index + 1}</td>
                    <td>
                      <FieldCell
                        id={`student-name-${row.id}`}
                        value={row.name}
                        placeholder="Nome completo"
                        error={errors.name}
                        onChange={(name) => updateRow(row.id, { name })}
                      />
                    </td>
                    <td>
                      <FieldCell
                        id={`student-email-${row.id}`}
                        type="email"
                        value={row.email}
                        placeholder="email@exemplo.com"
                        error={errors.email}
                        onChange={(email) => updateRow(row.id, { email })}
                      />
                    </td>
                    <td>
                      <FieldCell
                        id={`student-whatsapp-${row.id}`}
                        type="tel"
                        inputMode="numeric"
                        value={row.whatsapp}
                        placeholder="(11) 98765-4321"
                        error={errors.whatsapp}
                        onChange={(whatsapp) =>
                          updateRow(row.id, { whatsapp: maskPhoneBR(whatsapp) })
                        }
                      />
                    </td>
                    <td className="student-rows__col-action">
                      <button
                        type="button"
                        className="student-rows__remove"
                        onClick={() => removeRow(row.id)}
                        aria-label={`Remover aluno ${index + 1}`}
                        title="Remover"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function draftsFromBulkItems(
  items: Array<{ name: string; email: string; whatsapp: string }>,
): StudentDraft[] {
  return items.map((item, index) => ({
    id: `import-${index}-${crypto.randomUUID()}`,
    name: trimmed(item.name),
    email: trimmed(item.email),
    whatsapp: item.whatsapp ? maskPhoneBR(item.whatsapp) : "",
  }));
}
