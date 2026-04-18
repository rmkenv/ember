// ─── NYC Static Knowledge Base ───────────────────────────────────────────────
export const NYC_KB = {
  floodZones: {
    label: "Flood Zones (FEMA)",
    data: `Zone A: High-risk coastal/tidal flood areas — Lower Manhattan, Red Hook (Brooklyn), Rockaway Peninsula (Queens), Staten Island east shore. No base flood elevation determined.
Zone AE: Special Flood Hazard Areas with established base flood elevations. Covers Coney Island, Howard Beach, Broad Channel, southern Staten Island.
Zone X (shaded): Moderate flood risk, 0.2% annual chance. Much of Brooklyn and Queens inland.
Zone VE: Coastal high-hazard areas with wave action. Far Rockaway, Breezy Point, Sea Gate.
Post-Sandy (2012): ~88,000 buildings damaged; $19B in damage. NYC's flood maps substantially revised post-event.`,
    source: "FEMA NFHL / NYC OEM"
  },
  evacZones: {
    label: "Evacuation Zones",
    data: `Zone 1 (Highest Risk): Immediate coastal areas, barrier islands. Mandatory evacuation during Category 1+ hurricanes. Rockaways, Coney Island, South Beach SI, Red Hook waterfront.
Zone 2: Low-lying areas near coast/rivers. Evacuation advised Cat 2+.
Zone 3: Moderate flood risk. Cat 3+. Zones 4-6: Lower risk, inland.
Shelters: 30+ designated hurricane evacuation centers across all 5 boroughs. Primary shelter capacity ~600,000. Special Medical Needs Shelters at select hospitals.
Key routes: FDR Drive, BQE, Staten Island Expressway designated contraflow corridors during mass evacuations.`,
    source: "NYC OEM"
  },
  criticalInfrastructure: {
    label: "Critical Infrastructure",
    data: `Hospitals: 11 Level 1 Trauma Centers. Key: Bellevue (Manhattan), Kings County (Brooklyn), Lincoln (Bronx), Staten Island University, Jamaica (Queens).
Power: ConEd substations — critical nodes at East River facilities. Vulnerable underground feeders in Lower Manhattan (flooded during Sandy).
Subway: 245 miles of track, 472 stations. 52 stations in flood zones. MTA deployed flood barriers at high-risk entrances. South Ferry rebuilt with permanent flood protection post-Sandy.
Water: DEP operates 14 reservoirs, 2 city tunnels. Newtown Creek and North River WWTPs serve millions — both partially flooded in Sandy.
Communications: Notify NYC (push alerts), NYC Emergency Management radio (ICAD), Wireless Emergency Alerts (WEA). Backup EOC at Pier 92, Manhattan.
Airports: JFK (Zone A/AE), LaGuardia (Zone A — flooded in Sandy). Newark (NJ jurisdiction).`,
    source: "NYC OEM / CISA"
  },
  hazardProfiles: {
    label: "Hazard Profiles",
    data: `HURRICANES: Season June-Nov. Sandy (2012, Cat 1 at landfall) caused $19B damage. Primary risk: storm surge, not wind.
EXTREME HEAT: 115-150 deaths/year average. Heat Emergency Protocol activates at Heat Index >= 100F. 500+ cooling centers citywide. Vulnerable: elderly, NYCHA residents.
COASTAL/URBAN FLOODING: Flash floods increasingly common (Ida 2021 — 13 deaths in basement apartments). 22,000+ miles of combined sewer; overflows during heavy rain.
WINTER STORMS: Nor'easters primary threat. Jonas (2016) — 27 inches snowfall, travel ban. Blizzard protocol: Sanitation deploys 2,300 plows.
EARTHQUAKE: Low but non-zero risk. Historical: 1884 M5.5 earthquake felt strongly. Building stock largely unreinforced masonry pre-1930.
TERRORISM/HAZMAT: NYC highest-risk US city per DHS. JTTF, NYPD Intelligence, FDNY HazMat protocols established.
PANDEMICS: COVID-19 (2020): 3,000+ deaths first 30 days. NYC Health + Hospitals surge: 3,500+ beds activated.`,
    source: "NYC OEM Hazard Mitigation Plan 2023"
  },
  resources: {
    label: "Contacts & Resources",
    data: `NYC OEM: 718-422-8700 | nyc.gov/oem | EOC: 165 Cadman Plaza East, Brooklyn
FDNY: 911 (emergency) | 718-999-2000 (admin) | 250+ firehouses citywide
NYPD: 911 (emergency) | 646-610-5000 (admin)
NYC Health: 311 | nyc.gov/health
FEMA Region 2 (NY/NJ): 212-680-3600
NWS NY/NJ (OKX): weather.gov/okx | 631-924-0517
Con Edison (electric): 1-800-75-CONED
National Grid (gas): 1-800-930-5003
NYC 311: General city services, non-emergency
Notify NYC: nyc.gov/notifynyc — free emergency push alerts
CERT: nyc.gov/cert — Community Emergency Response Teams all 5 boroughs`,
    source: "NYC OEM / 311"
  }
}

