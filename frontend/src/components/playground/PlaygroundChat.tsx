import {
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  fetchStudentMessages,
  sendStudentMessage,
  type PlaygroundMessage,
} from "../../lib/playground";
import { PlaygroundSessionHead } from "./PlaygroundSessionHead";

interface Props {
  cohortId: string;
  studentId: string;
  studentName: string;
  lessonId: string;
  lessonTitle: string;
  canChat: boolean;
  headerActions?: ReactNode;
  onMessageSent?: () => void;
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
  headerActions,
  onMessageSent,
}: Props) {
  const [messages, setMessages] = useState<PlaygroundMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  useEffect(() => {
    if (!canChat || loading) return;
    textareaRef.current?.focus();
  }, [canChat, loading, cohortId, studentId, lessonId]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (sending) return;
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
      onMessageSent?.();
    } catch {
      setMessages((prev) => prev.filter((m) => m !== optimistic));
      setInput(content);
      setError("Não foi possível enviar a mensagem. Tente novamente.");
    } finally {
      setSending(false);
      requestAnimationFrame(() => textareaRef.current?.focus());
    }
  }

  return (
    <section className="playground-chat">
      <PlaygroundSessionHead
        title={lessonTitle}
        participantName={studentName}
        roleLabel="Aluno"
        actions={headerActions}
      />

      <div className="playground-chat__log" aria-live="polite">
        <div className="playground-chat__thread">
          {loading && <p className="muted playground-chat__empty">Carregando histórico…</p>}

          {!loading && messages.length === 0 && (
            <p className="muted playground-chat__intro">
              Envie uma mensagem para iniciar a conversa nesta aula.
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
      </div>

      <footer className="playground-composer">
        {error && <div className="form-error playground-composer__error">{error}</div>}

        {!canChat ? (
          <p className="muted playground-composer__hint">
            Selecione a aula atual ou uma aula já concluída para conversar.
          </p>
        ) : (
          <form className="playground-composer__form" onSubmit={handleSubmit}>
            <div className="playground-composer__box">
              <textarea
                ref={textareaRef}
                className="playground-composer__input"
                rows={1}
                value={input}
                onChange={(ev) => setInput(ev.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Digite como o aluno faria uma pergunta…"
              />
              <button
                type="submit"
                className="playground-composer__send"
                disabled={sending || !input.trim()}
                aria-label="Enviar mensagem"
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
                  <path
                    d="M16 2L8 10M16 2l-4.5 14L8 10M16 2 2 6.5 8 10"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          </form>
        )}
      </footer>
    </section>
  );
}
