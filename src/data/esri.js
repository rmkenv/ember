// ─── ArcGIS Online & Living Atlas Search ─────────────────────────────────────
// Uses the public ArcGIS Online sharing REST API — no API key required for
// public content. Living Atlas items are owned by esri_livingatlas / Esri.
// Docs: https://developers.arcgis.com/rest/users-groups-and-items/search/

export const AGOL_BASE = "https://www.arcgis.com/sharing/rest"

// Item type categories meaningful to emergency managers
export const ESRI_ITEM_TYPES = {
  "Feature Layer":    "Feature Layer",
  "Map Service":      "Map Service",
  "Image Service":    "Image Service",
  "Vector Tile Layer":"Vector Tile Layer",
  "Web Map":          "Web Map",
  "Web Scene":        "Web Scene",
  "Feature Collection":"Feature Collection",
  "StoryMap":         "StoryMap",
  "Dashboard":        "Dashboard",
}

// Curated emergency-relevant Living Atlas tags / keywords
export const LIVING_ATLAS_FILTERS = [
  { label: "All Public", value: "" },
  { label: "Living Atlas Only", value: "owner:esri_livingatlas" },
  { label: "Flood / Hydrology",  value: "tags:flood OR tags:hydrology OR tags:inundation" },
  { label: "Hurricanes",         value: "tags:hurricane OR tags:storm surge OR tags:cyclone" },
  { label: "Wildfire",           value: "tags:wildfire OR tags:fire perimeter" },
  { label: "Emergency Mgmt",     value: "tags:emergency management OR tags:disaster response" },
  { label: "Critical Infra",     value: "tags:critical infrastructure OR tags:hospitals" },
  { label: "Climate / Weather",  value: "tags:climate OR tags:weather OR tags:NWS" },
  { label: "NYC / New York",     value: "tags:New York City OR tags:NYC" },
  { label: "FEMA",               value: "tags:FEMA OR owner:FEMA" },
]

/**
 * Search ArcGIS Online / Living Atlas public catalog
 * @param {string}  query      - free-text search
 * @param {string}  filterExpr - additional owner/tag filter (ANDed with query)
 * @param {string}  itemType   - item type filter (e.g. "Feature Layer")
 * @param {number}  num        - results per page (max 100)
 * @param {number}  start      - pagination offset (1-based)
 * @returns {Promise<{results: Array, total: number, error?: string}>}
 */
export async function searchAGOL({ query = "", filterExpr = "", itemType = "", num = 12, start = 1 } = {}) {
  // Build composite query string
  let q = query.trim() || "*"

  // Scope to Living Atlas + public content
  const scopeParts = ["access:public"]
  if (filterExpr) scopeParts.push(`(${filterExpr})`)
  if (itemType)   scopeParts.push(`type:"${itemType}"`)

  const fullQuery = `${q} ${scopeParts.join(" AND ")}`

  const params = new URLSearchParams({
    f:          "json",
    q:          fullQuery,
    num:        String(num),
    start:      String(start),
    sortField:  "relevance",
    sortOrder:  "desc",
  })

  try {
    const res = await fetch(`${AGOL_BASE}/search?${params}`, {
      signal: AbortSignal.timeout(10000),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) throw new Error(data.error.message)
    return { results: data.results || [], total: data.total || 0 }
  } catch (e) {
    return { results: [], total: 0, error: e.message }
  }
}

/**
 * Fetch full item metadata from ArcGIS Online by item ID
 * @param {string} itemId
 */
export async function fetchItemMetadata(itemId) {
  try {
    const [itemRes, dataRes] = await Promise.all([
      fetch(`${AGOL_BASE}/content/items/${itemId}?f=json`, { signal: AbortSignal.timeout(8000) }),
      fetch(`${AGOL_BASE}/content/items/${itemId}/data?f=json`, { signal: AbortSignal.timeout(8000) })
        .catch(() => null),
    ])
    if (!itemRes.ok) throw new Error(`Item fetch HTTP ${itemRes.status}`)
    const item = await itemRes.json()
    let data = null
    if (dataRes?.ok) {
      try { data = await dataRes.json() } catch { /* not JSON */ }
    }
    return { item, data, error: null }
  } catch (e) {
    return { item: null, data: null, error: e.message }
  }
}

/**
 * Format item metadata into a concise text block for LLM context injection
 */
export function formatItemForContext(item, data) {
  if (!item) return ""
  const tags   = (item.tags  || []).join(", ")
  const extent = item.extent ? `[${item.extent.flat().join(", ")}]` : "N/A"
  const url    = item.url    || `https://www.arcgis.com/home/item.html?id=${item.id}`

  let block = `
[ESRI/Living Atlas Item: ${item.title}]
  Item ID:      ${item.id}
  Type:         ${item.type}
  Owner:        ${item.owner}
  Description:  ${(item.description || "").replace(/<[^>]+>/g, "").substring(0, 600)}
  Tags:         ${tags}
  Snippet:      ${item.snippet || ""}
  Extent:       ${extent}
  Spatial Ref:  ${item.spatialReference?.wkid || "unknown"}
  Access:       ${item.access}
  Updated:      ${item.modified ? new Date(item.modified).toISOString().substring(0, 10) : "unknown"}
  Service URL:  ${url}
  Views:        ${item.numViews || 0}
`.trim()

  if (data && typeof data === "object") {
    // If it's a FeatureService / MapService — pull layer names
    if (data.layers) {
      const layerNames = data.layers.map(l => `${l.id}: ${l.name}`).join(", ")
      block += `\n  Layers: ${layerNames}`
    }
    // If it's a webmap — pull operational layer titles
    if (data.operationalLayers) {
      const opLayers = data.operationalLayers.map(l => l.title || l.id).join(", ")
      block += `\n  Operational Layers: ${opLayers}`
    }
  }

  return block
}

/**
 * Summarize a list of AGOL search results into a compact text block for LLM context
 */
export function summarizeSearchResults(results, query) {
  if (!results.length) return `[ESRI Search for "${query}": no results]`
  const items = results.slice(0, 8).map(r =>
    `  - ${r.title} (${r.type}, owner:${r.owner}, id:${r.id}) — ${r.snippet || ""}`
  ).join("\n")
  return `[ESRI/Living Atlas Search: "${query}" — ${results.length} results]\n${items}`
}
