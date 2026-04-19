import { useEffect, useRef, useState, useCallback } from "react"
import { MAP_LAYERS } from "../data/nyc.js"

const TILE_URL  = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'

// Iowa State MESONET NEXRAD composite reflectivity tiles — free, no key, ~5 min latency
// Cache-bust with 5-minute epoch so the browser re-fetches fresh tiles automatically
const radarEpoch  = () => Math.floor(Date.now() / 300_000) // changes every 5 min
const RADAR_TILE_URL  = () =>
  `https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png?_=${radarEpoch()}`
const RADAR_TILE_ATTR = 'NEXRAD Radar &copy; <a href="https://mesonet.agron.iastate.edu/">Iowa State MESONET</a>'

// Wind barb direction lookup — returns CSS rotation for "from" bearing
// Arrow points INTO the wind (meteorological convention)
function windArrowSvg(speedMph, dirDeg, gustMph) {
  const color = speedMph < 15 ? "#4ade80"
              : speedMph < 25 ? "#facc15"
              : speedMph < 40 ? "#fb923c"
              : "#f87171"
  const size = speedMph < 20 ? 18 : speedMph < 35 ? 22 : 28
  const label = gustMph ? `${speedMph}g${gustMph}` : `${speedMph}`
  // Arrow points in the direction the wind is going TO (rotation from north)
  const toDir = (dirDeg + 180) % 360
  return `
    <div style="
      display:flex;flex-direction:column;align-items:center;gap:1px;
      transform:rotate(0deg);cursor:default;
    ">
      <div style="
        font-size:${size}px;line-height:1;
        transform:rotate(${toDir}deg);
        filter:drop-shadow(0 0 3px ${color}88);
      ">↑</div>
      <div style="
        font-size:9px;font-family:monospace;font-weight:700;
        color:${color};background:#07090dcc;
        padding:1px 3px;border-radius:2px;white-space:nowrap;
        border:1px solid ${color}44;
      ">${label}mph</div>
    </div>`
}

function makeIcon(L, color, emoji) {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:28px;height:28px;border-radius:50%;
      background:${color}22;border:2px solid ${color};
      display:flex;align-items:center;justify-content:center;
      font-size:13px;cursor:pointer;
      box-shadow:0 0 8px ${color}44;
    ">${emoji}</div>`,
    iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -16]
  })
}

// NYC observation station coords — we'll place wind arrows at actual station locations
const WIND_STATIONS = [
  { id: "KNYC", name: "Central Park",  lat: 40.7789, lng: -73.9692 },
  { id: "KJFK", name: "JFK Airport",   lat: 40.6413, lng: -73.7781 },
  { id: "KEWR", name: "Newark",        lat: 40.6895, lng: -74.1745 },
  { id: "KLGA", name: "LaGuardia",     lat: 40.7772, lng: -73.8726 },
  { id: "KBDR", name: "Bridgeport",    lat: 41.1635, lng: -73.1262 },
  { id: "KHPN", name: "White Plains",  lat: 41.0670, lng: -73.7076 },
]

async function fetchStationObs(stationId) {
  try {
    const r = await fetch(`https://api.weather.gov/stations/${stationId}/observations/latest`, {
      signal: AbortSignal.timeout(6000),
      headers: { "User-Agent": "EMBER/1.0" }
    })
    if (!r.ok) return null
    const d = await r.json()
    const p = d.properties
    return {
      stationId,
      speedMph: p.windSpeed?.value != null
        ? +(p.windSpeed.value * 0.621371).toFixed(0) : null,
      gustMph: p.windGust?.value != null
        ? +(p.windGust.value * 0.621371).toFixed(0) : null,
      dirDeg: p.windDirection?.value != null
        ? +p.windDirection.value.toFixed(0) : null,
      tempF: p.temperature?.value != null
        ? +(p.temperature.value * 9/5 + 32).toFixed(0) : null,
      precipIn: p.precipitationLastHour?.value != null
        ? +(p.precipitationLastHour.value * 0.0393701).toFixed(2) : null,
      desc: p.textDescription ?? "",
      time: p.timestamp ?? null,
    }
  } catch { return null }
}

