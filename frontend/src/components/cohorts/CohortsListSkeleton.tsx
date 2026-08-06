import { PageHeader } from "../layout/PageHeader";
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

      <div className="cohorts-list">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="card cohorts-list__item cohorts-list-skeleton__item"
          >
            <div className="cohorts-list__head">
              <div style={{ flex: 1, minWidth: 0 }}>
                <Skeleton variant="text" width="55%" height={22} />
                <div style={{ marginTop: 8 }}>
                  <Skeleton variant="text" width="42%" height={14} />
                </div>
              </div>
              {canManage && <Skeleton variant="rect" width={96} height={24} />}
            </div>
            <div style={{ marginTop: 12 }}>
              <Skeleton variant="text" width="32%" height={13} />
            </div>
          </div>
        ))}
      </div>
    </SkeletonStatus>
  );
}
