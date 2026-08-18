import { PageHeader } from "../layout/PageHeader";
import { ListTableSkeleton } from "../ui/ListTableSkeleton";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function ProfessorsListSkeleton() {
  return (
    <SkeletonStatus label="Carregando professores…">
      <PageHeader
        title="Professores"
        description="Contas de quem leciona e encerra aulas das turmas."
        actions={<Skeleton variant="rect" width={140} height={40} />}
      />

      <ListTableSkeleton rows={5} columns={3} />
    </SkeletonStatus>
  );
}