// ─── Live API Endpoints ───────────────────────────────────────────────────────
export const LIVE_ENDPOINTS = [
  { name: "NWS Alerts — NY",     url: "https://api.weather.gov/alerts/active?area=NY",                                                                            type: "weather" },
  { name: "NWS Forecast — NYC",  url: "https://api.weather.gov/gridpoints/OKX/33,37/forecast",                                                                    type: "forecast"},
  { name: "USGS Stream Gauges",  url: "https://waterservices.usgs.gov/nwis/iv/?format=json&stateCd=ny&parameterCd=00065&siteStatus=active",                       type: "flood"   },
  { name: "FEMA Disasters — NY", url: "https://www.fema.gov/api/open/v2/disasterDeclarationsSummaries?state=NY&$top=10&$orderby=declarationDate%20desc",          type: "fema"    },
  { name: "NYC 311",             url: "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=5&$order=created_date%20DESC",                                type: "civic"   },
]

// ─── Map Layer Data ───────────────────────────────────────────────────────────
export const MAP_LAYERS = {
  hospitals: {
    label: "Trauma Centers",
    color: "#f87171",
    icon: "🏥",
    features: [
      { name: "Bellevue Hospital",              lat: 40.7394, lng: -73.9754, borough: "Manhattan",  note: "Level 1 Trauma | NYC Health + Hospitals" },
      { name: "NewYork-Presbyterian / Weill Cornell", lat: 40.7648, lng: -73.9543, borough: "Manhattan", note: "Level 1 Trauma" },
      { name: "Mount Sinai Hospital",           lat: 40.7900, lng: -73.9526, borough: "Manhattan",  note: "Level 1 Trauma" },
      { name: "Kings County Hospital",          lat: 40.6551, lng: -73.9444, borough: "Brooklyn",   note: "Level 1 Trauma | NYC Health + Hospitals" },
      { name: "Maimonides Medical Center",      lat: 40.6356, lng: -73.9985, borough: "Brooklyn",   note: "Level 1 Trauma" },
      { name: "Lincoln Medical Center",         lat: 40.8168, lng: -73.9249, borough: "Bronx",      note: "Level 1 Trauma | NYC Health + Hospitals" },
      { name: "Jacobi Medical Center",          lat: 40.8508, lng: -73.8454, borough: "Bronx",      note: "Level 1 Trauma | NYC Health + Hospitals" },
      { name: "Jamaica Hospital Medical Center",lat: 40.7003, lng: -73.7958, borough: "Queens",     note: "Level 1 Trauma" },
      { name: "Staten Island University Hosp.", lat: 40.5766, lng: -74.1159, borough: "Staten Island", note: "Level 1 Trauma" },
    ]
  },
  shelters: {
    label: "Evacuation Shelters",
    color: "#60a5fa",
    icon: "🏫",
    features: [
      { name: "Boys & Girls HS (Zone 1 Shelter)",        lat: 40.6797, lng: -73.9434, borough: "Brooklyn",    note: "Hurricane Evacuation Center — Zone 1" },
      { name: "Brandeis HS (Zone 1 Shelter)",            lat: 40.7960, lng: -73.9804, borough: "Manhattan",   note: "Hurricane Evacuation Center" },
      { name: "August Martin HS (Zone 1 Shelter)",       lat: 40.6719, lng: -73.7770, borough: "Queens",      note: "Hurricane Evacuation Center" },
      { name: "PS 14 (Zone 1 Shelter)",                  lat: 40.6285, lng: -74.0754, borough: "Staten Island",note: "Hurricane Evacuation Center — Zone 1" },
      { name: "Lehman HS (Zone 1 Shelter)",              lat: 40.8780, lng: -73.8985, borough: "Bronx",       note: "Hurricane Evacuation Center" },
      { name: "John Adams HS",                           lat: 40.6607, lng: -73.8555, borough: "Queens",      note: "Hurricane Evacuation Center" },
      { name: "Susan Wagner HS",                         lat: 40.6074, lng: -74.1193, borough: "Staten Island",note: "Hurricane Evacuation Center" },
    ]
  },
  gauges: {
    label: "USGS Stream Gauges",
    color: "#4ade80",
    icon: "📡",
    features: [
      { name: "Bronx River at Bronxville",    lat: 40.9382, lng: -73.8312, note: "USGS 01302500 — flood monitoring" },
      { name: "Newtown Creek at Maspeth",     lat: 40.7228, lng: -73.9167, note: "USGS tidal gauge — storm surge" },
      { name: "Hutchinson River at Pelham",   lat: 40.8914, lng: -73.8077, note: "USGS 01303500" },
      { name: "Jamaica Bay (Inwood)",         lat: 40.6226, lng: -73.7576, note: "NOAA tidal gauge — Zone A monitoring" },
      { name: "Battery Park Tidal Gauge",     lat: 40.7003, lng: -74.0141, note: "NOAA 8518750 — primary NYC surge gauge" },
      { name: "Kings Point Tidal Gauge",      lat: 40.8105, lng: -73.7659, note: "NOAA 8516945 — Long Island Sound" },
    ]
  },
  eoc: {
    label: "EOC / Command Posts",
    color: "#facc15",
    icon: "🏛",
    features: [
      { name: "NYC Emergency Operations Center",lat: 40.6967, lng: -73.9896, borough: "Brooklyn",   note: "Primary EOC — 165 Cadman Plaza East" },
      { name: "Pier 92 Backup EOC",             lat: 40.7671, lng: -74.0029, borough: "Manhattan",   note: "Backup EOC / Mass Casualty staging" },
      { name: "FDNY HQ",                        lat: 40.7127, lng: -74.0040, borough: "Manhattan",   note: "9 MetroTech Center, Brooklyn" },
      { name: "NYPD HQ (1PP)",                  lat: 40.7128, lng: -74.0060, borough: "Manhattan",   note: "1 Police Plaza" },
      { name: "FEMA Region 2 Office",           lat: 40.7143, lng: -74.0071, borough: "Manhattan",   note: "26 Federal Plaza — FEMA Region 2" },
    ]
  },
  floodRisk: {
    label: "High Flood Risk Areas",
    color: "#fb923c",
    icon: "💧",
    features: [
      { name: "Red Hook, Brooklyn",        lat: 40.6745, lng: -74.0097, note: "FEMA Zone AE — severely flooded in Sandy 2012" },
      { name: "Coney Island",              lat: 40.5755, lng: -73.9707, note: "FEMA Zone AE — 10ft+ surge in Sandy" },
      { name: "Howard Beach",              lat: 40.6570, lng: -73.8378, note: "FEMA Zone AE — interior flooding risk" },
      { name: "Broad Channel",             lat: 40.6138, lng: -73.8213, note: "FEMA Zone AE — island community" },
      { name: "Rockaway Peninsula",        lat: 40.5874, lng: -73.8261, note: "FEMA Zone VE/AE — barrier island, highest surge risk" },
      { name: "South Beach, Staten Island",lat: 40.5842, lng: -74.0783, note: "FEMA Zone AE — major Sandy impact zone" },
      { name: "Lower Manhattan (FiDi)",    lat: 40.7074, lng: -74.0104, note: "FEMA Zone AE — subway/utility vulnerability" },
      { name: "Breezy Point",              lat: 40.5587, lng: -73.9290, note: "FEMA Zone VE — barrier spit, wave action" },
    ]
  }
}

