import { useState, useRef, useEffect } from "react"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

export default function HermesChatBar() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [open, setOpen] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || streaming) return
    setInput("")
    setOpen(true)
    setMessages(m => [...m, { role: "user", content: text }])
    setStreaming(true)

    // Add an empty assistant message we'll stream into
    setMessages(m => [...m, { role: "assistant", content: "" }])

    try {
      const res = await fetch(`${API}/api/hermes/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value).replace(/^data: /, "")
        setMessages(m => {
          const updated = [...m]
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: updated[updated.length - 1].content + chunk,
          }
          return updated
        })
      }
    } catch (err) {
      setMessages(m => {
        const updated = [...m]
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: `Hermes not connected. Start with: hermes gateway start\n\nError: ${err.message}`,
        }
        return updated
      })
    } finally {
      setStreaming(false)
    }
  }

  return (
    <div style={{
      borderTop: "0.5px solid var(--color-border-tertiary)",
      background: "var(--color-background-primary)",
      flexShrink: 0,
    }}>
      {open && messages.length > 0 && (
        <div style={{
          maxHeight: 240,
          overflowY: "auto",
          padding: "12px 16px",
          borderBottom: "0.5px solid var(--color-border-tertiary)",
        }}>
          {messages.map((m, i) => (
            <div key={i} style={{
              marginBottom: 10,
              display: "flex",
              gap: 8,
              alignItems: "flex-start",
            }}>
              <div style={{
                width: 22, height: 22,
                borderRadius: "50%",
                background: m.role === "user"
                  ? "var(--color-background-secondary)"
                  : "var(--color-background-info)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontWeight: 500, flexShrink: 0,
                color: m.role === "user"
                  ? "var(--color-text-secondary)"
                  : "var(--color-text-info)",
              }}>
                {m.role === "user" ? "U" : "H"}
              </div>
              <div style={{
                fontSize: 13,
                lineHeight: 1.5,
                color: "var(--color-text-primary)",
                whiteSpace: "pre-wrap",
                flex: 1,
              }}>
                {m.content}
                {streaming && i === messages.length - 1 && m.role === "assistant" && (
                  <span style={{ opacity: 0.4 }}>▋</span>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      <div style={{
        display: "flex",
        gap: 8,
        padding: "10px 16px",
        alignItems: "center",
      }}>
        <div style={{
          width: 24, height: 24,
          borderRadius: "50%",
          background: "var(--color-background-info)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, fontWeight: 500,
          color: "var(--color-text-info)",
          flexShrink: 0,
        }}>H</div>
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && send()}
          placeholder="Ask Hermes — e.g. 'Which entries are missing documents?' or 'Summarise this month'"
          style={{
            flex: 1,
            border: "0.5px solid var(--color-border-secondary)",
            borderRadius: "var(--border-radius-md)",
            padding: "7px 12px",
            fontSize: 13,
            background: "var(--color-background-secondary)",
            color: "var(--color-text-primary)",
          }}
          disabled={streaming}
        />
        <button
          onClick={send}
          disabled={streaming || !input.trim()}
          style={{
            padding: "7px 14px",
            borderRadius: "var(--border-radius-md)",
            background: "var(--color-text-primary)",
            color: "var(--color-background-primary)",
            border: "none",
            fontSize: 13,
            cursor: streaming ? "not-allowed" : "pointer",
            opacity: streaming || !input.trim() ? 0.4 : 1,
          }}
        >
          {streaming ? "…" : "Ask"}
        </button>
        {messages.length > 0 && (
          <button
            onClick={() => { setMessages([]); setOpen(false) }}
            style={{
              padding: "7px 10px",
              borderRadius: "var(--border-radius-md)",
              border: "0.5px solid var(--color-border-secondary)",
              background: "none",
              fontSize: 12,
              cursor: "pointer",
              color: "var(--color-text-secondary)",
            }}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  )
}
