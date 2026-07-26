import {
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  fetchStudentMessages,
  sendStudentMessage,
  type PlaygroundMessage,
  type PlaygroundMessageSource,
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

const SOURCE_LABELS: Record<PlaygroundMessageSource, string> = {
  realtime_voice: "Voz",
  whatsapp_text: "WhatsApp",
  whatsapp_audio: "WhatsApp áudio",
  in_app_text: "Playground",
};

function sourceLabel(source: PlaygroundMessageSource | null | undefined): string | null {
  if (!source) return null;
  return SOURCE_LABELS[source] ?? source;
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

const URL_PATTERN = /(https?:\/\/\S+)/g;

function renderMessageContent(content: string) {
  return content.split(URL_PATTERN).map((part, index) => {
    if (!/^https?:\/\//.test(part)) {
      return <span key={index}>{part}</span>;
    }

    return (
      <a
        key={index}
        href={part}
        className="playground-chat__link"
        target="_blank"
        rel="noopener noreferrer"
      >
        {part}
      </a>
    );
  });
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
  const [refreshing, setRefreshing] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const loadMessages = useCallback(
    async (options?: { refresh?: boolean }) => {
      if (!cohortId || !studentId || !lessonId) {
        setMessages([]);
        return;
      }

      const isRefresh = options?.refresh ?? false;
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError("");

      try {
        const data = await fetchStudentMessages(cohortId, studentId, lessonId);
        setMessages(data);
      } catch {
        setError(
          isRefresh
            ? "Não foi possível atualizar o histórico."
            : "Não foi possível carregar o histórico.",
        );
      } finally {
        if (isRefresh) {
          setRefreshing(false);
        } else {
          setLoading(false);
        }
      }
    },
    [cohortId, studentId, lessonId],
  );

  useEffect(() => {
    void loadMessages();
  }, [loadMessages]);

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
      source: "in_app_text",
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      const { response } = await sendStudentMessage(cohortId, studentId, lessonId, content);
      setMessages((prev) => [
        ...prev,
        {
          author: "agent",
          content: response,
          created_at: new Date().toISOString(),
          source: "in_app_text",
        },
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
        actions={
          <>
            <button
              type="button"
              className="btn btn-ghost btn-sm playground-chat__refresh"
              onClick={() => void loadMessages({ refresh: true })}
              disabled={loading || refreshing || !canChat}
              aria-label="Atualizar mensagens"
            >
              {refreshing ? "Atualizando…" : "Atualizar"}
            </button>
            {headerActions}
          </>
        }
      />

      <div className="playground-chat__log" aria-live="polite">
        <div className="playground-chat__thread">
          {loading && <p className="muted playground-chat__empty">Carregando histórico…</p>}

          {!loading && messages.length === 0 && (
            <p className="muted playground-chat__intro">
              Envie uma mensagem para iniciar a conversa nesta aula.
            </p>
          )}

          {messages.map((msg, index) => {
            const source = sourceLabel(msg.source);
            return (
              <div
                key={`${msg.created_at}-${index}`}
                className={`playground-chat__bubble playground-chat__bubble--${msg.author}`}
              >
                <span className="playground-chat__author">{authorLabel(msg.author)}</span>
                <p>{renderMessageContent(msg.content)}</p>
                <div className="playground-chat__meta">
                  {source && <span className="playground-chat__source">{source}</span>}
                  <time className="playground-chat__time" dateTime={msg.created_at}>
                    {formatWhen(msg.created_at)}
                  </time>
                </div>
              </div>
            );
          })}

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
