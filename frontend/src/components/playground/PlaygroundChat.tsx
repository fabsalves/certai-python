import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  fetchStudentMessages,
  sendStudentMessage,
  type PlaygroundMessage,
} from "../../lib/playground";

interface Props {
  cohortId: string;
  studentId: string;
  studentName: string;
  lessonId: string;
  lessonTitle: string;
  canChat: boolean;
}

function authorLabel(author: PlaygroundMessage["author"]): string {
  if (author === "student") return "Aluno";
  if (author === "agent") return "Lira";
  return "Professor";
}

export function PlaygroundChat({
  cohortId,
  studentId,
  studentName,
  lessonId,
  lessonTitle,
  canChat,
}: Props) {
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!cohortId || !studentId || !lessonId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    fetchStudentMessages(cohortId, studentId, lessonId)
      .then((data) => {
        if (!cancelled) setMessages(data);
      })
      .catch(() => {
        if (!cancelled) setError("Não foi possível carregar o histórico.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [cohortId, studentId, lessonId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const content = input.trim();
    if (!content || !canChat) return;

    setError("");
    setSending(true);
    setInput("");

    const optimistic: PlaygroundMessage = {
      author: "student",
      content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      const { response } = await sendStudentMessage(cohortId, studentId, lessonId, content);
      setMessages((prev) => [
        ...prev,
        { author: "agent", content: response, created_at: new Date().toISOString() },
      ]);
    } catch {
      setMessages((prev) => prev.filter((m) => m !== optimistic));
      setInput(content);
      setError("Não foi possível enviar a mensagem. Tente novamente.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="playground-chat card">
      <header className="playground-chat__head">
        <div>
          <span className="tag">Sessão de aluno</span>
          <h2 style={{ margin: "8px 0 0" }}>{lessonTitle}</h2>
          <p className="muted" style={{ marginTop: 6, fontSize: 14 }}>
            Conversando como <strong>{studentName}</strong> — a IA responde com o contexto desta turma e aula.
          </p>
        </div>
      </header>

      <div className="playground-chat__log" aria-live="polite">
        {loading && <p className="muted playground-chat__empty">Carregando histórico…</p>}
        {!loading && messages.length === 0 && (
          <p className="muted playground-chat__empty">
            Nenhuma mensagem ainda. Envie a primeira pergunta para testar a Lira.
          </p>
        )}
        {messages.map((msg, index) => (
          <div
            key={`${msg.created_at}-${index}`}
            className={`playground-chat__bubble playground-chat__bubble--${msg.author}`}
          >
            <span className="playground-chat__author">{authorLabel(msg.author)}</span>
            <p>{msg.content}</p>
          </div>
        ))}
        {sending && (
          <div className="playground-chat__bubble playground-chat__bubble--agent">
            <span className="playground-chat__author">Lira</span>
            <p className="muted">Pensando…</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <div className="form-error playground-chat__error">{error}</div>}

      {!canChat ? (
        <p className="muted playground-chat__hint">
          Selecione a aula atual ou uma aula já concluída para conversar.
        </p>
      ) : (
        <form className="playground-chat__form" onSubmit={handleSubmit}>
          <textarea
            className="input"
            rows={3}
            value={input}
            onChange={(ev) => setInput(ev.target.value)}
            placeholder="Digite como o aluno faria uma pergunta…"
            disabled={sending}
          />
          <button type="submit" className="btn btn-primary" disabled={sending || !input.trim()}>
            {sending ? "Enviando…" : "Enviar como aluno"}
          </button>
        </form>
      )}
    </section>
  );
}
