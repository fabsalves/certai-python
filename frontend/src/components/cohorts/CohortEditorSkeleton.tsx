import { EditorLayoutSkeleton } from "../ui/EditorLayoutSkeleton";

interface Props {
  tabCount?: number;
}

export function CohortEditorSkeleton({ tabCount = 3 }: Props) {
  return (
    <EditorLayoutSkeleton
      label="Carregando turma…"
      tabCount={tabCount}
      className="track-editor cohort-editor"
    />
  );
}
