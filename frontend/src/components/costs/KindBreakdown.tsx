import { useMemo } from "react";
import { DataTable, type DataColumn } from "../ui/DataTable";
import {
  formatMinutes,
  formatTokens,
  formatUsd,
  type KindBreakdown as KindBreakdownRow,
} from "../../lib/costs";

/**
 * Onde o dinheiro foi, por tipo de gasto. É a tabela que responde *por que*
 * custou — áudio de saída pesa ~80x mais que o mesmo volume em cache.
 */
export function KindBreakdown({ rows }: { rows: KindBreakdownRow[] }) {
  const columns = useMemo<DataColumn<KindBreakdownRow>[]>(
    () => [
      {
        id: "label",
        header: "Tipo de gasto",
        primary: true,
        render: (row) => <span className="table__primary">{row.label}</span>,
      },
      {
        id: "provider",
        header: "Provedor",
        render: (row) => row.provider,
      },
      {
        id: "tokens",
        header: "Tokens",
        align: "end",
        render: (row) => formatTokens(row.total_tokens),
      },
      {
        id: "minutes",
        header: "Tempo (est.)",
        align: "end",
        render: (row) => formatMinutes(row.voice_minutes_est),
      },
      {
        id: "usd",
        header: "Custo",
        align: "end",
        render: (row) =>
          row.unpriced_events > 0 && row.cost_usd === 0 ? (
            <span className="muted" title="Modelo sem tarifa conhecida">
              sem tarifa
            </span>
          ) : (
            formatUsd(row.cost_usd)
          ),
      },
    ],
    [],
  );

  if (rows.length === 0) return null;

  return (
    <section className="card" style={{ padding: 20, marginBottom: 24 }}>
      <h3 style={{ marginBottom: 12 }}>Por tipo de gasto</h3>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => `${row.provider}:${row.cost_kind}`}
        aria-label="Custos por tipo de gasto"
      />
    </section>
  );
}
