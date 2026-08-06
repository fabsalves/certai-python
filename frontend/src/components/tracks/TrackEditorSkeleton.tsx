import { EditorLayoutSkeleton } from "../ui/EditorLayoutSkeleton";

export function TrackEditorSkeleton() {
  return (
    <EditorLayoutSkeleton
      label="Carregando trilha…"
      tabCount={2}
      className="track-editor"
    />
  );
}