// ── Build popup HTML — shared for static and live-enriched markers ─────────────
function buildPopupHTML(color, icon, f, reading) {
  const statusColor = reading?.status === "flood"    ? "#f87171"
                    : reading?.status === "elevated" ? "#facc15"
                    : reading            ? "#4ade80"
                    : null

  return `<div style="font-family:'IBM Plex Mono',monospace">
    <div style="font-weight:700;color:${color};margin-bottom:4px;font-size:12px">${icon} ${f.name}</div>
    ${f.borough ? `<div style="color:#888;font-size:10px;margin-bottom:4px">${f.borough}</div>` : ""}
    <div style="font-size:11px;color:#aac;margin-bottom:${reading ? 6 : 0}px">${f.note}</div>
    ${reading ? `
    <div style="border-top:1px solid #1e2a40;padding-top:6px;margin-top:2px">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
        <div style="width:8px;height:8px;border-radius:50%;background:${statusColor};flex-shrink:0"></div>
        <span style="color:${statusColor};font-weight:700;font-size:11px">${reading.level} ${reading.unit}</span>
        <span style="color:#556;font-size:9px">${reading.status?.toUpperCase()}</span>
      </div>
      <div style="color:#446;font-size:9px">${reading.source} · live reading</div>
    </div>` : ""}
  </div>`
}

