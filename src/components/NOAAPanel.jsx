import { useState, useCallback } from "react"
import { NOAA_CATEGORIES, fetchNOAAEndpoint, summarizeNOAAResult, getAllEndpoints } from "../data/noaa.js"

const ACCENT = "#34d399"  // green — NOAA ocean/environment

// ── Small helpers ──────────────────────────────────────────────────────────────
const Tag = ({ label, color = "#555" }) => (
  <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: color + "18", color, border: `1px solid ${color}33`, fontFamily: "monospace", whiteSpace: "nowrap" }}>
    {label}
  </span>
)

const StatusDot = ({ status }) => {
  const colors = { idle: "#333", loading: "#facc15", ok: "#4ade80", error: "#f87171" }
  const labels = { idle: "IDLE", loading: "FETCHING…", ok: "OK", error: "ERROR" }
  return (
    <span style={{ fontSize: 9, fontFamily: "monospace", color: colors[status] || "#333", fontWeight: 700 }}>
      {status === "loading" ? <span className="spin">↺</span> : "●"} {labels[status] || status}
    </span>
  )
}

// ── Endpoint card ──────────────────────────────────────────────────────────────
const EndpointCard = ({ ep, catColor, catIcon, result, onFetch, onInject, injected, loading }) => {
  const [expanded, setExpanded] = useState(false)
  const status = loading ? "loading" : result ? (result.success ? "ok" : "error") : "idle"

  return (
    <div style={{
      background: "#0c1018",
      border: `1px solid ${injected ? ACCENT + "55" : result?.success ? "#1e3a2e" : "#141820"}`,
      borderRadius: 6, marginBottom: 6, overflow: "hidden",
      transition: "border-color 0.15s"
    }}>
      {/* Header row */}
      <div style={{ padding: "8px 10px", display: "flex", gap: 8, alignItems: "flex-start" }}>
        <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1 }}>{catIcon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "#dde", marginBottom: 2, lineHeight: 1.3 }}>{ep.name}</div>
          <div style={{ fontSize: 10, color: "#556", lineHeight: 1.5, marginBottom: 4 }}>{ep.desc}</div>
          <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
            {ep.tags?.slice(0, 4).map((t, i) => <Tag key={i} label={t} color={catColor} />)}
          </div>
        </div>
        <div style={{ flexShrink: 0, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <StatusDot status={status} />
        </div>
      </div>

      {/* Actions */}
      <div style={{ padding: "0 10px 8px", display: "flex", gap: 5, flexWrap: "wrap" }}>
        <button onClick={() => onFetch(ep)} disabled={loading} style={{
          fontSize: 9.5, padding: "3px 9px", borderRadius: 4, fontWeight: 700,
          border: `1px solid ${catColor}55`, background: "transparent",
          color: catColor, cursor: loading ? "not-allowed" : "pointer", fontFamily: "monospace"
        }}>
          {loading ? <span className="spin">↺</span> : "▶"} FETCH
        </button>
        {result?.success && (
          <>
            <button onClick={() => setExpanded(p => !p)} style={{
              fontSize: 9.5, padding: "3px 9px", borderRadius: 4, fontWeight: 700,
              border: "1px solid #1e2a30", background: "transparent",
              color: "#778", cursor: "pointer", fontFamily: "monospace"
            }}>
              {expanded ? "▾ HIDE" : "▸ PREVIEW"}
            </button>
            <button onClick={() => onInject(ep, result)} style={{
              fontSize: 9.5, padding: "3px 9px", borderRadius: 4, fontWeight: 700,
              border: `1px solid ${injected ? "#4ade80" : "#1e2a30"}`,
              background: injected ? "#4ade8015" : "transparent",
              color: injected ? "#4ade80" : "#778",
              cursor: "pointer", fontFamily: "monospace"
            }}>
              {injected ? "✓ IN KB" : "+ ADD TO KB"}
            </button>
          </>
        )}
        <a href={ep.url} target="_blank" rel="noopener noreferrer" style={{
          fontSize: 9.5, padding: "3px 9px", borderRadius: 4,
          border: "1px solid #141820", color: "#3a3e50",
          textDecoration: "none", fontFamily: "monospace"
        }}>↗ URL</a>
      </div>

      {/* Preview */}
      {expanded && result?.success && (
        <div style={{
          borderTop: "1px solid #141820", padding: "8px 10px",
          background: "#080b10", fontSize: 10, fontFamily: "monospace",
          color: "#7a9", lineHeight: 1.7, whiteSpace: "pre-wrap",
          maxHeight: 200, overflowY: "auto"
        }}>
          {summarizeNOAAResult(result)}
        </div>
      )}
      {result && !result.success && (
        <div style={{ borderTop: "1px solid #2a1010", padding: "6px 10px", background: "#0d0808", fontSize: 10, color: "#f87171", fontFamily: "monospace" }}>
          ⚠ {result.error}
        </div>
      )}
    </div>
  )
}

