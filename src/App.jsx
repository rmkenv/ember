import { useState, useRef, useCallback, useEffect } from "react"
import MapPanel from "./components/MapPanel.jsx"
import ChatPanel from "./components/ChatPanel.jsx"
import ESRIPanel from "./components/ESRIPanel.jsx"
import NOAAPanel from "./components/NOAAPanel.jsx"
import { NYC_KB, LIVE_ENDPOINTS, MAP_LAYERS, buildContext, summarizeAPIData } from "./data/nyc.js"
import { summarizeSearchResults } from "./data/esri.js"
import { summarizeNOAAResult } from "./data/noaa.js"
import { streamOllama, pingOllama, OLLAMA_MODEL } from "./hooks/useOllama.js"

const QUICK_QUERIES = [
  "Storm surge risk — Lower Manhattan",
  "Zone 1 evacuation assets at risk from Cat 2 hurricane",
  "Trauma centers and surge capacity",
  "Current NWS weather alerts for NYC",
  "Heat emergency protocol — thresholds and cooling centers",
  "Subway flood exposure and MTA closure protocols",
  "Flash flood response — basement apartment risk",
  "Critical infrastructure in FEMA Zone AE",
]

const KB_MODULES = [
  { id: "floodZones",             label: "FLOOD ZONES"    },
  { id: "evacZones",              label: "EVAC ZONES"     },
  { id: "criticalInfrastructure", label: "INFRASTRUCTURE" },
  { id: "hazardProfiles",         label: "HAZARDS"        },
  { id: "resources",              label: "CONTACTS"       },
]

const MAP_LAYER_TOGGLES = [
  { id: "floodRisk",  label: "FLOOD RISK",  color: "#fb923c" },
  { id: "gauges",     label: "GAUGES",      color: "#4ade80" },
  { id: "shelters",   label: "SHELTERS",    color: "#60a5fa" },
  { id: "hospitals",  label: "TRAUMA CTR",  color: "#f87171" },
  { id: "eoc",        label: "EOC / CMD",   color: "#facc15" },
]

// Separate weather overlay toggles (not marker layers)
const WEATHER_OVERLAY_TOGGLES = [
  { id: "radar", label: "NEXRAD RADAR", color: "#3b82f6" },
  { id: "wind",  label: "WIND OBS",     color: "#4ade80" },
]

// Right-panel tabs
const RIGHT_TABS = [
  { id: "chat", label: "CHAT" },
  { id: "noaa", label: "NOAA DATA" },
  { id: "esri", label: "ESRI / LIVING ATLAS" },
]

