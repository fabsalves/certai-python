import { PageHeader } from "../layout/PageHeader";
import { ListTableSkeleton } from "../ui/ListTableSkeleton";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function CostsListSkeleton({
  title = "Custos",
  description = "Consumo de IA medido por turma, aluno e aula.",
  columns = 6,
}: {
  title?: string;
  description?: string;
  columns?: number;
}) {
  return (
    <SkeletonStatus label="Carregando custos…">
      <PageHeader
        title={title}
        description={description}
        actions={<Skeleton variant="rect" width={140} height={40} />}
      />
      <div className="page-grid page-grid--stats" style={{ marginBottom: 24 }}>
        {[0, 1, 2].map((index) => (
          <div key={index} className="card stat-card">
            <Skeleton variant="text" width="60%" height={12} />
            <Skeleton variant="text" width="45%" height={26} />
          </div>
        ))}
      </div>
      <ListTableSkeleton rows={5} columns={columns} />
    </SkeletonStatus>
  );
}
