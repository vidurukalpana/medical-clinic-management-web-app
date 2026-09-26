import { useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, Loader2, MessageCircle, Send, X } from "lucide-react";
import { api, type ChatMessage } from "../lib/api";

// Matches the backend limits in app/schemas/chatbot.py.
const MAX_MESSAGE_LENGTH = 1000;
const MAX_HISTORY_MESSAGES = 20;

const SUGGESTIONS = ["What are the consultation hours?", "How do I book a visit?", "How do I cancel a booking?"];

// Question-only assistant for the public site. The conversation lives in memory
// and is gone when the page is closed.
export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, sending, error]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || sending) return;
    const history = [...messages, { role: "user" as const, content: question }];
    setMessages(history);
    setDraft("");
    setError(null);
    setSending(true);
    try {
      const { reply } = await api.askChatbot(history.slice(-MAX_HISTORY_MESSAGES));
      setMessages((current) => [...current, { role: "assistant", content: reply }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  return (
    <div className="chat-widget">
      {open && (
        <section className="chat-panel" role="dialog" aria-label="Clinic assistant">
          <header className="chat-head">
            <span className="chat-avatar">
              <Bot size={18} />
            </span>
            <div>
              <strong>Clinic assistant</strong>
              <small>Answers questions about the clinic and booking</small>
            </div>
            <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close chat">
              <X size={18} />
            </button>
          </header>

          <div className="chat-log" ref={logRef} aria-live="polite">
            <p className="chat-bubble is-assistant">
              Hi! Ask me about our doctors, consultation hours or how booking works. I can't book or change
              appointments, and I can't give medical advice.
            </p>
            {messages.length === 0 && (
              <div className="chat-suggestions">
                {SUGGESTIONS.map((suggestion) => (
                  <button key={suggestion} className="btn btn-secondary btn-sm" onClick={() => void send(suggestion)}>
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            {messages.map((message, index) => (
              <p key={index} className={`chat-bubble is-${message.role}`}>
                {message.content}
              </p>
            ))}
            {sending && (
              <p className="chat-bubble is-assistant chat-typing">
                <Loader2 size={14} className="spin" /> Thinking…
              </p>
            )}
            {error && <div className="alert alert-error">{error}</div>}
          </div>

          <form className="chat-form" onSubmit={onSubmit}>
            <input
              ref={inputRef}
              className="input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={MAX_MESSAGE_LENGTH}
              placeholder="Type your question…"
              aria-label="Your question"
            />
            <button className="btn btn-primary chat-send" disabled={sending || !draft.trim()} aria-label="Send">
              <Send size={16} />
            </button>
          </form>
          <p className="chat-note">AI answers may be wrong. Please don't share medical details or booking codes.</p>
        </section>
      )}
      <button
        className="btn btn-accent chat-launcher"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={open ? "Close chat" : "Ask a question"}
      >
        {open ? <X size={20} /> : <MessageCircle size={20} />}
        {!open && <span>Ask a question</span>}
      </button>
    </div>
  );
}
