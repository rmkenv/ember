// ─── NOAA Open Data Stack ─────────────────────────────────────────────────────
// All endpoints below are free and require NO API key.
// Sources:
//   NWS:       https://www.weather.gov/documentation/services-web-api
//   CO-OPS:    https://api.tidesandcurrents.noaa.gov/api/prod/
//   NCEI Data: https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation
//   NCEI Search: https://www.ncei.noaa.gov/support/access-search-service-api-user-documentation
//   NCEI Support: https://www.ncei.noaa.gov/access/services/support/v3/datasets/
//   SPC:       https://www.spc.noaa.gov/
//   Space Wx:  https://services.swpc.noaa.gov/

// ── NYC-specific station IDs ──────────────────────────────────────────────────
export const NYC_STATIONS = {
  nws: {
    office:     "OKX",   // NWS Forecast Office — NYC
    gridX:      33,
    gridY:      37,
    zone:       "NYZ178", // NYC metro zone
    county:     "NYC",
    obs_station:"KNYC",  // Central Park observation station
  },
  coops: {
    battery:    "8518750", // The Battery, Manhattan — primary NYC surge gauge
    kings_point:"8516945", // Kings Point, Long Island Sound
    sandy_hook: "8531680", // Sandy Hook, NJ — regional surge reference
    montauk:    "8510560", // Montauk — outer harbor
  },
  ncei: {
    central_park: "GHCND:USW00094728", // Central Park daily summaries
    jfk:          "GHCND:USW00094789", // JFK Airport
    laguardia:    "GHCND:USW00014732", // LaGuardia Airport
  }
}