// ─── Summarize live API response for LLM context ──────────────────────────────
export function summarizeAPIData(r) {
  if (!r.success) return `[${r.name}: unavailable — ${r.error}]`
  const d = r.data
  try {
    if (r.type === "weather" && d.features) {
      const alerts = d.features.slice(0, 3).map(f => `${f.properties.event} — ${(f.properties.headline||"").substring(0,90)}`).join("; ")
      return `NWS Active Alerts (NY): ${d.features.length} total. ${alerts || "None active"}`
    }
    if (r.type === "forecast" && d.properties?.periods) {
      return "NWS Forecast NYC: " + d.properties.periods.slice(0,3).map(p=>`${p.name}: ${p.shortForecast}, ${p.temperature}°${p.temperatureUnit}`).join("; ")
    }
    if (r.type === "flood" && d.value?.timeSeries) {
      return "USGS NY Gauges: " + d.value.timeSeries.slice(0,4).map(g=>`${g.sourceInfo.siteName}: ${g.values?.[0]?.value?.[0]?.value??"N/A"} ft`).join("; ")
    }
    if (r.type === "fema" && d.DisasterDeclarationsSummaries) {
      return "FEMA NY Declarations: " + d.DisasterDeclarationsSummaries.slice(0,3).map(x=>`${x.incidentType} — ${x.declarationTitle} (${(x.declarationDate||"").substring(0,10)})`).join("; ")
    }
    if (r.type === "civic" && Array.isArray(d)) {
      return "NYC 311 Recent: " + d.slice(0,3).map(x=>`${x.complaint_type}: ${x.descriptor} (${x.borough})`).join("; ")
    }
    return `[${r.name}: received]`
  } catch { return `[${r.name}: parse error]` }
}

export function buildContext(files, apiResults, activeModules) {
  let ctx = "=== NYC EMERGENCY MANAGEMENT KNOWLEDGE BASE ===\n\n"
  for (const [key, mod] of Object.entries(NYC_KB)) {
    if (activeModules.includes(key)) ctx += `--- ${mod.label} [${mod.source}] ---\n${mod.data}\n\n`
  }
  if (apiResults.length) {
    ctx += "--- LIVE API DATA (fetched " + new Date().toUTCString() + ") ---\n"
    apiResults.forEach(r => { ctx += summarizeAPIData(r) + "\n" })
    ctx += "\n"
  }
  if (files.length) {
    ctx += "--- UPLOADED DOCUMENTS ---\n"
    files.forEach(f => { ctx += `[File: ${f.name}]\n${f.content.substring(0,4000)}\n\n` })
  }
  return ctx
}