export default function MapPanel({ activeLayers, onMarkerClick, showRadar, showWind, liveReadings = {} }) {
  const mapRef     = useRef(null)
  const leafletRef = useRef(null)
  const layerRefs  = useRef({})
  const radarRef   = useRef(null)
  const windRef    = useRef(null)   // L.layerGroup for wind arrows
  const [ready, setReady]         = useState(false)
  const [radarTime, setRadarTime] = useState(null)
  const [windLoading, setWindLoading] = useState(false)
  const [windObs, setWindObs]     = useState([])

  // ── Init map ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (leafletRef.current) return
    import("leaflet").then(({ default: L }) => {
      const map = L.map(mapRef.current, {
        center: [40.7128, -74.006],
        zoom: 10,
        zoomControl: true,
        attributionControl: true,
      })

      L.tileLayer(TILE_URL, {
        attribution: TILE_ATTR, maxZoom: 19, subdomains: "abcd"
      }).addTo(map)

      // ── Radar tile layer (on by default) ─────────────────────────────────
      const radarLayer = L.tileLayer(RADAR_TILE_URL(), {
        attribution: RADAR_TILE_ATTR,
        opacity: 0.65,
        maxZoom: 19,
      })
      radarRef.current = radarLayer
      setRadarTime(new Date().toLocaleTimeString())

      // ── Wind arrow layer group ─────────────────────────────────────────────
      const windGroup = L.layerGroup()
      windRef.current = windGroup

      // ── Marker layers ──────────────────────────────────────────────────────
      for (const [key, layer] of Object.entries(MAP_LAYERS)) {
        const group = L.layerGroup()
        layer.features.forEach(f => {
          const marker = L.marker([f.lat, f.lng], { icon: makeIcon(L, layer.color, layer.icon) })
          marker._emberKey     = key
          marker._emberFeature = f
          marker._emberColor   = layer.color
          marker._emberIcon    = layer.icon
          marker.bindPopup(buildPopupHTML(layer.color, layer.icon, f, null))
          marker.on("click", () => onMarkerClick?.({ ...f, layerLabel: layer.label, color: layer.color }))
          group.addLayer(marker)
        })
        layerRefs.current[key] = group
      }

      leafletRef.current = map
      setReady(true)
    })

    return () => {
      if (leafletRef.current) { leafletRef.current.remove(); leafletRef.current = null }
    }
  }, [])

  // ── Enrich gauge popups when live readings arrive ──────────────────────────
  useEffect(() => {
    if (!ready || !Object.keys(liveReadings).length) return
    import("leaflet").then(({ default: L }) => {
      const gaugeGroup = layerRefs.current["gauges"]
      if (!gaugeGroup) return
      gaugeGroup.eachLayer(marker => {
        const f = marker._emberFeature
        if (!f) return
        // Match USGS site name to gauge feature name (partial, case-insensitive)
        const reading = Object.entries(liveReadings).find(([siteName]) =>
          siteName.toLowerCase().includes(f.name.split(",")[0].toLowerCase().split(" ")[0]) ||
          f.name.toLowerCase().includes(siteName.toLowerCase().split(" at ")[0])
        )?.[1]
        marker.setPopupContent(buildPopupHTML(marker._emberColor, marker._emberIcon, f, reading ?? null))
        // Re-color icon by flood status
        if (reading?.status) {
          const c = { flood: "#f87171", elevated: "#facc15", normal: "#4ade80" }[reading.status] ?? "#4ade80"
          marker.setIcon(makeIcon(L, c, marker._emberIcon))
          marker._emberColor = c
        }
      })
    })
  }, [liveReadings, ready])

  // ── Toggle marker layers ───────────────────────────────────────────────────
  useEffect(() => {
    if (!ready || !leafletRef.current) return
    const map = leafletRef.current
    for (const [key, group] of Object.entries(layerRefs.current)) {
      if (activeLayers.includes(key)) { if (!map.hasLayer(group)) group.addTo(map) }
      else                            { if ( map.hasLayer(group)) map.removeLayer(group) }
    }
  }, [activeLayers, ready])

  // ── Auto-refresh radar tiles every 5 minutes ──────────────────────────────
  useEffect(() => {
    if (!ready) return
    const id = setInterval(() => {
      if (!leafletRef.current || !radarRef.current) return
      const map = leafletRef.current
      if (!map.hasLayer(radarRef.current)) return
      // Replace tile layer with fresh cache-busted URL
      import("leaflet").then(({ default: L }) => {
        map.removeLayer(radarRef.current)
        const newLayer = L.tileLayer(RADAR_TILE_URL(), {
          attribution: RADAR_TILE_ATTR,
          opacity: 0.65,
          maxZoom: 19,
        })
        newLayer.addTo(map)
        // Bring all marker layers above radar
        for (const group of Object.values(layerRefs.current)) {
          if (map.hasLayer(group)) { map.removeLayer(group); group.addTo(map) }
        }
        if (windRef.current && map.hasLayer(windRef.current)) {
          map.removeLayer(windRef.current); windRef.current.addTo(map)
        }
        radarRef.current = newLayer
        setRadarTime(new Date().toLocaleTimeString())
      })
    }, 300_000) // 5 minutes
    return () => clearInterval(id)
  }, [ready])

  // ── Auto-refresh wind obs every 5 minutes when layer is visible ────────────
  useEffect(() => {
    if (!ready || !showWind) return
    // Fetch immediately when enabled
    fetchWindObs()
    const id = setInterval(() => {
      fetchWindObs()
    }, 300_000) // 5 minutes
    return () => clearInterval(id)
  }, [ready, showWind, fetchWindObs])

  // ── Radar layer toggle ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!ready || !leafletRef.current || !radarRef.current) return
    const map = leafletRef.current
    if (showRadar) {
      if (!map.hasLayer(radarRef.current)) radarRef.current.addTo(map)
      // Bring markers above radar
      for (const group of Object.values(layerRefs.current)) {
        if (map.hasLayer(group)) { map.removeLayer(group); group.addTo(map) }
      }
      setRadarTime(new Date().toLocaleTimeString())
    } else {
      if (map.hasLayer(radarRef.current)) map.removeLayer(radarRef.current)
    }
  }, [showRadar, ready])

  // ── Wind layer toggle + fetch ──────────────────────────────────────────────
  const fetchWindObs = useCallback(async () => {
    if (!ready || !leafletRef.current || !windRef.current) return
    setWindLoading(true)
    import("leaflet").then(async ({ default: L }) => {
      const obs = await Promise.all(WIND_STATIONS.map(s =>
        fetchStationObs(s.id).then(data => data ? { ...s, ...data } : null)
      ))
      const valid = obs.filter(Boolean)
      setWindObs(valid)

      // Clear old wind markers
      windRef.current.clearLayers()

      // Add wind arrow div markers
      valid.forEach(o => {
        if (o.speedMph == null || o.dirDeg == null) return
        const icon = L.divIcon({
          className: "",
          html: windArrowSvg(o.speedMph, o.dirDeg, o.gustMph),
          iconSize: [50, 40],
          iconAnchor: [25, 20],
        })
        const marker = L.marker([o.lat, o.lng], { icon, zIndexOffset: 500 })
        marker.bindPopup(`
          <div style="font-family:monospace;font-size:11px">
            <div style="font-weight:700;color:#60a5fa;margin-bottom:4px">${o.id} — ${o.name}</div>
            <div>Wind: <b>${o.speedMph}mph</b> from ${o.dirDeg}°${o.gustMph ? ` (gusts ${o.gustMph}mph)` : ""}</div>
            ${o.precipIn != null ? `<div>Precip (1h): <b>${o.precipIn}"</b></div>` : ""}
            ${o.tempF    != null ? `<div>Temp: <b>${o.tempF}°F</b></div>` : ""}
            <div style="color:#556;margin-top:3px">${o.desc}</div>
            <div style="color:#444;font-size:9px;margin-top:3px">${o.time ? new Date(o.time).toLocaleTimeString() : ""}</div>
          </div>
        `)
        windRef.current.addLayer(marker)
      })

      setWindLoading(false)
    })
  }, [ready])

  // ── Wind layer toggle + fetch ──────────────────────────────────────────────
  useEffect(() => {
    if (!ready || !leafletRef.current || !windRef.current) return
    const map = leafletRef.current
    if (showWind) {
      if (!map.hasLayer(windRef.current)) windRef.current.addTo(map)
      // fetchWindObs is called by the auto-refresh interval effect above
    } else {
      if (map.hasLayer(windRef.current)) map.removeLayer(windRef.current)
    }
  }, [showWind, ready])

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={mapRef} style={{ width: "100%", height: "100%" }} />

      {/* ── Radar timestamp badge ── */}
      {showRadar && radarTime && (
        <div style={{
          position: "absolute", bottom: 56, left: 10, zIndex: 1000,
          background: "#07090dee", border: "1px solid #3b82f655",
          borderRadius: 4, padding: "3px 8px",
          fontSize: 9, fontFamily: "monospace", color: "#60a5fa"
        }}>
          📡 NEXRAD · {radarTime} · auto-refreshes every 5min
        </div>
      )}

      {/* ── Wind loading indicator ── */}
      {windLoading && (
        <div style={{
          position: "absolute", top: 10, right: 10, zIndex: 1000,
          background: "#07090dee", border: "1px solid #4ade8055",
          borderRadius: 4, padding: "3px 8px",
          fontSize: 9, fontFamily: "monospace", color: "#4ade80"
        }}>
          <span className="spin">↺</span> fetching wind obs…
        </div>
      )}

      {/* ── Wind refresh button ── */}
      {showWind && !windLoading && (
        <div style={{
          position: "absolute", top: 10, right: 10, zIndex: 1000,
        }}>
          <button onClick={fetchWindObs} style={{
            background: "#07090dee", border: "1px solid #4ade8055",
            borderRadius: 4, padding: "3px 8px",
            fontSize: 9, fontFamily: "monospace", color: "#4ade80",
            cursor: "pointer"
          }}>↺ refresh wind</button>
        </div>
      )}

      {!ready && (
        <div style={{
          position: "absolute", inset: 0, display: "flex",
          alignItems: "center", justifyContent: "center",
          background: "#0d1117", color: "#333", fontSize: 12, fontFamily: "monospace"
        }}>
          <span className="spin" style={{ marginRight: 8 }}>↺</span> Loading map…
        </div>
      )}
    </div>
  )
}
