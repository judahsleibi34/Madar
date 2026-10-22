import { useEffect, useRef, useState } from "react";
import { History, Maximize2, Minimize2, Plus, Send, X } from "lucide-react";

import aiIcon from "../../../../assets/MadarTemplates/AI Icon.png";
import madarLogo from "../../../../assets/MadarTemplates/madar_header.svg";
import ResultView from "./ResultView";

const CHAT_HISTORY_KEY = "madar.dataWorkspace.athena.history.v1";

const getChatHistoryKey = (user, projectId) => {
  const tenantId = String(user?.tenant_id || "tenant").trim();
  const userId = String(user?.id || user?.auth_id || "user").trim();
  const normalizedProjectId = String(projectId || "project").trim();
  return `${CHAT_HISTORY_KEY}:${tenantId}:${userId}:${normalizedProjectId}`;
};

const readChatHistory = (storageKey) => {
  try {
    const value = JSON.parse(window.localStorage.getItem(storageKey) || "[]");
    return Array.isArray(value) ? value.slice(0, 20) : [];
  } catch {
    return [];
  }
};

export default function DataWorkspaceChatbot({ dataset, onAsk, t, isArabic, projectId, user }) {
  const chatHistoryKey = getChatHistoryKey(user, projectId);
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const [history, setHistory] = useState(() => readChatHistory(chatHistoryKey));
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isFullPage, setIsFullPage] = useState(false);
  const inputRef = useRef(null);
  const threadRef = useRef(null);
  const messageIdRef = useRef(0);
  const sessionIdRef = useRef("");

  const nextMessageId = () => {
    messageIdRef.current += 1;
    return `data-chat-message-${messageIdRef.current}`;
  };

  useEffect(() => {
    threadRef.current?.scrollTo?.({ top: threadRef.current.scrollHeight });
  }, [messages, isSending]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleEscape = (event) => {
      if (event.key !== "Escape") return;
      if (isFullPage) {
        setIsFullPage(false);
      } else {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [isFullPage, isOpen]);

  useEffect(() => {
    try {
      window.localStorage.setItem(chatHistoryKey, JSON.stringify(history.slice(0, 20)));
    } catch {
      // Chat history is optional when browser storage is unavailable or full.
    }
  }, [chatHistoryKey, history]);

  useEffect(() => {
    const firstQuestion = messages.find((message) => message.role === "user");
    if (!firstQuestion) return;

    if (!sessionIdRef.current) {
      sessionIdRef.current = `athena-session-${Date.now()}-${messageIdRef.current}`;
    }

    const session = {
      id: sessionIdRef.current,
      title: String(firstQuestion.value).slice(0, 80),
      datasetName:
        dataset?.original_filename ||
        dataset?.name ||
        dataset?.file_path?.split(/[\\/]/).pop() ||
        t.chatbotDataset,
      updatedAt: Date.now(),
      messages,
    };

    setHistory((current) => [
      session,
      ...current.filter((item) => item.id !== session.id),
    ].slice(0, 20));
  }, [dataset, messages, t.chatbotDataset]);

  const openChat = () => {
    setIsOpen(true);
  };

  const closeChat = () => {
    setIsFullPage(false);
    setIsOpen(false);
  };

  const startNewSession = () => {
    sessionIdRef.current = "";
    setMessages([]);
    setQuestion("");
    setIsHistoryOpen(false);
  };

  const restoreSession = (session) => {
    sessionIdRef.current = session.id;
    setMessages(Array.isArray(session.messages) ? session.messages : []);
    setQuestion("");
    setIsHistoryOpen(false);
  };

  const sendQuestion = async (event) => {
    event.preventDefault();
    const nextQuestion = question.trim();

    if (!nextQuestion || !dataset || isSending) return;

    setQuestion("");
    setMessages((current) => [
      ...current,
      { id: nextMessageId(), role: "user", value: nextQuestion },
    ]);
    setIsSending(true);

    try {
      const result = await onAsk(nextQuestion);
      setMessages((current) => [
        ...current,
        { id: nextMessageId(), role: "assistant", value: result },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: nextMessageId(),
          role: "error",
          value: error.message || t.chatbotError,
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const renderSessionHistory = (inSidebar = false) => (
    <section
      className={`daw-chatbot-history ${inSidebar ? "is-sidebar" : ""}`}
      aria-labelledby={inSidebar ? "daw-chatbot-sidebar-history-title" : "daw-chatbot-history-title"}
    >
      <div className="daw-chatbot-history-heading">
        <div>
          <span>{t.chatbotHistoryKicker}</span>
          <h3 id={inSidebar ? "daw-chatbot-sidebar-history-title" : "daw-chatbot-history-title"}>
            {t.chatbotHistory}
          </h3>
        </div>
        <button type="button" onClick={startNewSession}>
          <Plus size={16} aria-hidden="true" />
          {t.chatbotNewSession}
        </button>
      </div>
      {history.length ? (
        <div className="daw-chatbot-history-list">
          {history.map((session) => (
            <button
              type="button"
              className={session.id === sessionIdRef.current ? "is-active" : ""}
              key={session.id}
              onClick={() => restoreSession(session)}
            >
              <strong>{session.title}</strong>
              <span>{session.datasetName}</span>
              <time dateTime={new Date(session.updatedAt).toISOString()}>
                {new Intl.DateTimeFormat(isArabic ? "ar" : "en", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(session.updatedAt)}
              </time>
            </button>
          ))}
        </div>
      ) : (
        <p className="daw-chatbot-history-empty">{t.chatbotNoHistory}</p>
      )}
    </section>
  );

  return (
    <aside
      className={`daw-chatbot ${isOpen ? "is-open" : ""} ${isFullPage ? "is-full-page" : ""}`}
      dir={isArabic ? "rtl" : "ltr"}
      style={{
        "--daw-chatbot-image": `url("${aiIcon}")`,
        "--daw-chatbot-watermark": `url("${madarLogo}")`,
      }}
      aria-label={t.chatbotTitle}
    >
      {isOpen ? (
        <section className="daw-chatbot-panel" role="dialog" aria-labelledby="daw-chatbot-title">
          <header className="daw-chatbot-header">
            <span className="daw-chatbot-avatar" aria-hidden="true" />
            <div>
              <h2 id="daw-chatbot-title">{t.chatbotTitle}</h2>
              <p>{dataset ? t.chatbotReady : t.chatbotNeedsData}</p>
            </div>
            <div className="daw-chatbot-header-actions">
              {!isFullPage ? (
                <button
                  type="button"
                  className={`daw-chatbot-header-action ${isHistoryOpen ? "is-active" : ""}`}
                  onClick={() => setIsHistoryOpen((current) => !current)}
                  aria-label={t.chatbotHistory}
                  title={t.chatbotHistory}
                >
                  <History size={18} aria-hidden="true" />
                </button>
              ) : null}
              <button
                type="button"
                className="daw-chatbot-header-action"
                onClick={startNewSession}
                aria-label={t.chatbotNewSession}
                title={t.chatbotNewSession}
              >
                <Plus size={18} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="daw-chatbot-header-action"
                onClick={() => setIsFullPage((current) => !current)}
                aria-label={isFullPage ? t.chatbotExitFullPage : t.chatbotEnterFullPage}
                title={isFullPage ? t.chatbotExitFullPage : t.chatbotEnterFullPage}
              >
                {isFullPage ? (
                  <Minimize2 size={18} aria-hidden="true" />
                ) : (
                  <Maximize2 size={18} aria-hidden="true" />
                )}
              </button>
              <button
                type="button"
                className="daw-chatbot-close"
                onClick={closeChat}
                aria-label={t.chatbotClose}
              >
                <X size={20} aria-hidden="true" />
              </button>
            </div>
          </header>

          <div className="daw-chatbot-body">
            {isFullPage ? (
              <aside className="daw-chatbot-history-sidebar" aria-label={t.chatbotHistory}>
                {renderSessionHistory(true)}
              </aside>
            ) : null}

            <div className="daw-chatbot-conversation">
              {isFullPage ? (
                <span className="daw-chatbot-full-page-watermark" aria-hidden="true" />
              ) : null}
              {isHistoryOpen && !isFullPage ? renderSessionHistory() : (
                <div ref={threadRef} className="daw-chatbot-thread" aria-live="polite">
                  <article className="daw-chatbot-message is-assistant">
                    <p>{t.chatbotGreeting}</p>
                  </article>

                  {messages.map((message) => (
                    <article
                      className={`daw-chatbot-message is-${message.role}`}
                      key={message.id}
                    >
                      {message.role === "assistant" ? (
                        <ResultView value={message.value} t={t} />
                      ) : (
                        <p>{message.value}</p>
                      )}
                    </article>
                  ))}

                  {isSending ? (
                    <article className="daw-chatbot-message is-assistant is-thinking">
                      <p>{t.chatbotThinking}</p>
                    </article>
                  ) : null}
                </div>
              )}

              {!isHistoryOpen || isFullPage ? (
                <form className="daw-chatbot-form" onSubmit={sendQuestion}>
                  <label className="daw-chatbot-sr-only" htmlFor="daw-chatbot-question">
                    {t.chatbotQuestionLabel}
                  </label>
                  <textarea
                    id="daw-chatbot-question"
                    ref={inputRef}
                    rows={2}
                    value={question}
                    disabled={!dataset || isSending}
                    placeholder={dataset ? t.chatbotPlaceholder : t.chatbotNeedsData}
                    onChange={(event) => setQuestion(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        event.currentTarget.form?.requestSubmit();
                      }
                    }}
                  />
                  <button
                    type="submit"
                    disabled={!dataset || isSending || !question.trim()}
                    aria-label={t.chatbotSend}
                  >
                    <Send size={18} aria-hidden="true" />
                  </button>
                </form>
              ) : null}
            </div>
          </div>
        </section>
      ) : (
        <div className="daw-chatbot-launcher-row">
          <button
            type="button"
            className="daw-chatbot-launcher"
            onClick={openChat}
            aria-label={t.chatbotOpen}
          />
        </div>
      )}
    </aside>
  );
}
