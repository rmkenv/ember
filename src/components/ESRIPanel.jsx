import { useState, useCallback, useRef } from "react"
import {
  searchAGOL, fetchItemMetadata, formatItemForContext,
  summarizeSearchResults, LIVING_ATLAS_FILTERS, ESRI_ITEM_TYPES, AGOL_BASE
} from "../data/esri.js"

const ACCENT = "#a78bfa"  // purple — ESRI brand adjacent

// ── small helpers ─────────────────────────────────────────────────────────────
const Tag = ({ label, color = "#333", bg = "#1a1a2e" }) => (
  <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 3, background: bg, color, border: `1px solid ${color}33`, fontFamily: "monospace", whiteSpace: "nowrap" }}>
    {label}
  </span>
)

const TypeBadge = ({ type }) => {
  const colors = {
    "Feature Layer": "#60a5fa", "Feature Service": "#60a5fa",
    "Map Service": "#34d399",   "Image Service": "#f59e0b",
    "Vector Tile Layer": "#a78bfa", "Web Map": "#fb923c",
    "Web Scene": "#f87171",    "StoryMap": "#e879f9",
    "Dashboard": "#facc15",    "Feature Collection": "#4ade80",
  }
  const c = colors[type] || "#666"
  return <Tag label={type} color={c} />
}