// ── NOAA API category definitions ─────────────────────────────────────────────
export const NOAA_CATEGORIES = {
  nws: {
    label: "NWS Weather API",
    color: "#60a5fa",
    icon:  "🌩",
    description: "National Weather Service — alerts, forecasts, observations, radar. No key required.",
    endpoints: [
      {
        id: "nws_alerts_ny",
        name: "Active Alerts — New York",
        url: "https://api.weather.gov/alerts/active?area=NY",
        desc: "All active NWS weather alerts for New York State",
        tags: ["alerts","severe weather","tornado","flood","winter storm"],
      },
      {
        id: "nws_alerts_urgent",
        name: "Urgent Alerts (Extreme/Severe)",
        url: "https://api.weather.gov/alerts/active?area=NY&severity=Extreme,Severe&status=Actual",
        desc: "Only extreme and severe active alerts — highest priority",
        tags: ["alerts","extreme","severe"],
      },
      {
        id: "nws_forecast_nyc",
        name: "7-Day Forecast — NYC",
        url: "https://api.weather.gov/gridpoints/OKX/33,37/forecast",
        desc: "NWS OKX 7-day text forecast for NYC metro",
        tags: ["forecast","weather","temperature","precipitation"],
      },
      {
        id: "nws_forecast_hourly",
        name: "Hourly Forecast — NYC",
        url: "https://api.weather.gov/gridpoints/OKX/33,37/forecast/hourly",
        desc: "Hour-by-hour NWS forecast for NYC — temperature, wind, precipitation probability",
        tags: ["forecast","hourly","wind","temperature"],
      },
      {
        id: "nws_obs_central_park",
        name: "Current Observations — Central Park (KNYC)",
        url: "https://api.weather.gov/stations/KNYC/observations/latest",
        desc: "Latest surface observation from NYC Central Park station",
        tags: ["observations","current","temperature","wind","humidity"],
      },
      {
        id: "nws_obs_jfk",
        name: "Current Observations — JFK Airport (KJFK)",
        url: "https://api.weather.gov/stations/KJFK/observations/latest",
        desc: "Latest surface observation from JFK Airport — key for coastal/surge events",
        tags: ["observations","airport","wind","visibility"],
      },
      {
        id: "nws_obs_ewr",
        name: "Current Observations — Newark (KEWR)",
        url: "https://api.weather.gov/stations/KEWR/observations/latest",
        desc: "Latest surface observation from Newark Airport — NJ comparison",
        tags: ["observations","newark","wind"],
      },
      {
        id: "nws_radar_stations",
        name: "Radar Stations — NY Region",
        url: "https://api.weather.gov/radar/stations?stationType=WSR-88D&state=NY",
        desc: "NEXRAD WSR-88D radar stations covering New York",
        tags: ["radar","nexrad"],
      },
      {
        id: "nws_office_okx",
        name: "NWS Office Info — OKX (Upton, NY)",
        url: "https://api.weather.gov/offices/OKX",
        desc: "NWS forecast office responsible for NYC metro area",
        tags: ["office","metadata"],
      },
      {
        id: "nws_zone_nyc",
        name: "NYC Public Forecast Zone",
        url: "https://api.weather.gov/zones/public/NYZ178",
        desc: "Public forecast zone boundaries and metadata for NYC metro",
        tags: ["zones","forecast area"],
      },
      {
        id: "nws_products_okx",
        name: "Text Products — NWS OKX",
        url: "https://api.weather.gov/products?office=OKX&limit=10",
        desc: "Latest NWS text products issued by OKX (Area Forecast Discussion, Coastal Hazards, etc.)",
        tags: ["products","text","AFD","forecast discussion"],
      },
    ]
  },

  coops: {
    label: "CO-OPS Tides & Currents",
    color: "#34d399",
    icon:  "🌊",
    description: "NOAA Center for Operational Oceanographic Products — real-time water levels, tidal predictions, currents. No key required.",
    endpoints: [
      {
        id: "coops_water_battery",
        name: "Water Level — The Battery (NYC)",
        url: "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8518750&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER",
        desc: "Real-time water level at The Battery, Manhattan — primary NYC storm surge gauge (MLLW datum, feet)",
        tags: ["water level","storm surge","tidal","battery","manhattan"],
      },
      {
        id: "coops_predictions_battery",
        name: "Tidal Predictions — The Battery",
        url: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?begin_date=${new Date().toISOString().slice(0,10).replace(/-/g,"")}&end_date=${new Date(Date.now()+2*86400000).toISOString().slice(0,10).replace(/-/g,"")}&station=8518750&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json&application=EMBER`,
        desc: "High/low tide predictions for The Battery — next 48 hours",
        tags: ["tidal predictions","high tide","low tide"],
      },
      {
        id: "coops_water_kings_point",
        name: "Water Level — Kings Point (Long Island Sound)",
        url: "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8516945&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER",
        desc: "Real-time water level at Kings Point — Long Island Sound surge monitoring",
        tags: ["water level","kings point","long island sound"],
      },
      {
        id: "coops_water_sandy_hook",
        name: "Water Level — Sandy Hook, NJ",
        url: "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8531680&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER",
        desc: "Real-time water level at Sandy Hook — outer harbor reference station",
        tags: ["water level","sandy hook","outer harbor"],
      },
      {
        id: "coops_met_battery",
        name: "Meteorological — The Battery (Wind/Pressure/Air Temp)",
        url: "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8518750&product=wind&time_zone=lst_ldt&units=english&format=json&application=EMBER",
        desc: "Real-time wind speed, direction, and gusts at The Battery station",
        tags: ["wind","meteorological","battery"],
      },
      {
        id: "coops_station_battery_meta",
        name: "Station Metadata — The Battery",
        url: "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/8518750.json?expand=details,sensors,products,disclaimers",
        desc: "Full metadata for The Battery station — sensors, products, operational status, datum offsets",
        tags: ["metadata","station info","sensors","datums"],
      },
      {
        id: "coops_stations_ny",
        name: "All CO-OPS Stations — NY Region",
        url: "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels&state=NY",
        desc: "All active water level stations in New York state",
        tags: ["stations","inventory","new york"],
      },
    ]
  },

  ncei: {
    label: "NCEI Climate Data",
    color: "#f59e0b",
    icon:  "📊",
    description: "NOAA National Centers for Environmental Information — historical climate, station data, dataset catalog. No key required on new endpoints.",
    endpoints: [
      {
        id: "ncei_datasets",
        name: "NCEI Dataset Catalog",
        url: "https://www.ncei.noaa.gov/access/services/support/v3/datasets.json",
        desc: "Full catalog of all NCEI datasets — daily summaries, hourly, monthly, radar, marine, etc.",
        tags: ["catalog","datasets","metadata"],
      },
      {
        id: "ncei_daily_nyc",
        name: "Daily Climate Summaries — Central Park (recent 7 days)",
        url: `https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094728&dataTypes=TMAX,TMIN,PRCP,SNOW,SNWD,AWND&startDate=${new Date(Date.now()-7*86400000).toISOString().slice(0,10)}&endDate=${new Date().toISOString().slice(0,10)}&format=json&units=standard`,
        desc: "Last 7 days of daily weather summaries from Central Park — temp, precip, snow, wind",
        tags: ["daily summaries","temperature","precipitation","snow","central park"],
      },
      {
        id: "ncei_daily_jfk",
        name: "Daily Climate Summaries — JFK Airport (recent 7 days)",
        url: `https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094789&dataTypes=TMAX,TMIN,PRCP,SNOW,AWND&startDate=${new Date(Date.now()-7*86400000).toISOString().slice(0,10)}&endDate=${new Date().toISOString().slice(0,10)}&format=json&units=standard`,
        desc: "Last 7 days of daily weather summaries from JFK Airport — coastal weather indicator",
        tags: ["daily summaries","jfk","temperature","precipitation"],
      },
      {
        id: "ncei_normals_nyc",
        name: "Climate Normals — NYC (1991–2020)",
        url: "https://www.ncei.noaa.gov/access/services/data/v1?dataset=normals-daily&stations=USW00094728&startDate=2010-01-01&endDate=2010-12-31&dataTypes=DLY-TMAX-NORMAL,DLY-TMIN-NORMAL,DLY-PRCP-PCTALL-GE001HI&format=json",
        desc: "1991–2020 climate normals for NYC Central Park — baseline for anomaly detection",
        tags: ["climate normals","baseline","temperature","precipitation"],
      },
      {
        id: "ncei_search_storms",
        name: "Storm Events — NY (recent)",
        url: `https://www.ncei.noaa.gov/access/services/search/v1/data?dataset=local-climatological-data&bbox=40.5,-74.3,41.0,-73.7&startDate=${new Date(Date.now()-30*86400000).toISOString().slice(0,10)}&endDate=${new Date().toISOString().slice(0,10)}&limit=10&format=json`,
        desc: "Local climatological data for NYC bounding box — last 30 days",
        tags: ["storm events","local climate","recent"],
      },
      {
        id: "ncei_dataset_daily_meta",
        name: "Dataset Metadata — Daily Summaries",
        url: "https://www.ncei.noaa.gov/access/services/support/v3/datasets/daily-summaries.json",
        desc: "Full metadata and attribute list for the NCEI daily-summaries dataset",
        tags: ["metadata","daily summaries","attributes"],
      },
      {
        id: "ncei_dataset_storm_meta",
        name: "Dataset Metadata — Storm Events",
        url: "https://www.ncei.noaa.gov/access/services/support/v3/datasets/storm-events.json",
        desc: "Full metadata for NCEI storm events database — tornadoes, floods, hurricanes since 1950",
        tags: ["metadata","storm events","tornadoes","floods"],
      },
    ]
  },

  spc: {
    label: "Storm Prediction Center",
    color: "#f87171",
    icon:  "⚡",
    description: "NOAA Storm Prediction Center — convective outlooks, tornado/severe thunderstorm watches. No key required.",
    endpoints: [
      {
        id: "spc_active_watches",
        name: "Active Watches — Tornado / Severe Thunderstorm",
        url: "https://www.spc.noaa.gov/products/watch/ActiveWW.txt",
        desc: "Currently active SPC tornado and severe thunderstorm watches — plain text",
        tags: ["watches","tornado","severe thunderstorm","active"],
        format: "text",
      },
      {
        id: "spc_day1_outlook",
        name: "Day 1 Convective Outlook",
        url: "https://www.spc.noaa.gov/products/outlook/day1otlk.txt",
        desc: "SPC Day 1 convective outlook — categorical severe weather risk",
        tags: ["convective outlook","severe weather","day 1"],
        format: "text",
      },
      {
        id: "spc_mcd",
        name: "Mesoscale Discussions (active)",
        url: "https://www.spc.noaa.gov/products/md/mdurl.txt",
        desc: "Active SPC mesoscale discussions — precursor to watch issuance",
        tags: ["mesoscale discussion","MCD","convective","near-term"],
        format: "text",
      },
    ]
  },

  space_wx: {
    label: "Space Weather",
    color: "#a78bfa",
    icon:  "☀️",
    description: "NOAA Space Weather Prediction Center — geomagnetic storms, solar flares, GPS/radio disruption. No key required.",
    endpoints: [
      {
        id: "swpc_alerts",
        name: "Space Weather Alerts",
        url: "https://services.swpc.noaa.gov/products/alerts.json",
        desc: "Current space weather alerts, watches, and warnings — geomagnetic storms, radiation events",
        tags: ["space weather","geomagnetic storm","solar flare","GPS disruption"],
      },
      {
        id: "swpc_geomagnetic_forecast",
        name: "3-Day Geomagnetic Forecast",
        url: "https://services.swpc.noaa.gov/text/3-day-geomag-forecast.txt",
        desc: "SWPC 3-day geomagnetic activity forecast — Kp index, Ap values",
        tags: ["geomagnetic","Kp index","3-day forecast"],
        format: "text",
      },
      {
        id: "swpc_solar_wind",
        name: "Real-Time Solar Wind (DSCOVR)",
        url: "https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json",
        desc: "Real-time solar wind plasma data from DSCOVR satellite — density, speed, temperature",
        tags: ["solar wind","DSCOVR","real-time","plasma"],
      },
      {
        id: "swpc_kp_index",
        name: "Planetary K-Index (past 7 days)",
        url: "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
        desc: "1-minute Kp index values — geomagnetic disturbance level indicator",
        tags: ["Kp index","geomagnetic","1-minute"],
      },
    ]
  }
}

