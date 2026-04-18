// Ollama Cloud API — https://docs.ollama.com/cloud
// Base URL: https://ollama.com (not localhost)
// Auth:     Authorization: Bearer <OLLAMA_API_KEY>
// No local Ollama install required. Works from Vercel, Streamlit Cloud, anywhere.

const OLLAMA_HOST  = import.meta.env.VITE_OLLAMA_HOST  || "https://ollama.com"
const OLLAMA_MODEL = import.meta.env.VITE_OLLAMA_MODEL || "gpt-oss:120b-cloud"
const OLLAMA_KEY   = import.meta.env.VITE_OLLAMA_API_KEY || ""

export { OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_KEY }

export async function pingOllama() {
  if (!OLLAMA_KEY) return "no-key"
  try {
    const res = await fetch(`${OLLAMA_HOST}/api/tags`, {
      headers: { Authorization: `Bearer ${OLLAMA_KEY}` },
      signal: AbortSignal.timeout(5000),
    })
    return res.ok ? true : false
  } catch {
    return false
  }
}

export async function* streamOllama(messages, context, abortSignal) {
  if (!OLLAMA_KEY) {
    yield "⚠ No API key set. Add VITE_OLLAMA_API_KEY to your .env.local file.\n\nGet a key at: https://ollama.com/settings/keys"
    return
  }

  const systemPrompt = `You are EMBER — Emergency Management Body of Evidence & Resources — an AI assistant for NYC emergency managers and first responders.

KNOWLEDGE BASE:
${context}

RESPONSE RULES:
1. Lead with operationally critical information first.
2. Be concise — emergency managers need facts, not prose.
3. Cite your source for every key fact using brackets: [NYC OEM], [NWS], [FEMA], [USGS], etc.
4. For location-specific queries, prioritize zone and risk data for that location.
5. Flag data gaps or caveats clearly.
6. Use structured formatting: bold headers, bullet points for action items.
7. For life-safety queries, always include emergency contact numbers.
8. Never hallucinate. If information is not in the knowledge base, say so explicitly.`

  const payload = {
    model: OLLAMA_MODEL,
    stream: true,
    messages: [
      { role: "system", content: systemPrompt },
      ...messages.slice(-10).map(m => ({ role: m.role, content: m.content }))
    ]
  }

  const res = await fetch(`${OLLAMA_HOST}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${OLLAMA_KEY}`,
    },
    body: JSON.stringify(payload),
    signal: abortSignal,
  })

  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText)
    throw new Error(`Ollama Cloud ${res.status}: ${err}`)
  }

  const reader  = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop()
    for (const line of lines) {
      if (!line.trim()) continue
      try {
        const obj   = JSON.parse(line)
        const token = obj.message?.content
        if (token) yield token
        if (obj.done) return
      } catch { /* skip malformed */ }
    }
  }
}