async function fetchLiveData(ep) {
  try {
    const res = await fetch(ep.url, { signal: AbortSignal.timeout(7000) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return { success: true, data: await res.json(), name: ep.name, type: ep.type }
  } catch (e) {
    return { success: false, error: e.message, name: ep.name, type: ep.type }
  }
}

export default function App() {
  const [messages, setMessages]             = useState([{ role: "assistant", content: `EMBER initialized — Emergency Management Body of Evidence & Resources\nBackend: Ollama Cloud · ${OLLAMA_MODEL}\nJurisdiction: New York City (5 boroughs)\n\nKnowledge base loaded: Flood zones · Evacuation zones · Critical infrastructure · Hazard profiles · Contacts\nMap loaded: Trauma centers · Shelters · Flood risk areas · Stream gauges · EOC locations\nESRI panel: Search ArcGIS Online & Living Atlas — inspect metadata and inject into KB\n\nClick a map marker, search ESRI layers, or state an incident scenario to begin.` }])
  const [input, setInput]                   = useState("")
  const [streaming, setStreaming]           = useState(false)
  const [activeKB, setActiveKB]             = useState(["floodZones","evacZones","criticalInfrastructure","hazardProfiles","resources"])
  const [activeMapLayers, setActiveMapLayers] = useState(["floodRisk","hospitals","shelters","gauges","eoc"])
  const [showRadar, setShowRadar]           = useState(true)
  const [showWind,  setShowWind]            = useState(true)
  const [files, setFiles]                   = useState([])          // uploaded docs
  const [esriItems, setEsriItems]           = useState([])          // ESRI metadata injections
  const [noaaItems, setNoaaItems]           = useState([])          // NOAA data injections
  const [apiResults, setApiResults]         = useState([])
  const [apiStatus, setApiStatus]           = useState("idle")
  const [fetchingAPIs, setFetchingAPIs]     = useState(false)
  const [ollamaOk, setOllamaOk]             = useState(null)
  const [mapWidth, setMapWidth]             = useState(42)          // percent
  const [rightTab, setRightTab]             = useState("chat")
  const [selectedMarker, setSelectedMarker] = useState(null)
  const [showQuick, setShowQuick]           = useState(false)
  const fileInputRef  = useRef(null)
  const abortRef      = useRef(false)
  const abortController = useRef(null)
  const dragging      = useRef(false)

  useEffect(() => { pingOllama().then(ok => setOllamaOk(ok)) }, [])

  // ── Divider drag ──
  const onDividerMouseDown = useCallback((e) => {
    dragging.current = true
    e.preventDefault()
    const onMove = (ev) => {
      if (!dragging.current) return
      setMapWidth(Math.min(65, Math.max(22, (ev.clientX / window.innerWidth) * 100)))
    }
    const onUp = () => { dragging.current = false; window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp) }
    window.addEventListener("mousemove", onMove)
    window.addEventListener("mouseup", onUp)
  }, [])

  const toggleKB  = id => setActiveKB(p  => p.includes(id) ? p.filter(m=>m!==id) : [...p,id])
  const toggleMap = id => setActiveMapLayers(p => p.includes(id) ? p.filter(m=>m!==id) : [...p,id])

  const fetchAPIs = async () => {
    setFetchingAPIs(true)
    const results = await Promise.all(LIVE_ENDPOINTS.map(fetchLiveData))
    setApiResults(results)
    setApiStatus(results.some(r=>r.success) ? "live" : "error")
    setFetchingAPIs(false)
  }

  // Derive live gauge readings keyed by station name for MapPanel popup enrichment
  // Structure: { "Battery Park Tidal Gauge": { level: "4.21", unit: "ft MLLW", status: "normal" }, … }
  const liveReadings = (() => {
    const readings = {}
    for (const r of apiResults) {
      if (!r.success) continue
      // USGS stream gauge data
      if (r.type === "flood" && r.data?.value?.timeSeries) {
        for (const ts of r.data.value.timeSeries) {
          const siteName = ts.sourceInfo?.siteName ?? ""
          const val = ts.values?.[0]?.value?.[0]?.value
          if (val != null) readings[siteName] = { level: val, unit: "ft", source: "USGS", status: parseFloat(val) > 10 ? "flood" : parseFloat(val) > 5 ? "elevated" : "normal" }
        }
      }
      // NWS active alerts — flag relevant zones
      if (r.type === "weather" && r.data?.features) {
        for (const f of r.data.features) {
          const event = f.properties?.event ?? ""
          if (event.toLowerCase().includes("flood") || event.toLowerCase().includes("surge")) {
            readings["__alert__"] = { event, severity: f.properties?.severity, headline: f.properties?.headline?.substring(0, 120) }
          }
        }
      }
    }
    return readings
  })()

  const ingestFile = useCallback(file => {
    const reader = new FileReader()
    reader.onload = e => setFiles(p => [...p, { name: file.name, content: e.target.result }])
    reader.readAsText(file)
  }, [])

  // Called by NOAAPanel when user adds a fetched endpoint to KB
  const handleNOAAInject = useCallback((noaaItem) => {
    setNoaaItems(prev => {
      const exists = prev.find(i => i.itemId === noaaItem.itemId)
      if (exists) return prev
      return [...prev, noaaItem]
    })
    setRightTab("chat")
    setMessages(prev => [...prev, {
      role: "assistant",
      content: `✓ NOAA data added to knowledge base:\n${noaaItem.name}\n\nYou can now query this data. Try: "Summarize the latest ${noaaItem.name.replace("NOAA: ","")} data and flag any emergency-relevant readings."`
    }])
  }, [])

  // Called by ESRIPanel when user clicks "+ ADD TO KB"
  const handleESRIInject = useCallback((esriItem) => {
    setEsriItems(prev => {
      const exists = prev.find(i => i.itemId === esriItem.itemId)
      if (exists) return prev
      return [...prev, esriItem]
    })
    // Switch to chat tab and note the injection
    setRightTab("chat")
    setMessages(prev => [...prev, {
      role: "assistant",
      content: `✓ ESRI item added to knowledge base:\n${esriItem.name}\n\nYou can now query this layer's metadata. Try: "What does the ${esriItem.name.replace("ESRI: ","").split(" (")[0]} layer cover and how can it support this incident?"`
    }])
  }, [])

  const handleMarkerClick = useCallback((marker) => {
    setSelectedMarker(marker)
    setRightTab("chat")
    sendQuery(`Tell me about emergency considerations for ${marker.name} — ${marker.note}`)
  }, [])

  // Build full context including ESRI injections
  const buildFullContext = useCallback(() => {
    const base = buildContext(files, apiResults, activeKB)
    let extra = ""
    if (noaaItems.length) {
      extra += "--- NOAA OPEN DATA (user-fetched) ---\n" +
        noaaItems.map(i => i.content).join("\n\n") + "\n\n"
    }
    if (esriItems.length) {
      extra += "--- ESRI / LIVING ATLAS LAYERS (user-selected metadata) ---\n" +
        esriItems.map(i => i.content).join("\n\n") + "\n"
    }
    return base + extra
  }, [files, apiResults, activeKB, esriItems])

  const sendQuery = async (override) => {
    const q = (override || input).trim()
    if (!q || streaming) return
    setInput("")
    setShowQuick(false)
    setRightTab("chat")
    abortRef.current = false

    const userMsg = { role: "user", content: q }
    const history = [...messages, userMsg]
    setMessages([...history, { role: "assistant", content: "" }])
    setStreaming(true)

    const context = buildFullContext()
    abortController.current = new AbortController()

    try {
      let full = ""
      for await (const token of streamOllama(history, context, abortController.current.signal)) {
        if (abortRef.current) break
        full += token
        setMessages(prev => {
          const u = [...prev]
          u[u.length - 1] = { role: "assistant", content: full }
          return u
        })
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        setMessages(prev => {
          const u = [...prev]
          u[u.length - 1] = { role: "assistant", content: `CONNECTION ERROR: ${err.message}` }
          return u
        })
      }
    } finally {
      setStreaming(false)
    }
  }

  const stopStreaming = () => { abortRef.current = true; abortController.current?.abort() }

  // ── Pill component ──
  const pill = (label, active, onClick, color = "#e8372c") => (
    <button onClick={onClick} style={{
      padding: "2px 9px", borderRadius: 20, fontSize: 9.5, fontWeight: 700,
      letterSpacing: "0.05em", cursor: "pointer", transition: "all 0.12s",
      border: `1.5px solid ${active ? color : "#1e2030"}`,
      background: active ? `${color}18` : "transparent",
      color: active ? color : "#3a3e50", fontFamily: "inherit"
    }}>{label}</button>
  )

  const statusDot = (ok, label) => (
    <span style={{ fontSize: 9.5, fontFamily: "monospace", color: ok === true ? "#4ade80" : ok === false ? "#f87171" : "#444" }}>
      {ok === true ? "●" : ok === false ? "●" : "○"} {label}
    </span>
  )

  const esriCount  = esriItems.length
  const noaaCount  = noaaItems.length

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#07090d", overflow: "hidden" }}>

      {/* ══ Header ══ */}
      <div style={{ flexShrink:0, padding:"10px 18px", borderBottom:"1px solid #111820", background:"#090c12", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <div style={{ width:26, height:26, background:"#e8372c", borderRadius:5, display:"flex", alignItems:"center", justifyContent:"center", fontWeight:700, fontSize:13, color:"#fff" }}>E</div>
          <span style={{ fontWeight:700, letterSpacing:"0.14em", fontSize:14, color:"#fff" }}>EMBER</span>
          <span style={{ fontSize:9, color:"#2a2e3a", letterSpacing:"0.06em" }}>NYC EMERGENCY MANAGEMENT · v1.1</span>
        </div>
        <div style={{ display:"flex", gap:14, alignItems:"center", fontSize:9.5, fontFamily:"monospace" }}>
          {statusDot(true, "ACTIVE")}
          {statusDot(ollamaOk, ollamaOk ? `OLLAMA CLOUD · ${OLLAMA_MODEL}` : "OLLAMA OFFLINE")}
          {statusDot(apiStatus==="live"?true:apiStatus==="error"?false:null, apiStatus==="live"?"FEEDS LIVE":apiStatus==="error"?"FEED ERR":"FEEDS IDLE")}
          <span style={{ color:"#2a2e3a" }}>{files.length} doc{files.length!==1?"s":""}</span>
          {noaaItems.length > 0 && <span style={{ color:"#34d399" }}>▶ {noaaItems.length} NOAA feed{noaaItems.length!==1?"s":""}</span>}
          {esriCount > 0 && <span style={{ color:"#a78bfa" }}>⊕ {esriCount} ESRI layer{esriCount!==1?"s":""}</span>}
        </div>
      </div>

      {/* ══ Ollama offline warning ══ */}
      {ollamaOk === false && (
        <div style={{ flexShrink:0, background:"#1a0808", borderBottom:"1px solid #3a1010", padding:"6px 18px", fontSize:10.5, color:"#f87171" }}>
          ⚠ Ollama Cloud unreachable — check VITE_OLLAMA_API_KEY in .env.local · <a href="https://ollama.com/settings/keys" target="_blank" rel="noopener noreferrer" style={{ color:"#f87171" }}>Get API key</a>
        </div>
      )}

      {/* ══ Control Rail ══ */}
      <div style={{ flexShrink:0, padding:"7px 18px", borderBottom:"1px solid #0f1218", background:"#090c12", display:"flex", gap:5, flexWrap:"wrap", alignItems:"center" }}>
        <span style={{ fontSize:8.5, color:"#2a2e3a", fontWeight:700, letterSpacing:"0.1em", marginRight:3 }}>KB</span>
        {KB_MODULES.map(m => pill(m.label, activeKB.includes(m.id), () => toggleKB(m.id)))}
        <div style={{ width:1, height:14, background:"#1a1e28", margin:"0 4px" }} />
        <span style={{ fontSize:8.5, color:"#2a2e3a", fontWeight:700, letterSpacing:"0.1em", marginRight:3 }}>MAP</span>
        {MAP_LAYER_TOGGLES.map(m => pill(m.label, activeMapLayers.includes(m.id), () => toggleMap(m.id), m.color))}
        <div style={{ width:1, height:14, background:"#1a1e28", margin:"0 4px" }} />
        <span style={{ fontSize:8.5, color:"#2a2e3a", fontWeight:700, letterSpacing:"0.1em", marginRight:3 }}>WX</span>
        {pill("NEXRAD RADAR", showRadar, () => setShowRadar(p => !p), "#3b82f6")}
        {pill("WIND OBS",     showWind,  () => setShowWind(p  => !p), "#4ade80")}
        <div style={{ marginLeft:"auto", display:"flex", gap:7 }}>
          <button onClick={fetchAPIs} disabled={fetchingAPIs} style={{ padding:"2px 10px", borderRadius:4, fontSize:9.5, fontWeight:700, border:"1.5px solid #4ade8044", background:"transparent", color:"#4ade80", cursor:"pointer", fontFamily:"inherit", opacity:fetchingAPIs?0.5:1 }}>
            {fetchingAPIs ? <span className="spin">↺</span> : "↺"} LIVE FEEDS
          </button>
          <button onClick={() => fileInputRef.current?.click()} style={{ padding:"2px 10px", borderRadius:4, fontSize:9.5, fontWeight:700, border:"1.5px solid #60a5fa44", background:"transparent", color:"#60a5fa", cursor:"pointer", fontFamily:"inherit" }}>⬆ INGEST DOC</button>
          <input ref={fileInputRef} type="file" multiple accept=".txt,.csv,.json,.geojson,.md" onChange={e => Array.from(e.target.files).forEach(ingestFile)} style={{ display:"none" }} />
        </div>
      </div>

      {/* ══ Sub-strips ══ */}
      {(files.length > 0 || esriItems.length > 0) && (
        <div style={{ flexShrink:0, padding:"4px 18px", borderBottom:"1px solid #0c1018", background:"#090f1a", display:"flex", gap:5, flexWrap:"wrap", alignItems:"center" }}>
          {files.length > 0 && <>
            <span style={{ fontSize:8.5, color:"#60a5fa", fontWeight:700 }}>DOCS</span>
            {files.map((f,i) => (
              <span key={i} style={{ fontSize:9.5, padding:"1px 8px", borderRadius:4, background:"#60a5fa0e", color:"#60a5fa", border:"1px solid #60a5fa1a" }}>
                {f.name}
                <button onClick={() => setFiles(p=>p.filter((_,j)=>j!==i))} style={{ marginLeft:5, background:"none", border:"none", color:"#f87171", cursor:"pointer", fontSize:9 }}>✕</button>
              </span>
            ))}
          </>}
          {noaaItems.length > 0 && <>
            <span style={{ fontSize:8.5, color:"#34d399", fontWeight:700, marginLeft:files.length?8:0 }}>NOAA</span>
            {noaaItems.map((item,i) => (
              <span key={i} style={{ fontSize:9.5, padding:"1px 8px", borderRadius:4, background:"#34d39910", color:"#34d399", border:"1px solid #34d39920" }}>
                {item.name.replace("NOAA: ","").substring(0,28)}…
                <button onClick={() => setNoaaItems(p=>p.filter((_,j)=>j!==i))} style={{ marginLeft:5, background:"none", border:"none", color:"#f87171", cursor:"pointer", fontSize:9 }}>✕</button>
              </span>
            ))}
          </>}
          {esriItems.length > 0 && <>
            <span style={{ fontSize:8.5, color:"#a78bfa", fontWeight:700, marginLeft:(files.length||noaaItems.length)?8:0 }}>ESRI KB</span>
            {esriItems.map((item,i) => (
              <span key={i} style={{ fontSize:9.5, padding:"1px 8px", borderRadius:4, background:"#a78bfa0e", color:"#a78bfa", border:"1px solid #a78bfa1a" }}>
                {item.name.replace("ESRI: ","").substring(0,30)}…
                <button onClick={() => setEsriItems(p=>p.filter((_,j)=>j!==i))} style={{ marginLeft:5, background:"none", border:"none", color:"#f87171", cursor:"pointer", fontSize:9 }}>✕</button>
              </span>
            ))}
          </>}
        </div>
      )}

      {apiResults.length > 0 && (
        <div style={{ flexShrink:0, padding:"4px 18px", borderBottom:"1px solid #0c1018", background:"#090f12", display:"flex", gap:5, flexWrap:"wrap", alignItems:"center" }}>
          <span style={{ fontSize:8.5, color:"#4ade80", fontWeight:700 }}>FEEDS</span>
          {apiResults.map((r,i) => (
            <span key={i} style={{ fontSize:9.5, padding:"1px 8px", borderRadius:4, background:r.success?"#4ade800e":"#f871710e", color:r.success?"#4ade80":"#f87171", border:`1px solid ${r.success?"#4ade801a":"#f871711a"}` }}>
              {r.success?"●":"○"} {r.name}
            </span>
          ))}
        </div>
      )}

      {/* ══ Main: map | divider | right panel ══ */}
      <div style={{ flex:1, display:"flex", overflow:"hidden" }}
        onDrop={e => { e.preventDefault(); Array.from(e.dataTransfer.files).forEach(ingestFile) }}
        onDragOver={e => e.preventDefault()}
      >
        {/* Map */}
        <div style={{ width:`${mapWidth}%`, flexShrink:0, position:"relative", borderRight:"1px solid #0f1520" }}>
          <MapPanel activeLayers={activeMapLayers} onMarkerClick={handleMarkerClick} showRadar={showRadar} showWind={showWind} liveReadings={liveReadings} />

          {/* Legend */}
          <div style={{ position:"absolute", bottom:24, left:10, zIndex:1000, background:"#07090dee", border:"1px solid #1a1e28", borderRadius:6, padding:"8px 10px", fontSize:9.5, fontFamily:"monospace" }}>
            {MAP_LAYER_TOGGLES.filter(l=>activeMapLayers.includes(l.id)).map(l => (
              <div key={l.id} style={{ display:"flex", alignItems:"center", gap:5, marginBottom:3, color:l.color }}>
                <div style={{ width:7, height:7, borderRadius:"50%", background:l.color, flexShrink:0 }} />
                {l.label}
              </div>
            ))}
            {showRadar && (
              <div style={{ display:"flex", alignItems:"center", gap:5, marginBottom:3, color:"#3b82f6" }}>
                <div style={{ width:7, height:7, borderRadius:2, background:"#3b82f6", flexShrink:0 }} />
                NEXRAD RADAR
              </div>
            )}
            {showWind && (
              <div style={{ display:"flex", alignItems:"center", gap:5, color:"#4ade80" }}>
                <span style={{ fontSize:11 }}>↑</span> WIND OBS
              </div>
            )}
          </div>

          {selectedMarker && (
            <div style={{ position:"absolute", top:10, left:10, right:10, zIndex:1000, background:"#0d1520ee", border:`1px solid ${selectedMarker.color}44`, borderRadius:6, padding:"7px 10px", fontSize:10, fontFamily:"monospace", color:"#ccd" }}>
              <div style={{ fontWeight:700, color:selectedMarker.color, marginBottom:2 }}>{selectedMarker.name}</div>
              <div style={{ color:"#778", fontSize:9 }}>{selectedMarker.note}</div>
              <button onClick={() => setSelectedMarker(null)} style={{ position:"absolute", top:6, right:8, background:"none", border:"none", color:"#444", cursor:"pointer", fontSize:11 }}>✕</button>
            </div>
          )}
        </div>

        {/* Divider */}
        <div onMouseDown={onDividerMouseDown} style={{ width:5, flexShrink:0, cursor:"col-resize", background:"#0d1018", borderLeft:"1px solid #111820", borderRight:"1px solid #111820", display:"flex", alignItems:"center", justifyContent:"center" }}>
          <div style={{ width:2, height:32, background:"#1e2230", borderRadius:1 }} />
        </div>

        {/* Right panel */}
        <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>

          {/* Tab bar */}
          <div style={{ flexShrink:0, display:"flex", borderBottom:"1px solid #0f1218", background:"#090c12" }}>
            {RIGHT_TABS.map(tab => (
              <button key={tab.id} onClick={() => setRightTab(tab.id)} style={{
                padding:"8px 16px", fontSize:10, fontWeight:700, letterSpacing:"0.08em",
                border:"none", borderBottom:`2px solid ${rightTab===tab.id ? (tab.id==="esri"?"#a78bfa":"#e8372c") : "transparent"}`,
                background:"transparent", color: rightTab===tab.id ? (tab.id==="esri"?"#a78bfa":"#e8372c") : "#3a3e50",
                cursor:"pointer", fontFamily:"monospace", transition:"all 0.12s"
              }}>
                {tab.label}
                {tab.id==="esri" && esriCount>0 && (
                  <span style={{ marginLeft:6, fontSize:9, padding:"1px 5px", borderRadius:10, background:"#a78bfa22", color:"#a78bfa" }}>{esriCount}</span>
                )}
                {tab.id==="noaa" && noaaItems.length>0 && (
                  <span style={{ marginLeft:6, fontSize:9, padding:"1px 5px", borderRadius:10, background:"#34d39922", color:"#34d399" }}>{noaaItems.length}</span>
                )}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>

            {/* ── CHAT TAB ── */}
            {rightTab === "chat" && (
              <>
                <ChatPanel messages={messages} streaming={streaming} modelName={OLLAMA_MODEL} onStop={stopStreaming} />

                <div style={{ flexShrink:0, borderTop:"1px solid #0d1018", padding:"6px 14px 0" }}>
                  <button onClick={() => setShowQuick(p=>!p)} style={{ fontSize:9, color:"#333", background:"none", border:"none", cursor:"pointer", fontFamily:"monospace", letterSpacing:"0.06em", marginBottom:4 }}>
                    {showQuick?"▾":"▸"} QUICK QUERIES
                  </button>
                  {showQuick && (
                    <div style={{ display:"flex", gap:5, flexWrap:"wrap", paddingBottom:6 }}>
                      {QUICK_QUERIES.map((q,i) => (
                        <button key={i} onClick={() => sendQuery(q)} disabled={streaming} style={{ fontSize:9.5, padding:"3px 9px", borderRadius:4, border:"1px solid #13171f", background:"#0c0f14", color:"#3a3e50", cursor:streaming?"not-allowed":"pointer", fontFamily:"inherit", letterSpacing:"0.02em", transition:"all 0.1s" }}
                          onMouseEnter={e=>{e.target.style.color="#aaa";e.target.style.borderColor="#e8372c44"}}
                          onMouseLeave={e=>{e.target.style.color="#3a3e50";e.target.style.borderColor="#13171f"}}
                        >{q}</button>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ flexShrink:0, padding:"8px 14px 14px", borderTop:"1px solid #0d1018" }}>
                  <div style={{ display:"flex", gap:8, alignItems:"flex-end", background:"#0c0f15", border:"1px solid #181c24", borderRadius:7, padding:"9px 12px" }}>
                    <textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendQuery()}}} placeholder="Incident type + location… or ask about any ESRI layer in the KB" rows={2} style={{ flex:1, background:"none", border:"none", outline:"none", color:"#ccd", fontSize:12, fontFamily:"inherit", lineHeight:1.6 }} />
                    <button onClick={()=>sendQuery()} disabled={streaming||!input.trim()} style={{ width:30, height:30, borderRadius:5, flexShrink:0, background:streaming||!input.trim()?"#111":"#e8372c", border:"none", cursor:streaming||!input.trim()?"not-allowed":"pointer", color:"#fff", fontSize:14, display:"flex", alignItems:"center", justifyContent:"center", transition:"background 0.15s" }}>
                      {streaming?<span className="spin" style={{fontSize:12}}>↺</span>:"↑"}
                    </button>
                  </div>
                  <div style={{ fontSize:8.5, color:"#1a1e28", marginTop:4, letterSpacing:"0.04em" }}>
                    ENTER send · SHIFT+ENTER newline · drag files to ingest · drag divider to resize
                  </div>
                </div>
              </>
            )}

            {/* ── NOAA TAB ── */}
            {rightTab === "noaa" && (
              <NOAAPanel onInjectToKB={handleNOAAInject} />
            )}

            {/* ── ESRI TAB ── */}
            {rightTab === "esri" && (
              <ESRIPanel onInjectToKB={handleESRIInject} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
