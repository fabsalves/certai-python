import { useMemo, useState } from "react";
import { TrackPath } from "../components/tracks/TrackPath";
import { buildPathFromLearnLessons } from "../components/tracks/trackPathUtils";
import { PageHeader } from "../components/layout/PageHeader";

type State = "done" | "current" | "locked";

const LESSONS = [
  { title: "Leitura crítica de textos", module: "Fundamentos", state: "done" as State },
  { title: "Estrutura de um parecer", module: "Fundamentos", state: "done" as State },
  { title: "Primeiro rascunho", module: "Fundamentos", state: "done" as State },
  { title: "Revisão em pares", module: "Prática", state: "current" as State },
  { title: "Argumentação objetiva", module: "Prática", state: "locked" as State },
  { title: "Entrega final", module: "Prática", state: "locked" as State },
];

export function Learn() {
  const [selected, setSelected] = useState(3);
  const lesson = LESSONS[selected];
  const canOpen = lesson && lesson.state !== "locked";

  const pathNodes = useMemo(
    () => buildPathFromLearnLessons(LESSONS, { selectedIndex: selected, onSelect: setSelected }),
    [selected],
  );

  return (
    <>
      <PageHeader
        title="Minhas aulas"
        description="O material abre na ordem da turma. Cada aula nova só fica disponível depois que o professor confirma a anterior."
      />

      <div className="learn-layout">
        <div className="card learn-path-panel">
          <TrackPath nodes={pathNodes} selectedId={String(selected)} />
        </div>

        <aside className="learn-panel">
          {canOpen ? (
            <div className="card" style={{ padding: 28 }}>
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>{lesson.module}</p>
              <h2 style={{ marginTop: 6 }}>{lesson.title}</h2>
              <p className="muted" style={{ marginTop: 10 }}>
                {lesson.state === "current"
                  ? "Esta é a aula em que a turma parou. Estude o material e registre dúvidas conforme for avançando."
                  : "Aula já concluída com a turma. Você pode revisar o conteúdo quando quiser."}
              </p>
              <button type="button" className="btn btn-primary" style={{ marginTop: 20 }}>
                {lesson.state === "current" ? "Entrar na aula" : "Revisar aula"}
              </button>
            </div>
          ) : (
            <div className="card learn-panel-empty">
              <p className="muted">Esta aula ainda não foi liberada para a turma.</p>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
