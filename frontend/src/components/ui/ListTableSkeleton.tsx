import { Skeleton } from "./Skeleton";

interface Props {
  rows?: number;
  columns?: number;
}

export function ListTableSkeleton({ rows = 5, columns = 4 }: Props) {
  return (
    <div className="table-wrap list-table-skeleton" aria-hidden>
      <table className="table">
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, index) => (
              <th key={index}>
                <Skeleton variant="text" width={`${48 + index * 8}%`} height={12} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr key={rowIndex}>
              {Array.from({ length: columns }).map((_, colIndex) => (
                <td key={colIndex}>
                  <Skeleton
                    variant="text"
                    width={`${55 + ((rowIndex + colIndex) % 3) * 12}%`}
                    height={14}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