// ── Fetch a single NOAA endpoint ──────────────────────────────────────────────
export async function fetchNOAAEndpoint(endpoint) {
  try {
    const res = await fetch(endpoint.url, {
      signal: AbortSignal.timeout(10000),
      headers: { "User-Agent": "EMBER-EmergencyManagement/1.0" },
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)

    const isText = endpoint.format === "text" ||
      res.headers.get("content-type")?.includes("text/plain")

    const data = isText ? await res.text() : await res.json()
    return { success: true, data, isText, endpoint }
  } catch (e) {
    return { success: false, error: e.message, endpoint }
  }
}

// ── Summarize a NOAA fetch result for LLM context ────────────────────────────
export function summarizeNOAAResult(result) {
  if (!result.success) {
    return `[NOAA ${result.endpoint.name}: fetch failed — ${result.error}]`
  }
  const { data, isText, endpoint } = result

  try {
    if (isText) {
      return `[NOAA ${endpoint.name}]\n${String(data).substring(0, 800)}`
    }

    // NWS alerts
    if (endpoint.id.includes("alert") && data.features) {
      const alerts = data.features.slice(0, 5).map(f => {
        const p = f.properties
        return `  - ${p.event} (${p.severity}/${p.urgency}): ${(p.headline||"").substring(0,100)}`
      }).join("\n")
      return `[NOAA NWS Alerts: ${data.features.length} active]\n${alerts || "  None active"}`
    }

    // NWS forecast
    if (endpoint.id.includes("forecast") && data.properties?.periods) {
      const periods = data.properties.periods.slice(0, 6).map(p =>
        `  ${p.name}: ${p.shortForecast}, ${p.temperature}°${p.temperatureUnit}, wind ${p.windSpeed} ${p.windDirection}, precip ${p.probabilityOfPrecipitation?.value ?? "?"}%`
      ).join("\n")
      return `[NOAA NWS Forecast — ${endpoint.name}]\n${periods}`
    }

    // NWS observation
    if (endpoint.id.includes("obs") && data.properties) {
      const p = data.properties
      const tempF = p.temperature?.value ? (p.temperature.value * 9/5 + 32).toFixed(1) : "N/A"
      const windMph = p.windSpeed?.value ? (p.windSpeed.value * 0.621371).toFixed(1) : "N/A"
      const gustMph = p.windGust?.value  ? (p.windGust.value  * 0.621371).toFixed(1) : "N/A"
      return `[NOAA NWS Obs — ${endpoint.name}]
  Time: ${p.timestamp ? new Date(p.timestamp).toLocaleString() : "?"}
  Temp: ${tempF}°F | Humidity: ${p.relativeHumidity?.value?.toFixed(0) ?? "?"}%
  Wind: ${windMph} mph ${p.windDirection?.value ? p.windDirection.value + "°" : ""} (gusts: ${gustMph} mph)
  Visibility: ${p.visibility?.value ? (p.visibility.value/1609.34).toFixed(1)+" mi" : "?"}
  Conditions: ${p.textDescription || "?"}`
    }

    // CO-OPS water level
    if (endpoint.id.includes("water") && data.data) {
      const latest = data.data[data.data.length - 1]
      const meta = data.metadata
      return `[NOAA CO-OPS Water Level — ${meta?.name || endpoint.name}]
  Station: ${meta?.id || "?"} — ${meta?.name || "?"}
  Latest: ${latest?.v || "?"} ft MLLW @ ${latest?.t || "?"}
  Previous readings: ${data.data.slice(-5).map(d => `${d.v}ft@${d.t.slice(11,16)}`).join(", ")}`
    }

    // CO-OPS tidal predictions
    if (endpoint.id.includes("predictions") && data.predictions) {
      const preds = data.predictions.slice(0, 8).map(p =>
        `  ${p.type === "H" ? "HIGH" : "low "} ${p.v}ft @ ${p.t}`
      ).join("\n")
      return `[NOAA CO-OPS Tidal Predictions — Battery NYC]\n${preds}`
    }

    // CO-OPS wind/met
    if (endpoint.id.includes("met") && data.data) {
      const latest = data.data[data.data.length - 1]
      return `[NOAA CO-OPS Wind — ${endpoint.name}]
  Speed: ${latest?.s || "?"} knots | Direction: ${latest?.dr || "?"}
  Gusts: ${latest?.g || "?"} knots | Time: ${latest?.t || "?"}`
    }

    // CO-OPS station inventory
    if (endpoint.id.includes("stations") && data.stations) {
      return `[NOAA CO-OPS Stations — NY: ${data.stations.length} stations]\n` +
        data.stations.slice(0, 8).map(s => `  ${s.id}: ${s.name} (${s.state})`).join("\n")
    }

    // NCEI daily summaries
    if (endpoint.id.includes("daily") && Array.isArray(data)) {
      return `[NOAA NCEI Daily Summaries — ${endpoint.name}]\n` +
        data.slice(0, 5).map(r =>
          `  ${r.DATE}: TMAX=${r.TMAX ?? "?"}°F TMIN=${r.TMIN ?? "?"}°F PRCP=${r.PRCP ?? "?"}in SNOW=${r.SNOW ?? "?"}in WIND=${r.AWND ?? "?"}mph`
        ).join("\n")
    }

    // NCEI dataset catalog
    if (endpoint.id.includes("datasets") && data.datasets) {
      return `[NOAA NCEI Dataset Catalog: ${data.datasets.length} datasets]\n` +
        data.datasets.slice(0, 10).map(d => `  ${d.id}: ${d.name}`).join("\n")
    }

    // SWPC alerts
    if (endpoint.id.includes("swpc_alerts") && Array.isArray(data)) {
      return `[NOAA Space Weather Alerts: ${data.length}]\n` +
        data.slice(0, 5).map(a => `  ${a.message?.substring(0, 120) || JSON.stringify(a).substring(0, 100)}`).join("\n")
    }

    // SWPC solar wind
    if (endpoint.id.includes("solar_wind") && Array.isArray(data)) {
      const latest = data[data.length - 1]
      return `[NOAA DSCOVR Solar Wind — latest]
  Density: ${latest?.[1] ?? "?"} p/cm³ | Speed: ${latest?.[2] ?? "?"} km/s | Temp: ${latest?.[3] ?? "?"} K`
    }

    // Generic JSON fallback
    const str = JSON.stringify(data)
    return `[NOAA ${endpoint.name}]: ${str.substring(0, 400)}`
  } catch (e) {
    return `[NOAA ${endpoint.name}: parse error — ${e.message}]`
  }
}

// ── Format a result for display card ─────────────────────────────────────────
export function formatResultPreview(result) {
  if (!result.success) return { status: "error", preview: `Error: ${result.error}` }
  const sum = summarizeNOAAResult(result)
  return { status: "ok", preview: sum }
}

// ── All endpoint IDs flat list ─────────────────────────────────────────────────
export function getAllEndpoints() {
  return Object.values(NOAA_CATEGORIES).flatMap(cat =>
    cat.endpoints.map(ep => ({ ...ep, category: cat.label, color: cat.color, icon: cat.icon }))
  )
}
