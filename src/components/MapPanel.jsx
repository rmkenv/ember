import { useEffect, useRef, useState } from "react"
import { MAP_LAYERS } from "../data/nyc.js"

// We use Leaflet directly (not react-leaflet) to avoid SSR issues and for
// finer control over the dark tile layer and custom markers.

const TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
const TILE_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'

const LAYER_ORDER = ["floodRisk", "gauges", "shelters", "hospitals", "eoc"]

function makeIcon(L, color, emoji) {
  return L.divIcon({
    className: "",
    html: `<div style="
      width:28px;height:28px;border-radius:50%;
      background:${color}22;border:2px solid ${color};
      display:flex;align-items:center;justify-content:center;
      font-size:13px;cursor:pointer;
      box-shadow:0 0 8px ${color}44;
      transition:transform 0.15s;
    ">${emoji}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -16]
  })
}

export default function MapPanel({ activeLayers, onMarkerClick }) {
  const mapRef    = useRef(null)
  const leafletRef= useRef(null)
  const layerRefs = useRef({})
  const [ready, setReady] = useState(false)

  // ── Init map ──
  useEffect(() => {
    if (leafletRef.current) return
    import("leaflet").then(({ default: L }) => {
      const map = L.map(mapRef.current, {
        center: [40.7128, -74.006],
        zoom: 11,
        zoomControl: true,
        attributionControl: true,
      })

      L.tileLayer(TILE_URL, { attribution: TILE_ATTR, maxZoom: 19, subdomains: "abcd" }).addTo(map)

      // Store layer groups
      for (const [key, layer] of Object.entries(MAP_LAYERS)) {
        const group = L.layerGroup()
        layer.features.forEach(f => {
          const marker = L.marker([f.lat, f.lng], { icon: makeIcon(L, layer.color, layer.icon) })
          marker.bindPopup(`
            <div>
              <div style="font-weight:700;color:${layer.color};margin-bottom:4px;font-size:12px">${layer.icon} ${f.name}</div>
              ${f.borough ? `<div style="color:#888;font-size:10px;margin-bottom:4px">${f.borough}</div>` : ""}
              <div style="font-size:11px;color:#aac">${f.note}</div>
            </div>
          `)
          marker.on("click", () => onMarkerClick && onMarkerClick({ ...f, layerLabel: layer.label, color: layer.color }))
          group.addLayer(marker)
        })
        layerRefs.current[key] = group
      }

      leafletRef.current = map
      setReady(true)
    })

    return () => {
      if (leafletRef.current) {
        leafletRef.current.remove()
        leafletRef.current = null
      }
    }
  }, [])

  // ── Toggle layers ──
  useEffect(() => {
    if (!ready || !leafletRef.current) return
    const map = leafletRef.current
    for (const [key, group] of Object.entries(layerRefs.current)) {
      if (activeLayers.includes(key)) {
        if (!map.hasLayer(group)) group.addTo(map)
      } else {
        if (map.hasLayer(group)) map.removeLayer(group)
      }
    }
  }, [activeLayers, ready])

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={mapRef} style={{ width: "100%", height: "100%" }} />
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
