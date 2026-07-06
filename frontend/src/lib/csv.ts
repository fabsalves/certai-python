import type { StudentBulkItemInput } from "./users";
import { maskPhoneBR, trimmed } from "./validation";

function formatImportedWhatsapp(value: string): string {
  const raw = trimmed(value);
  if (!raw) return "";
  return maskPhoneBR(raw);
}

const HEADER_ALIASES: Record<string, keyof StudentBulkItemInput> = {
  nome: "name",
  name: "name",
  email: "email",
  "e-mail": "email",
  whatsapp: "whatsapp",
  telefone: "whatsapp",
  phone: "whatsapp",
};

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      cells.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }

  cells.push(current.trim());
  return cells;
}

export function parseStudentsCsv(text: string): StudentBulkItemInput[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length === 0) return [];

  const firstCells = parseCsvLine(lines[0]).map((cell) => cell.toLowerCase());
  const isHeader = firstCells.some((cell) => cell in HEADER_ALIASES);

  let startIdx = 0;
  const colMap: Partial<Record<keyof StudentBulkItemInput, number>> = {};

  if (isHeader) {
    firstCells.forEach((cell, index) => {
      const key = HEADER_ALIASES[cell];
      if (key) colMap[key] = index;
    });
    startIdx = 1;
  } else {
    colMap.name = 0;
    colMap.email = 1;
    colMap.whatsapp = 2;
  }

  const rows: StudentBulkItemInput[] = [];
  for (let i = startIdx; i < lines.length; i += 1) {
    const cells = parseCsvLine(lines[i]);
    if (cells.every((cell) => !cell.trim())) continue;

    rows.push({
      name: cells[colMap.name ?? 0] ?? "",
      email: cells[colMap.email ?? 1] ?? "",
      whatsapp: formatImportedWhatsapp(cells[colMap.whatsapp ?? 2] ?? ""),
    });
  }

  return rows;
}

export const STUDENT_CSV_TEMPLATE =
  "nome,email,whatsapp\nJoão Silva,joao@example.com,(11) 98765-4321\n";

export function downloadStudentCsvTemplate(): void {
  const blob = new Blob([STUDENT_CSV_TEMPLATE], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "alunos-modelo.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}
