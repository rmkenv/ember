import { useRef, useEffect } from "react"

export default function ChatPanel({ messages, streaming, modelName, onStop }) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streaming])

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "16px 18px 8px" }}>
      {messages.map((msg, i) => {
        const isUser = msg.role === "user"
        return (
          <div key={i} className="fade-in" style={{
            display: "flex", flexDirection: "column",
            alignItems: isUser ? "flex-end" : "flex-start",
            marginBottom: 16
          }}>
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: "0.1em",
              color: isUser ? "#444" : "#e8372c88",
              marginBottom: 4, fontFamily: "monospace", textTransform: "uppercase"
            }}>
              {isUser ? "Operator" : `EMBER · ${modelName}`}
            </div>
            <div style={{
              maxWidth: "92%",
              background: isUser ? "#111418" : "#0c1118",
              border: `1px solid ${isUser ? "#1e1e1e" : "#e8372c22"}`,
              borderRadius: isUser ? "10px 10px 3px 10px" : "10px 10px 10px 3px",
              padding: "10px 14px",
              fontSize: 12.5, lineHeight: 1.75,
              color: isUser ? "#bbb" : "#dde",
              whiteSpace: "pre-wrap",
              fontFamily: "'IBM Plex Mono', monospace",
            }}>
              {msg.content || <span style={{ color: "#333" }}>▋</span>}
            </div>
          </div>
        )
      })}

      {streaming && (
        <div style={{ fontSize: 10, color: "#e8372c55", marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
          <span className="blink">▋</span>
          <span style={{ fontFamily: "monospace" }}>{modelName} generating…</span>
          <button onClick={onStop} style={{
            fontSize: 9, color: "#555", background: "none",
            border: "1px solid #222", borderRadius: 3,
            cursor: "pointer", padding: "1px 7px", fontFamily: "monospace"
          }}>stop</button>
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}
