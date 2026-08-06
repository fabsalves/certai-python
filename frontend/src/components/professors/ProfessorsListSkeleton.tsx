import { PageHeader } from "../layout/PageHeader";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function ProfessorsListSkeleton() {
  return (
    <SkeletonStatus label="Carregando professores…">
      <PageHeader
        title="Professores"
        description="Contas de quem leciona e encerra aulas das turmas."
        actions={<Skeleton variant="rect" width={140} height={40} />}
      />

      <ul className="professors-list">
        {Array.from({ length: 5 }).map((_, index) => (
          <li key={index} className="card professors-list__item list-skeleton-card">
            <div style={{ flex: 1, minWidth: 0 }}>
              <Skeleton variant="text" width="42%" height={18} />
              <div style={{ marginTop: 8 }}>
                <Skeleton variant="text" width="55%" height={14} />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </SkeletonStatus>
  );
}