// ── Item card ─────────────────────────────────────────────────────────────────
const ItemCard = ({ item, onInspect, onInject, injected }) => {
  const isLivingAtlas = item.owner?.toLowerCase().includes("esri")
  const agolUrl = `https://www.arcgis.com/home/item.html?id=${item.id}`

  return (
    <div style={{
      background: "#0d1117", border: `1px solid ${injected ? ACCENT + "66" : "#1a1e2e"}`,
      borderRadius: 6, padding: "10px 12px", marginBottom: 7,
      transition: "border-color 0.15s"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", alignItems: "center", marginBottom: 4 }}>
            <TypeBadge type={item.type} />
            {isLivingAtlas && <Tag label="Living Atlas" color={ACCENT} bg="#1a1228" />}
            {item.access === "public" && <Tag label="public" color="#4ade80" />}
          </div>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#dde", marginBottom: 3, lineHeight: 1.3, wordBreak: "break-word" }}>
            {item.title}
          </div>
          <div style={{ fontSize: 10, color: "#555", marginBottom: 4, fontFamily: "monospace" }}>
            {item.owner} · {item.modified ? new Date(item.modified).toISOString().substring(0, 10) : ""}
          </div>
          {item.snippet && (
            <div style={{ fontSize: 10.5, color: "#778", lineHeight: 1.5, marginBottom: 5 }}>
              {item.snippet.substring(0, 140)}{item.snippet.length > 140 ? "…" : ""}
            </div>
          )}
          {item.tags?.length > 0 && (
            <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
              {item.tags.slice(0, 6).map((t, i) => <Tag key={i} label={t} color="#3a3e58" />)}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "flex", gap: 5, marginTop: 8, flexWrap: "wrap" }}>
        <button onClick={() => onInspect(item)} style={{
          fontSize: 9.5, padding: "3px 9px", borderRadius: 4,
          border: `1px solid ${ACCENT}55`, background: "transparent",
          color: ACCENT, cursor: "pointer", fontFamily: "monospace", fontWeight: 700
        }}>⊕ INSPECT METADATA</button>
        <button onClick={() => onInject(item)} style={{
          fontSize: 9.5, padding: "3px 9px", borderRadius: 4,
          border: `1px solid ${injected ? "#4ade80" : "#333"}`,
          background: injected ? "#4ade8015" : "transparent",
          color: injected ? "#4ade80" : "#555",
          cursor: "pointer", fontFamily: "monospace", fontWeight: 700
        }}>
          {injected ? "✓ IN KB" : "+ ADD TO KB"}
        </button>
        <a href={agolUrl} target="_blank" rel="noopener noreferrer" style={{
          fontSize: 9.5, padding: "3px 9px", borderRadius: 4,
          border: "1px solid #1a1e2e", color: "#444",
          textDecoration: "none", fontFamily: "monospace"
        }}>↗ AGOL</a>
        {item.url && (
          <a href={item.url} target="_blank" rel="noopener noreferrer" style={{
            fontSize: 9.5, padding: "3px 9px", borderRadius: 4,
            border: "1px solid #1a1e2e", color: "#444",
            textDecoration: "none", fontFamily: "monospace"
          }}>↗ SERVICE</a>
        )}
      </div>
    </div>
  )
}

// ── Metadata inspector drawer ─────────────────────────────────────────────────
const MetadataDrawer = ({ item, onClose, onInject, injected }) => {
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)

  useState(() => {
    if (!item) return
    fetchItemMetadata(item.id).then(({ item: fullItem, data }) => {
      setMeta({ fullItem, data })
      setLoading(false)
    })
  }, [item?.id])

  if (!item) return null

  const renderJSON = (obj, depth = 0) => {
    if (!obj || typeof obj !== "object") return <span style={{ color: "#a5b4fc" }}>{JSON.stringify(obj)}</span>
    if (Array.isArray(obj)) {
      if (obj.length === 0) return <span style={{ color: "#666" }}>[]</span>
      if (typeof obj[0] !== "object") return <span style={{ color: "#a5b4fc" }}>[{obj.slice(0, 8).map(v => JSON.stringify(v)).join(", ")}{obj.length > 8 ? ` …+${obj.length - 8}` : ""}]</span>
    }
    return (
      <div style={{ paddingLeft: depth > 0 ? 14 : 0 }}>
        {Object.entries(obj).slice(0, depth > 0 ? 15 : 40).map(([k, v]) => (
          <div key={k} style={{ marginBottom: 2 }}>
            <span style={{ color: ACCENT, fontSize: 10 }}>{k}</span>
            <span style={{ color: "#444", fontSize: 10 }}>: </span>
            {typeof v === "object" && v !== null
              ? renderJSON(v, depth + 1)
              : <span style={{ color: typeof v === "string" ? "#86efac" : "#fbbf24", fontSize: 10 }}>{JSON.stringify(v)}</span>
            }
          </div>
        ))}
        {typeof obj === "object" && !Array.isArray(obj) && Object.keys(obj).length > 40 && (
          <div style={{ color: "#444", fontSize: 10 }}>…{Object.keys(obj).length - 40} more keys</div>
        )}
      </div>
    )
  }

  const fi = meta?.fullItem
  const d  = meta?.data

  return (
    <div style={{
      position: "absolute", inset: 0, zIndex: 200,
      background: "#07090dee", backdropFilter: "blur(4px)",
      display: "flex", alignItems: "stretch", justifyContent: "flex-end"
    }}>
      <div style={{
        width: "min(640px, 95vw)", background: "#090c14",
        borderLeft: `1px solid ${ACCENT}44`,
        display: "flex", flexDirection: "column",
        fontFamily: "monospace", fontSize: 11
      }}>
        {/* Header */}
        <div style={{ padding: "12px 16px", borderBottom: `1px solid ${ACCENT}22`, display: "flex", justifyContent: "space-between", alignItems: "center", flexShrink: 0 }}>
          <div>
            <div style={{ fontSize: 9, color: ACCENT, fontWeight: 700, letterSpacing: "0.1em" }}>METADATA INSPECTOR</div>
            <div style={{ fontSize: 12, color: "#dde", fontWeight: 700, marginTop: 2 }}>{item.title}</div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => onInject(item, fi, d)} style={{
              fontSize: 9.5, padding: "4px 10px", borderRadius: 4,
              border: `1px solid ${injected ? "#4ade80" : ACCENT}`,
              background: injected ? "#4ade8015" : `${ACCENT}15`,
              color: injected ? "#4ade80" : ACCENT,
              cursor: "pointer", fontFamily: "monospace", fontWeight: 700
            }}>
              {injected ? "✓ IN KNOWLEDGE BASE" : "+ ADD TO KNOWLEDGE BASE"}
            </button>
            <button onClick={onClose} style={{ background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 16 }}>✕</button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px" }}>
          {loading && <div style={{ color: "#444" }}>Loading metadata…</div>}

          {fi && (
            <>
              {/* Summary block */}
              <div style={{ background: "#0d1520", border: `1px solid ${ACCENT}22`, borderRadius: 6, padding: "10px 12px", marginBottom: 14 }}>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                  <TypeBadge type={fi.type} />
                  {fi.owner?.toLowerCase().includes("esri") && <Tag label="Living Atlas" color={ACCENT} bg="#1a1228" />}
                  <Tag label={fi.access} color="#4ade80" />
                </div>
                <MetaRow k="Item ID"   v={fi.id} copyable />
                <MetaRow k="Owner"     v={fi.owner} />
                <MetaRow k="Updated"   v={fi.modified ? new Date(fi.modified).toLocaleDateString() : "—"} />
                <MetaRow k="Views"     v={(fi.numViews || 0).toLocaleString()} />
                <MetaRow k="Extent"    v={fi.extent ? fi.extent.flat().map(n => n.toFixed(4)).join(", ") : "—"} />
                <MetaRow k="Spatial Ref" v={fi.spatialReference?.wkid || "—"} />
                {fi.url && <MetaRow k="Service URL" v={fi.url} link />}
                <MetaRow k="Tags" v={(fi.tags || []).join(", ")} />
              </div>

              {/* Description */}
              {fi.description && (
                <Section title="DESCRIPTION">
                  <div style={{ color: "#99a", fontSize: 11, lineHeight: 1.7 }}
                    dangerouslySetInnerHTML={{ __html: fi.description.substring(0, 2000) }} />
                </Section>
              )}

              {/* Layers from service data */}
              {d?.layers && (
                <Section title={`LAYERS (${d.layers.length})`}>
                  {d.layers.map(l => (
                    <div key={l.id} style={{ marginBottom: 5, padding: "5px 8px", background: "#0a0d14", borderRadius: 4 }}>
                      <span style={{ color: ACCENT }}>{l.id}</span>
                      <span style={{ color: "#555" }}> · </span>
                      <span style={{ color: "#aab" }}>{l.name}</span>
                      {l.geometryType && <span style={{ color: "#555", marginLeft: 8 }}>({l.geometryType})</span>}
                    </div>
                  ))}
                </Section>
              )}

              {/* Web map operational layers */}
              {d?.operationalLayers && (
                <Section title={`OPERATIONAL LAYERS (${d.operationalLayers.length})`}>
                  {d.operationalLayers.map((l, i) => (
                    <div key={i} style={{ marginBottom: 4, padding: "4px 8px", background: "#0a0d14", borderRadius: 4 }}>
                      <span style={{ color: "#aab" }}>{l.title || l.id}</span>
                      {l.url && <span style={{ color: "#555", fontSize: 9, marginLeft: 6 }}>{l.url.substring(0, 60)}</span>}
                    </div>
                  ))}
                </Section>
              )}

              {/* Raw item JSON */}
              <Section title="RAW ITEM JSON">
                <div style={{ background: "#080b10", borderRadius: 4, padding: "8px 10px", overflowX: "auto" }}>
                  {renderJSON(fi)}
                </div>
              </Section>

              {/* Raw data JSON (if available and meaningful) */}
              {d && d.layers === undefined && d.operationalLayers === undefined && (
                <Section title="RAW DATA JSON">
                  <div style={{ background: "#080b10", borderRadius: 4, padding: "8px 10px", overflowX: "auto" }}>
                    {renderJSON(d)}
                  </div>
                </Section>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

const MetaRow = ({ k, v, copyable, link }) => (
  <div style={{ display: "flex", gap: 8, marginBottom: 4, alignItems: "flex-start" }}>
    <span style={{ color: "#3a3e58", minWidth: 90, fontSize: 10, fontWeight: 700, flexShrink: 0 }}>{k}</span>
    {link
      ? <a href={v} target="_blank" rel="noopener noreferrer" style={{ color: "#60a5fa", fontSize: 10, wordBreak: "break-all" }}>{v}</a>
      : <span style={{ color: "#99a", fontSize: 10, wordBreak: "break-all" }}>{v}</span>
    }
    {copyable && <button onClick={() => navigator.clipboard.writeText(v)} style={{ background: "none", border: "none", color: "#333", cursor: "pointer", fontSize: 10, padding: 0, flexShrink: 0 }}>⧉</button>}
  </div>
)

const Section = ({ title, children }) => (
  <div style={{ marginBottom: 16 }}>
    <div style={{ fontSize: 9, color: "#3a3e58", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 6, borderBottom: "1px solid #0f1520", paddingBottom: 4 }}>{title}</div>
    {children}
  </div>
)

// ── Main ESRIPanel ─────────────────────────────────────────────────────────────
export default function ESRIPanel({ onInjectToKB }) {
  const [query, setQuery]           = useState("")
  const [filter, setFilter]         = useState("")
  const [itemType, setItemType]     = useState("")
  const [results, setResults]       = useState([])
  const [total, setTotal]           = useState(0)
  const [page, setPage]             = useState(1)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)
  const [inspectItem, setInspectItem] = useState(null)
  const [injectedIds, setInjectedIds] = useState(new Set())
  const [hasSearched, setHasSearched] = useState(false)
  const inputRef = useRef(null)

  const NUM = 10

  const doSearch = useCallback(async (p = 1) => {
    setLoading(true)
    setError(null)
    setPage(p)
    const { results: res, total: tot, error: err } = await searchAGOL({
      query, filterExpr: filter, itemType, num: NUM, start: (p - 1) * NUM + 1
    })
    if (err) setError(err)
    setResults(res)
    setTotal(tot)
    setLoading(false)
    setHasSearched(true)
  }, [query, filter, itemType])

  const handleInject = useCallback((item, fullItem = null, data = null) => {
    const { formatItemForContext, summarizeSearchResults } = require ? null : null
    // Build context text — use full metadata if available, else basic item
    import("../data/esri.js").then(({ formatItemForContext: fmt }) => {
      const text = fmt(fullItem || item, data)
      onInjectToKB({
        name: `ESRI: ${item.title} (${item.id})`,
        content: text,
        itemId: item.id,
        source: "ArcGIS Online / Living Atlas"
      })
      setInjectedIds(prev => new Set([...prev, item.id]))
    })
  }, [onInjectToKB])

  const totalPages = Math.ceil(total / NUM)

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: "monospace", position: "relative" }}>

      {/* ── Header ── */}
      <div style={{ padding: "10px 14px", borderBottom: `1px solid ${ACCENT}22`, background: "#090c14", flexShrink: 0 }}>
        <div style={{ fontSize: 9, color: ACCENT, fontWeight: 700, letterSpacing: "0.1em", marginBottom: 6 }}>
          ESRI ARCGIS ONLINE & LIVING ATLAS
        </div>

        {/* Search input */}
        <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && doSearch(1)}
            placeholder="Search layers, maps, services… (e.g. NYC flood zones)"
            style={{
              flex: 1, background: "#0d1020", border: `1px solid ${ACCENT}33`,
              borderRadius: 5, padding: "6px 10px", color: "#dde", fontSize: 11,
              fontFamily: "monospace", outline: "none"
            }}
          />
          <button onClick={() => doSearch(1)} disabled={loading} style={{
            padding: "6px 14px", borderRadius: 5, fontSize: 10, fontWeight: 700,
            border: `1.5px solid ${ACCENT}`, background: `${ACCENT}15`,
            color: ACCENT, cursor: loading ? "not-allowed" : "pointer",
            fontFamily: "monospace", flexShrink: 0
          }}>
            {loading ? <span className="spin">↺</span> : "SEARCH"}
          </button>
        </div>

        {/* Filters row */}
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          <select value={filter} onChange={e => setFilter(e.target.value)} style={{
            background: "#0d1020", border: `1px solid ${ACCENT}22`, borderRadius: 4,
            color: "#778", fontSize: 10, padding: "3px 6px", fontFamily: "monospace",
            cursor: "pointer"
          }}>
            {LIVING_ATLAS_FILTERS.map(f => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <select value={itemType} onChange={e => setItemType(e.target.value)} style={{
            background: "#0d1020", border: `1px solid ${ACCENT}22`, borderRadius: 4,
            color: "#778", fontSize: 10, padding: "3px 6px", fontFamily: "monospace",
            cursor: "pointer"
          }}>
            <option value="">All Types</option>
            {Object.entries(ESRI_ITEM_TYPES).map(([k]) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
          {injectedIds.size > 0 && (
            <span style={{ fontSize: 9, padding: "3px 8px", borderRadius: 4, background: "#4ade8015", color: "#4ade80", border: "1px solid #4ade8033", alignSelf: "center" }}>
              {injectedIds.size} item{injectedIds.size !== 1 ? "s" : ""} in KB
            </span>
          )}
        </div>
      </div>

      {/* ── Results ── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }}>

        {error && (
          <div style={{ fontSize: 11, color: "#f87171", padding: "8px 10px", background: "#1a0808", borderRadius: 5, marginBottom: 8 }}>
            ⚠ {error}
          </div>
        )}

        {!hasSearched && !loading && (
          <div style={{ color: "#2a2e3a", fontSize: 11, textAlign: "center", marginTop: 30 }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>⊕</div>
            Search ArcGIS Online and Living Atlas<br />
            <span style={{ fontSize: 10 }}>Find public layers, maps, and services to inspect metadata<br />and inject into the EMBER knowledge base</span>
            <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 5, justifyContent: "center" }}>
              {["NYC flood zones", "hurricane surge", "FEMA disaster", "hospital locations", "critical infrastructure"].map(s => (
                <button key={s} onClick={() => { setQuery(s); setTimeout(() => doSearch(1), 50) }} style={{
                  fontSize: 10, padding: "3px 9px", borderRadius: 4,
                  border: `1px solid ${ACCENT}33`, background: `${ACCENT}0d`,
                  color: ACCENT, cursor: "pointer", fontFamily: "monospace"
                }}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div style={{ textAlign: "center", color: "#3a3e58", fontSize: 11, marginTop: 20 }}>
            <span className="spin" style={{ marginRight: 6, color: ACCENT }}>↺</span>
            Searching ArcGIS Online…
          </div>
        )}

        {!loading && hasSearched && results.length === 0 && !error && (
          <div style={{ color: "#3a3e58", fontSize: 11, textAlign: "center", marginTop: 20 }}>
            No results found. Try broader terms or different filters.
          </div>
        )}

        {!loading && results.map(item => (
          <ItemCard
            key={item.id}
            item={item}
            onInspect={setInspectItem}
            onInject={handleInject}
            injected={injectedIds.has(item.id)}
          />
        ))}

        {/* Pagination */}
        {total > NUM && (
          <div style={{ display: "flex", gap: 8, justifyContent: "center", alignItems: "center", padding: "10px 0", fontSize: 10, color: "#555" }}>
            <button disabled={page <= 1} onClick={() => doSearch(page - 1)} style={{
              padding: "3px 10px", borderRadius: 4, border: "1px solid #1a1e2e",
              background: "none", color: page <= 1 ? "#222" : "#778",
              cursor: page <= 1 ? "not-allowed" : "pointer", fontFamily: "monospace"
            }}>← prev</button>
            <span>{page} / {totalPages} · {total.toLocaleString()} results</span>
            <button disabled={page >= totalPages} onClick={() => doSearch(page + 1)} style={{
              padding: "3px 10px", borderRadius: 4, border: "1px solid #1a1e2e",
              background: "none", color: page >= totalPages ? "#222" : "#778",
              cursor: page >= totalPages ? "not-allowed" : "pointer", fontFamily: "monospace"
            }}>next →</button>
          </div>
        )}
      </div>

      {/* ── Metadata inspector overlay ── */}
      {inspectItem && (
        <MetadataDrawer
          item={inspectItem}
          onClose={() => setInspectItem(null)}
          onInject={handleInject}
          injected={injectedIds.has(inspectItem.id)}
        />
      )}
    </div>
  )
}
