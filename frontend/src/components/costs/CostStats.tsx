import type { ReactNode } from "react";

export interface CostStat {
  label: string;
  value: string;
  hint?: string;
}

/**
 * Faixa de indicadores. Cards dividem a linha por igual (2 ocupam 50/50),
 * sem forçar 3 colunas vazias do `page-grid--stats` em desktop.
 */
export function CostStats({ stats }: { stats: CostStat[] }) {
  if (stats.length === 0) return null;

  return (
    <div
      className="cost-stats"
      style={{
        gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))`,
      }}
    >
      {stats.map((stat) => (
        <div key={stat.label} className="card stat-card">
          <div className="stat-card__label">{stat.label}</div>
          <div className="stat-card__value">{stat.value}</div>
          {stat.hint && (
            <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
              {stat.hint}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Aviso de total incompleto. Esconder isto seria pior que não ter a tela:
 * o número exibido deixaria de ser confiável sem que ninguém soubesse.
 */
export function UnpricedWarning({ count }: { count: number }): ReactNode {
  if (count <= 0) return null;
  return (
    <div className="card" style={{ padding: 16, marginBottom: 24 }}>
      <strong>Total incompleto.</strong>{" "}
      <span className="muted">
        {count === 1
          ? "1 chamada usou um modelo sem tarifa cadastrada e não entrou na soma."
          : `${count} chamadas usaram um modelo sem tarifa cadastrada e não entraram na soma.`}{" "}
        Cadastre a tarifa em <code>backend/app/services/usage/pricing.py</code>.
      </span>
    </div>
  );
}
