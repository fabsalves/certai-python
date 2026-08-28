import { PageHeader } from "../layout/PageHeader";
import { ListTableSkeleton } from "../ui/ListTableSkeleton";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

interface Props {
  title: string;
  description: string;
  columns?: number;
}

export function AdminPageSkeleton({ title, description, columns = 5 }: Props) {
  return (
    <SkeletonStatus label="Carregando…">
      <PageHeader
        title={title}
        description={description}
        actions={<Skeleton variant="rect" width={160} height={40} />}
      />
      <ListTableSkeleton rows={5} columns={columns} />
    </SkeletonStatus>
  );
}