// ── Main NOAAPanel ────────────────────────────────────────────────────────────
export default function NOAAPanel({ onInjectToKB }) {
  const [results, setResults]         = useState({})   // ep.id → result
  const [loading, setLoading]         = useState({})   // ep.id → bool
  const [injectedIds, setInjectedIds] = useState(new Set())
  const [activeCategory, setActiveCategory] = useState("nws")
  const [searchText, setSearchText]   = useState("")
  const [fetching_all, setFetchingAll]= useState(false)

  const handleFetch = useCallback(async (ep) => {
    setLoading(p => ({ ...p, [ep.id]: true }))
    const result = await fetchNOAAEndpoint(ep)
    setResults(p => ({ ...p, [ep.id]: result }))
    setLoading(p => ({ ...p, [ep.id]: false }))
  }, [])

  const handleFetchAll = useCallback(async (categoryId) => {
    const cat = NOAA_CATEGORIES[categoryId]
    if (!cat) return
    setFetchingAll(true)
    await Promise.all(cat.endpoints.map(ep => handleFetch(ep)))
    setFetchingAll(false)
  }, [handleFetch])

  const handleInject = useCallback((ep, result) => {
    const content = summarizeNOAAResult(result)
    onInjectToKB({
      name: `NOAA: ${ep.name}`,
      content: `[NOAA Open Data — ${ep.name}]\nSource: ${ep.url}\n\n${content}`,
      itemId: ep.id,
      source: "NOAA Open Data"
    })
    setInjectedIds(prev => new Set([...prev, ep.id]))
  }, [onInjectToKB])

  // Search across all endpoints
  const searchResults = searchText.trim()
    ? getAllEndpoints().filter(ep =>
        ep.name.toLowerCase().includes(searchText.toLowerCase()) ||
        ep.desc.toLowerCase().includes(searchText.toLowerCase()) ||
        ep.tags?.some(t => t.toLowerCase().includes(searchText.toLowerCase()))
      )
    : null

  const cat = NOAA_CATEGORIES[activeCategory]
  const displayEndpoints = searchResults || cat?.endpoints || []
  const displayColor     = searchResults ? ACCENT : cat?.color || ACCENT
  const displayIcon      = searchResults ? "🔍" : cat?.icon || "📡"

  const fetchedCount = Object.values(results).filter(r => r?.success).length
  const injectedCount = injectedIds.size

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: "monospace" }}>

      {/* ── Header ── */}
      <div style={{ flexShrink: 0, padding: "10px 14px", borderBottom: `1px solid ${ACCENT}22`, background: "#090c14" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 9, color: ACCENT, fontWeight: 700, letterSpacing: "0.1em" }}>NOAA OPEN DATA STACK</div>
            <div style={{ fontSize: 9, color: "#333", marginTop: 1 }}>No API key required · All endpoints public</div>
          </div>
          <div style={{ display: "flex", gap: 10, fontSize: 9, fontFamily: "monospace" }}>
            <span style={{ color: "#4ade80" }}>▶ {fetchedCount} fetched</span>
            {injectedCount > 0 && <span style={{ color: ACCENT }}>✓ {injectedCount} in KB</span>}
          </div>
        </div>

        {/* Search */}
        <input
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          placeholder="Search endpoints… (flood, tide, temperature, alerts, solar wind…)"
          style={{
            width: "100%", background: "#0d1020", border: `1px solid ${ACCENT}33`,
            borderRadius: 5, padding: "6px 10px", color: "#dde", fontSize: 11,
            fontFamily: "monospace", outline: "none", marginBottom: 8
          }}
        />

        {/* Category tabs */}
        {!searchText && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {Object.entries(NOAA_CATEGORIES).map(([id, c]) => {
              const catFetched = c.endpoints.filter(ep => results[ep.id]?.success).length
              return (
                <button key={id} onClick={() => setActiveCategory(id)} style={{
                  fontSize: 9.5, padding: "3px 10px", borderRadius: 4, fontWeight: 700,
                  border: `1.5px solid ${activeCategory === id ? c.color : "#1a1e2e"}`,
                  background: activeCategory === id ? `${c.color}18` : "transparent",
                  color: activeCategory === id ? c.color : "#3a3e50",
                  cursor: "pointer", fontFamily: "monospace"
                }}>
                  {c.icon} {c.label.split(" ")[0]}
                  {catFetched > 0 && <span style={{ marginLeft: 4, fontSize: 8, color: "#4ade80" }}>({catFetched}✓)</span>}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Category header / Fetch All ── */}
      {!searchText && cat && (
        <div style={{ flexShrink: 0, padding: "8px 14px", borderBottom: "1px solid #0f1520", background: "#090e14", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, color: cat.color, fontWeight: 700 }}>{cat.icon} {cat.label}</div>
            <div style={{ fontSize: 9.5, color: "#446", marginTop: 2 }}>{cat.description}</div>
          </div>
          <button
            onClick={() => handleFetchAll(activeCategory)}
            disabled={fetching_all}
            style={{
              fontSize: 9.5, padding: "4px 12px", borderRadius: 4, fontWeight: 700,
              border: `1px solid ${cat.color}55`, background: `${cat.color}0d`,
              color: cat.color, cursor: fetching_all ? "not-allowed" : "pointer",
              fontFamily: "monospace", flexShrink: 0
            }}
          >
            {fetching_all ? <span className="spin">↺</span> : "▶▶"} FETCH ALL
          </button>
        </div>
      )}

      {searchText && (
        <div style={{ flexShrink: 0, padding: "6px 14px", borderBottom: "1px solid #0f1520", background: "#090e14", fontSize: 9.5, color: "#556" }}>
          {displayEndpoints.length} endpoint{displayEndpoints.length !== 1 ? "s" : ""} matching "{searchText}" across all NOAA APIs
        </div>
      )}

      {/* ── Endpoint list ── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }}>
        {displayEndpoints.length === 0 && (
          <div style={{ color: "#2a2e3a", fontSize: 11, textAlign: "center", marginTop: 24 }}>
            No endpoints found matching "{searchText}"
          </div>
        )}
        {displayEndpoints.map(ep => {
          const epCat = Object.values(NOAA_CATEGORIES).find(c => c.endpoints.some(e => e.id === ep.id))
          return (
            <EndpointCard
              key={ep.id}
              ep={ep}
              catColor={ep.color || epCat?.color || displayColor}
              catIcon={ep.icon || epCat?.icon || displayIcon}
              result={results[ep.id]}
              onFetch={handleFetch}
              onInject={handleInject}
              injected={injectedIds.has(ep.id)}
              loading={!!loading[ep.id]}
            />
          )
        })}
      </div>

      {/* ── Footer summary ── */}
      <div style={{ flexShrink: 0, padding: "6px 14px", borderTop: "1px solid #0f1520", background: "#090c12", fontSize: 9, color: "#333", display: "flex", gap: 12, fontFamily: "monospace" }}>
        <span>{getAllEndpoints().length} total endpoints</span>
        <span>{Object.keys(NOAA_CATEGORIES).length} API categories</span>
        <span>NWS · CO-OPS · NCEI · SPC · SWPC</span>
        <span style={{ marginLeft: "auto", color: "#4ade8055" }}>no key required</span>
      </div>
    </div>
  )
}
