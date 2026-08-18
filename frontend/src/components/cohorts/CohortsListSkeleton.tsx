import { PageHeader } from "../layout/PageHeader";
import { ListTableSkeleton } from "../ui/ListTableSkeleton";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

interface Props {
  canManage: boolean;
}

export function CohortsListSkeleton({ canManage }: Props) {
  return (
    <SkeletonStatus label="Carregando turmas…">
      <PageHeader
        title={canManage ? "Turmas" : "Minhas turmas"}
        description={
          canManage
            ? "Organize turmas por trilha, matricule alunos e acompanhe o andamento."
            : "Confirme quando a turma terminou uma aula para liberar a seguinte."
        }
        actions={
          canManage ? <Skeleton variant="rect" width={120} height={40} /> : undefined
        }
      />

      <ListTableSkeleton rows={4} columns={canManage ? 5 : 4} />
    </SkeletonStatus>
  );
}
