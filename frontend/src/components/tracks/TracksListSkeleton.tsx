import { PageHeader } from "../layout/PageHeader";
import { ListTableSkeleton } from "../ui/ListTableSkeleton";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function TracksListSkeleton() {
  return (
    <SkeletonStatus label="Carregando trilhas…">
      <PageHeader
        title="Trilhas"
        description="Monte o percurso completo: trilha, módulos com nível e aulas em sequência."
        actions={<Skeleton variant="rect" width={120} height={40} />}
      />

      <ListTableSkeleton rows={4} columns={5} />
    </SkeletonStatus>
  );
}
