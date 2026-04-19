"""
EMBER — Emergency Management Body of Evidence & Resources
Streamlit version · Ollama Cloud · NYC jurisdiction

Run:
    pip install -r requirements.txt
    export OLLAMA_API_KEY=your_key_here
    streamlit run streamlit/app.py
"""

# ── Imports (all at module level) ─────────────────────────────────────────────
import json, os, re, time as _time, datetime as _dt
from io import StringIO
import folium, requests, streamlit as st
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
from tidal_gauges import (
    fetch_all_ny_gauges, fetch_station_list,
    build_gauge_popup, gauge_marker_color,
    FLOOD_THRESHOLDS,
)

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_API_KEY = st.secrets.get("OLLAMA_API_KEY", os.environ.get("OLLAMA_API_KEY", ""))
OLLAMA_HOST    = st.secrets.get("OLLAMA_HOST",    os.environ.get("OLLAMA_HOST",    "https://ollama.com"))
OLLAMA_MODEL   = st.secrets.get("OLLAMA_MODEL",   os.environ.get("OLLAMA_MODEL",   "gpt-oss:120b-cloud"))
AGOL_BASE      = "https://www.arcgis.com/sharing/rest"
OLLAMA_HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {OLLAMA_API_KEY}"}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EMBER — NYC Emergency Management",
    page_icon="🚨", layout="wide", initial_sidebar_state="expanded"
)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Mono', monospace !important; }
.stApp { background: #07090d; color: #e0e0e8; }
section[data-testid="stSidebar"] { background: #090c12 !important; border-right: 1px solid #111820; }
.pill  { display:inline-block; padding:2px 8px; border-radius:12px; font-size:10px;
         font-weight:700; letter-spacing:0.05em; margin:2px; }
.p-green  { background:#4ade8020; color:#4ade80; border:1px solid #4ade8044; }
.p-red    { background:#f8717120; color:#f87171; border:1px solid #f8717144; }
.p-blue   { background:#60a5fa20; color:#60a5fa; border:1px solid #60a5fa44; }
.p-purple { background:#a78bfa20; color:#a78bfa; border:1px solid #a78bfa44; }
.p-yellow { background:#facc1520; color:#facc15; border:1px solid #facc1544; }
.esri-card { background:#0d1117; border:1px solid #1a1e2e; border-radius:6px;
             padding:10px 12px; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

NYC_KB = {
    "floodZones": {"label": "Flood Zones (FEMA)", "source": "FEMA NFHL / NYC OEM", "data":
        "Zone A: High-risk coastal/tidal flood areas — Lower Manhattan, Red Hook, Rockaway Peninsula, Staten Island east shore.\n"
        "Zone AE: Special Flood Hazard Areas — Coney Island, Howard Beach, Broad Channel, southern Staten Island.\n"
        "Zone VE: Coastal high-hazard with wave action — Far Rockaway, Breezy Point, Sea Gate.\n"
        "Zone X (shaded): Moderate flood risk, 0.2% annual chance.\n"
        "Post-Sandy (2012): ~88,000 buildings damaged; $19B in damage."},
    "evacZones": {"label": "Evacuation Zones", "source": "NYC OEM", "data":
        "Zone 1: Mandatory evacuation Cat 1+ hurricanes. Rockaways, Coney Island, South Beach SI, Red Hook waterfront.\n"
        "Zone 2: Evacuation advised Cat 2+. Zones 3-6: progressively lower risk inland.\n"
        "Shelters: 30+ hurricane evacuation centers, ~600,000 primary capacity.\n"
        "Contraflow: FDR Drive, BQE, Staten Island Expressway."},
    "criticalInfrastructure": {"label": "Critical Infrastructure", "source": "NYC OEM / CISA", "data":
        "Hospitals: 11 Level 1 Trauma Centers — Bellevue (Manhattan), Kings County (Brooklyn), Lincoln (Bronx), Staten Island University, Jamaica (Queens).\n"
        "Power: ConEd East River substations critical. Underground feeders in Lower Manhattan flooded during Sandy.\n"
        "Subway: 245 miles track, 472 stations. 52 stations in flood zones.\n"
        "Water: DEP 14 reservoirs, 2 city tunnels. Newtown Creek & North River WWTPs flooded in Sandy."},
    "hazardProfiles": {"label": "Hazard Profiles", "source": "NYC OEM HMP 2023", "data":
        "HURRICANES: Sandy (2012, Cat 1) — $19B damage. Primary risk: storm surge.\n"
        "EXTREME HEAT: 115-150 deaths/year. Protocol at Heat Index >= 100F. 500+ cooling centers.\n"
        "FLOODING: Ida 2021 — 13 deaths in basement apartments. 22,000+ miles combined sewer.\n"
        "WINTER STORMS: Jonas 2016 — 27 inches, travel ban. 2,300 Sanitation plows.\n"
        "EARTHQUAKE: Low risk. Historical 1884 M5.5. Unreinforced masonry stock pre-1930.\n"
        "TERRORISM/HAZMAT: Highest-risk US city (DHS). JTTF, NYPD Intelligence, FDNY HazMat."},
    "resources": {"label": "Contacts & Resources", "source": "NYC OEM / 311", "data":
        "NYC OEM: 718-422-8700 | nyc.gov/oem | EOC: 165 Cadman Plaza East, Brooklyn\n"
        "FDNY: 911 | 718-999-2000 | NYPD: 911 | 646-610-5000\n"
        "NYC Health: 311 | FEMA Region 2: 212-680-3600\n"
        "NWS OKX: 631-924-0517 | Con Edison: 1-800-75-CONED\n"
        "Notify NYC: nyc.gov/notifynyc"},
}

LIVE_ENDPOINTS = [
    {"name": "NWS Alerts — NY",    "url": "https://api.weather.gov/alerts/active?area=NY",                                                                          "type": "weather"},
    {"name": "NWS Forecast — NYC", "url": "https://api.weather.gov/gridpoints/OKX/33,37/forecast",                                                                   "type": "forecast"},
    {"name": "USGS Stream Gauges", "url": "https://waterservices.usgs.gov/nwis/iv/?format=json&stateCd=ny&parameterCd=00065&siteStatus=active",                      "type": "flood"},
    {"name": "FEMA Disasters",     "url": "https://www.fema.gov/api/open/v2/disasterDeclarationsSummaries?state=NY&$top=10&$orderby=declarationDate%20desc",         "type": "fema"},
    {"name": "NYC 311",            "url": "https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=5&$order=created_date%20DESC",                               "type": "civic"},
]

MAP_POINTS = {
    "hospitals": {"label": "Trauma Centers", "color": "#f87171", "features": [
        {"name": "Bellevue Hospital",         "lat": 40.7394, "lng": -73.9754, "note": "Level 1 Trauma | Manhattan"},
        {"name": "Kings County Hospital",     "lat": 40.6551, "lng": -73.9444, "note": "Level 1 Trauma | Brooklyn"},
        {"name": "Lincoln Medical Center",    "lat": 40.8168, "lng": -73.9249, "note": "Level 1 Trauma | Bronx"},
        {"name": "Jamaica Hospital",          "lat": 40.7003, "lng": -73.7958, "note": "Level 1 Trauma | Queens"},
        {"name": "Staten Island University",  "lat": 40.5766, "lng": -74.1159, "note": "Level 1 Trauma | Staten Island"},
        {"name": "Maimonides Medical Center", "lat": 40.6356, "lng": -73.9985, "note": "Level 1 Trauma | Brooklyn"},
    ]},
    "shelters": {"label": "Evac Shelters", "color": "#60a5fa", "features": [
        {"name": "Boys & Girls HS",     "lat": 40.6797, "lng": -73.9434, "note": "Evac Center | Brooklyn"},
        {"name": "Brandeis HS",         "lat": 40.7960, "lng": -73.9804, "note": "Evac Center | Manhattan"},
        {"name": "August Martin HS",    "lat": 40.6719, "lng": -73.7770, "note": "Evac Center | Queens"},
        {"name": "PS 14 Staten Island", "lat": 40.6285, "lng": -74.0754, "note": "Evac Center | Zone 1"},
        {"name": "Lehman HS",           "lat": 40.8780, "lng": -73.8985, "note": "Evac Center | Bronx"},
    ]},
    "gauges": {"label": "Stream Gauges", "color": "#4ade80", "features": [
        {"name": "Battery Park Tidal Gauge", "lat": 40.7003, "lng": -74.0141, "note": "NOAA 8518750 — primary NYC surge gauge"},
        {"name": "Kings Point Tidal Gauge",  "lat": 40.8105, "lng": -73.7659, "note": "NOAA 8516945 — Long Island Sound"},
        {"name": "Jamaica Bay (Inwood)",     "lat": 40.6226, "lng": -73.7576, "note": "NOAA tidal — Zone A monitoring"},
        {"name": "Sandy Hook, NJ",           "lat": 40.4669, "lng": -74.0094, "note": "NOAA 8531680 — outer harbor reference"},
    ]},
    "eoc": {"label": "EOC / Command", "color": "#facc15", "features": [
        {"name": "NYC EOC",        "lat": 40.6967, "lng": -73.9896, "note": "Primary EOC — 165 Cadman Plaza East"},
        {"name": "Pier 92 Backup", "lat": 40.7671, "lng": -74.0029, "note": "Backup EOC / Mass Casualty staging"},
        {"name": "FEMA Region 2",  "lat": 40.7143, "lng": -74.0071, "note": "26 Federal Plaza"},
    ]},
    "floodRisk": {"label": "Flood Risk Areas", "color": "#fb923c", "features": [
        {"name": "Red Hook, Brooklyn",     "lat": 40.6745, "lng": -74.0097, "note": "Zone AE — flooded Sandy 2012"},
        {"name": "Coney Island",           "lat": 40.5755, "lng": -73.9707, "note": "Zone AE — 10ft+ surge Sandy"},
        {"name": "Rockaway Peninsula",     "lat": 40.5874, "lng": -73.8261, "note": "Zone VE/AE — highest surge risk"},
        {"name": "Howard Beach",           "lat": 40.6570, "lng": -73.8378, "note": "Zone AE — interior flood risk"},
        {"name": "South Beach, SI",        "lat": 40.5842, "lng": -74.0783, "note": "Zone AE — major Sandy impact"},
        {"name": "Lower Manhattan (FiDi)", "lat": 40.7074, "lng": -74.0104, "note": "Zone AE — subway/utility risk"},
        {"name": "Breezy Point",           "lat": 40.5587, "lng": -73.9290, "note": "Zone VE — wave action"},
    ]},
}

NOAA_ENDPOINTS = [
    {"id": "nws_alerts_ny",     "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "Active Alerts — NY",             "url": "https://api.weather.gov/alerts/active?area=NY",                                                                                        "desc": "All active NWS alerts for New York State",               "tags": ["alerts","flood","tornado","winter storm"]},
    {"id": "nws_alerts_severe", "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "Extreme/Severe Alerts Only",      "url": "https://api.weather.gov/alerts/active?area=NY&severity=Extreme,Severe&status=Actual",                                                    "desc": "Only extreme and severe active alerts",                   "tags": ["extreme","severe","priority"]},
    {"id": "nws_forecast_nyc",  "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "7-Day Forecast — NYC",            "url": "https://api.weather.gov/gridpoints/OKX/33,37/forecast",                                                                                 "desc": "NWS OKX 7-day text forecast for NYC metro",               "tags": ["forecast","7-day","temperature"]},
    {"id": "nws_forecast_hrly", "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "Hourly Forecast — NYC",           "url": "https://api.weather.gov/gridpoints/OKX/33,37/forecast/hourly",                                                                          "desc": "Hour-by-hour forecast — temp, wind, precipitation prob",  "tags": ["hourly","wind","precipitation"]},
    {"id": "nws_grid_wind",     "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "Wind & Precip Grid — NYC",        "url": "https://api.weather.gov/gridpoints/OKX/33,37",                                                                                          "desc": "Full NWS gridpoint — wind, gusts, direction, QPF",        "tags": ["wind","QPF","precipitation","grid"]},
    {"id": "nws_obs_knyc",      "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "Observations — Central Park",     "url": "https://api.weather.gov/stations/KNYC/observations/latest",                                                                             "desc": "Latest surface observation from Central Park",            "tags": ["observations","current conditions","temperature"]},
    {"id": "nws_obs_kjfk",      "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "Observations — JFK Airport",      "url": "https://api.weather.gov/stations/KJFK/observations/latest",                                                                             "desc": "Latest surface observation from JFK",                     "tags": ["observations","airport","coastal"]},
    {"id": "nws_products_okx",  "cat": "NWS",    "color": "#60a5fa", "icon": "🌩", "name": "Text Products — NWS OKX",         "url": "https://api.weather.gov/products?office=OKX&limit=10",                                                                                  "desc": "Latest NWS text products: AFD, Coastal Hazards, etc.",    "tags": ["AFD","forecast discussion","text products"]},
    {"id": "coops_battery",     "cat": "CO-OPS", "color": "#34d399", "icon": "🌊", "name": "Water Level — The Battery",       "url": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8518750&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER", "desc": "Real-time water level at The Battery — primary NYC surge gauge", "tags": ["water level","surge","battery"]},
    {"id": "coops_predictions", "cat": "CO-OPS", "color": "#34d399", "icon": "🌊", "name": "Tidal Predictions — Battery 48h", "url": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&range=48&station=8518750&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json&application=EMBER", "desc": "High/low tide predictions — next 48 hours",               "tags": ["tide predictions","high tide","low tide"]},
    {"id": "coops_kings_point", "cat": "CO-OPS", "color": "#34d399", "icon": "🌊", "name": "Water Level — Kings Point",       "url": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8516945&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER", "desc": "Real-time water level — Long Island Sound",               "tags": ["water level","long island sound"]},
    {"id": "coops_sandy_hook",  "cat": "CO-OPS", "color": "#34d399", "icon": "🌊", "name": "Water Level — Sandy Hook, NJ",    "url": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8531680&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER", "desc": "Real-time water level at Sandy Hook — outer harbor ref",   "tags": ["water level","sandy hook","outer harbor"]},
    {"id": "coops_wind",        "cat": "CO-OPS", "color": "#34d399", "icon": "🌊", "name": "Wind — The Battery Station",      "url": "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8518750&product=wind&time_zone=lst_ldt&units=english&format=json&application=EMBER",                   "desc": "Real-time wind speed and direction at The Battery",        "tags": ["wind","meteorological"]},
    {"id": "coops_stations_ny", "cat": "CO-OPS", "color": "#34d399", "icon": "🌊", "name": "All CO-OPS Stations — NY",        "url": "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels&state=NY",                                       "desc": "All active water level stations in New York state",        "tags": ["stations","inventory"]},
    {"id": "ncei_datasets",     "cat": "NCEI",   "color": "#f59e0b", "icon": "📊", "name": "NCEI Dataset Catalog",            "url": "https://www.ncei.noaa.gov/access/services/support/v3/datasets.json",                                                                    "desc": "Full catalog of all NCEI datasets",                        "tags": ["catalog","datasets","metadata"]},
    {"id": "ncei_daily_cp",     "cat": "NCEI",   "color": "#f59e0b", "icon": "📊", "name": "Daily Summaries — Central Park",  "url": "DYNAMIC_CP",  "dynamic": True, "desc": "Last 7 days of daily weather from Central Park",           "tags": ["daily summaries","temperature","precipitation","snow"]},
    {"id": "ncei_daily_jfk",    "cat": "NCEI",   "color": "#f59e0b", "icon": "📊", "name": "Daily Summaries — JFK Airport",   "url": "DYNAMIC_JFK", "dynamic": True, "desc": "Last 7 days of daily weather from JFK Airport",             "tags": ["daily summaries","jfk","coastal"]},
    {"id": "ncei_storm_meta",   "cat": "NCEI",   "color": "#f59e0b", "icon": "📊", "name": "Storm Events Dataset Metadata",   "url": "https://www.ncei.noaa.gov/access/services/support/v3/datasets/storm-events.json",                                                      "desc": "Metadata for NCEI storm events database",                  "tags": ["storm events","metadata","historical"]},
    {"id": "spc_watches",       "cat": "SPC",    "color": "#f87171", "icon": "⚡", "name": "Active Watches (Tornado/SVR)",    "url": "https://www.spc.noaa.gov/products/watch/ActiveWW.txt",   "text": True,  "desc": "Currently active SPC watches",                             "tags": ["watches","tornado","severe thunderstorm"]},
    {"id": "spc_day1",          "cat": "SPC",    "color": "#f87171", "icon": "⚡", "name": "Day 1 Convective Outlook",        "url": "https://www.spc.noaa.gov/products/outlook/day1otlk.txt", "text": True,  "desc": "SPC Day 1 convective outlook — categorical severe risk",   "tags": ["convective","outlook","severe"]},
    {"id": "swpc_alerts",       "cat": "SWPC",   "color": "#a78bfa", "icon": "☀️", "name": "Space Weather Alerts",           "url": "https://services.swpc.noaa.gov/products/alerts.json",                                                                                   "desc": "Current space weather alerts, watches, warnings",          "tags": ["space weather","geomagnetic","solar flare","GPS"]},
    {"id": "swpc_solar_wind",   "cat": "SWPC",   "color": "#a78bfa", "icon": "☀️", "name": "Solar Wind — DSCOVR Real-Time",  "url": "https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json",                                                                 "desc": "Real-time solar wind plasma from DSCOVR satellite",        "tags": ["solar wind","real-time","DSCOVR"]},
    {"id": "swpc_kp",           "cat": "SWPC",   "color": "#a78bfa", "icon": "☀️", "name": "Planetary K-Index (1-min)",      "url": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",                                                                        "desc": "1-minute Kp index — geomagnetic disturbance level",        "tags": ["Kp index","geomagnetic"]},
]

MAP_CONNECTED_IDS = {
    "coops_battery", "coops_kings_point", "coops_sandy_hook",
    "coops_predictions", "coops_wind",
    "nws_alerts_ny", "nws_alerts_severe",
    "nws_obs_knyc", "nws_obs_kjfk",
}

REFRESH_INTERVALS = {
    "coops_battery": 300, "coops_kings_point": 300, "coops_sandy_hook": 300,
    "coops_wind": 300, "coops_predictions": 1800,
    "nws_alerts_ny": 180, "nws_alerts_severe": 180,
    "nws_obs_knyc": 300, "nws_obs_kjfk": 300,
    "nws_forecast_nyc": 3600, "nws_forecast_hrly": 3600, "nws_grid_wind": 3600,
    "ncei_daily_cp": 86400, "ncei_daily_jfk": 86400,
}

LIVING_ATLAS_FILTERS = {
    "All Public": "", "Living Atlas Only": "owner:esri_livingatlas",
    "Flood / Hydrology": "tags:flood OR tags:hydrology",
    "Hurricanes": "tags:hurricane OR tags:storm surge",
    "Wildfire": "tags:wildfire OR tags:fire perimeter",
    "Emergency Mgmt": "tags:emergency management OR tags:disaster",
    "Critical Infra": "tags:critical infrastructure",
    "Climate / Weather": "tags:climate OR tags:weather",
    "NYC / New York": "tags:New York City OR tags:NYC",
    "FEMA": "tags:FEMA OR owner:FEMA",
}
ITEM_TYPES = ["", "Feature Layer", "Map Service", "Image Service",
              "Vector Tile Layer", "Web Map", "Web Scene", "Feature Collection",
              "StoryMap", "Dashboard"]

WIND_STATIONS = [
    {"id": "KNYC", "name": "Central Park", "lat": 40.7789, "lng": -73.9692},
    {"id": "KJFK", "name": "JFK Airport",  "lat": 40.6413, "lng": -73.7781},
    {"id": "KEWR", "name": "Newark",       "lat": 40.6895, "lng": -74.1745},
    {"id": "KLGA", "name": "LaGuardia",    "lat": 40.7772, "lng": -73.8726},
]

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS — all defined at module level before any UI code
# ═══════════════════════════════════════════════════════════════════════════════

def ping_ollama():
    if not OLLAMA_API_KEY: return "no-key"
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", headers=OLLAMA_HEADERS, timeout=5)
        return r.ok
    except:
        return False

def fetch_live(ep):
    try:
        r = requests.get(ep["url"], timeout=7)
        r.raise_for_status()
        return {"success": True, "data": r.json(), "name": ep["name"], "type": ep["type"]}
    except Exception as e:
        return {"success": False, "error": str(e), "name": ep["name"], "type": ep["type"]}

def summarize_api(result):
    if not result["success"]: return f"[{result['name']}: unavailable — {result['error']}]"
    d, t = result["data"], result["type"]
    try:
        if t == "weather" and "features" in d:
            alerts = "; ".join(f"{f['properties']['event']} — {str(f['properties'].get('headline',''))[:80]}" for f in d["features"][:3])
            return f"NWS Alerts (NY): {len(d['features'])} active. {alerts or 'None'}"
        if t == "forecast" and "properties" in d:
            return "NWS Forecast: " + "; ".join(f"{p['name']}: {p['shortForecast']}, {p['temperature']}°{p['temperatureUnit']}" for p in d["properties"].get("periods", [])[:3])
        if t == "flood" and "value" in d:
            return "USGS Gauges: " + "; ".join(f"{g['sourceInfo']['siteName']}: {g['values'][0]['value'][0]['value'] if g.get('values') else 'N/A'} ft" for g in d["value"].get("timeSeries", [])[:4])
        if t == "fema" and "DisasterDeclarationsSummaries" in d:
            return "FEMA NY: " + "; ".join(f"{x['incidentType']} — {x['declarationTitle']}" for x in d["DisasterDeclarationsSummaries"][:3])
        if t == "civic" and isinstance(d, list):
            return "NYC 311: " + "; ".join(f"{x.get('complaint_type','?')}: {x.get('descriptor','?')} ({x.get('borough','?')})" for x in d[:3])
        return f"[{result['name']}: received]"
    except:
        return f"[{result['name']}: parse error]"

def build_live_readings(api_results):
    readings = {}
    for r in api_results:
        if not r.get("success"): continue
        d = r.get("data", {})
        if r.get("type") == "flood" and isinstance(d, dict) and "value" in d:
            for ts in d["value"].get("timeSeries", []):
                site = ts.get("sourceInfo", {}).get("siteName", "")
                vals = ts.get("values", [{}])[0].get("value", [])
                if vals and site:
                    try:
                        fval = float(vals[-1].get("value", 0))
                        readings[site] = {"level": f"{fval:.2f}", "unit": "ft", "source": "USGS",
                                          "status": "flood" if fval > 10 else "elevated" if fval > 5 else "normal"}
                    except:
                        pass
        if r.get("type") == "weather" and isinstance(d, dict) and "features" in d:
            for f in d["features"]:
                evt = f.get("properties", {}).get("event", "")
                if any(kw in evt.lower() for kw in ["flood", "surge", "coastal"]):
                    readings["__flood_alert__"] = {"event": evt, "severity": f["properties"].get("severity", ""),
                                                   "headline": (f["properties"].get("headline") or "")[:120]}
                    break
    return readings

def resolve_url(ep):
    if not ep.get("dynamic"): return ep["url"]
    today    = _dt.date.today().isoformat()
    week_ago = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
    base = "https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&dataTypes=TMAX,TMIN,PRCP,SNOW,AWND&format=json&units=standard"
    if ep["id"] == "ncei_daily_cp":  return f"{base}&stations=USW00094728&startDate={week_ago}&endDate={today}"
    if ep["id"] == "ncei_daily_jfk": return f"{base}&stations=USW00094789&startDate={week_ago}&endDate={today}"
    return ep["url"]

def fetch_noaa_ep(ep):
    url = resolve_url(ep)
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "EMBER/1.0"})
        r.raise_for_status()
        is_text = ep.get("text") or "text/plain" in r.headers.get("content-type", "")
        return {"success": True, "data": r.text if is_text else r.json(),
                "text": is_text, "ep": ep, "fetched_at": _dt.datetime.now().strftime("%H:%M:%S")}
    except Exception as e:
        return {"success": False, "error": str(e), "ep": ep,
                "fetched_at": _dt.datetime.now().strftime("%H:%M:%S")}

def summarize_noaa(result):
    if not result["success"]: return f"[{result['ep']['name']}: failed — {result['error']}]"
    d, ep, ts = result["data"], result["ep"], result.get("fetched_at", "?")
    try:
        if result.get("text"): return f"[NOAA {ep['name']} @ {ts}]\n{str(d)[:800]}"
        if "features" in d and "alert" in ep["id"]:
            alerts = "\n".join(f"  - {f['properties']['event']} ({f['properties']['severity']}): {str(f['properties'].get('headline',''))[:90]}" for f in d["features"][:5])
            return f"[NWS Alerts @ {ts}: {len(d['features'])} active]\n{alerts or '  None active'}"
        if "forecast" in ep["id"] and "properties" in d and "periods" in d.get("properties", {}):
            periods = "\n".join(f"  {p['name']}: {p['shortForecast']}, {p['temperature']}°{p['temperatureUnit']}" for p in d["properties"]["periods"][:6])
            return f"[NWS Forecast @ {ts}]\n{periods}"
        if "grid" in ep["id"] and "properties" in d:
            p = d["properties"]
            ws  = [v for v in p.get("windSpeed", {}).get("values", [])[:6] if v.get("value") is not None]
            qpf = [v for v in p.get("quantitativePrecipitation", {}).get("values", [])[:6] if v.get("value") is not None]
            speeds = ", ".join(f"{v['value']*0.621371:.0f}mph" for v in ws)
            inches = ", ".join(f"{v['value']*0.0393701:.2f}\"" for v in qpf)
            return f"[NWS Grid Wind & Precip @ {ts}]\n  Wind (next 6h): {speeds}\n  QPF (next 6h): {inches}"
        if "obs" in ep["id"] and "properties" in d:
            p = d["properties"]
            tempF   = f"{(p['temperature']['value']*9/5+32):.1f}°F" if p.get("temperature", {}).get("value") is not None else "?"
            windMph = f"{(p['windSpeed']['value']*0.621371):.1f}mph"  if p.get("windSpeed", {}).get("value")  is not None else "?"
            return f"[NWS Obs — {ep['name']} @ {ts}]\n  Temp: {tempF} | Wind: {windMph} | {p.get('textDescription','?')}"
        if "coops" in ep["id"] and "data" in d and ep["id"] != "coops_wind":
            latest = d["data"][-1] if d.get("data") else {}
            meta   = d.get("metadata", {})
            return f"[CO-OPS {meta.get('name', ep['name'])} @ {ts}]\n  Water level: {latest.get('v','?')} ft MLLW @ {latest.get('t','?')}"
        if ep["id"] == "coops_predictions" and "predictions" in d:
            preds = "\n".join(f"  {'HIGH' if p['type']=='H' else 'low '} {p['v']}ft @ {p['t']}" for p in d["predictions"][:8])
            return f"[CO-OPS Tidal Predictions @ {ts}]\n{preds}"
        if ep["id"] == "coops_wind" and "data" in d:
            w = d["data"][-1] if d.get("data") else {}
            return f"[CO-OPS Wind @ {ts}]\n  Speed: {w.get('s','?')} knots | Dir: {w.get('dr','?')} | Gusts: {w.get('g','?')} knots"
        if "stations" in ep["id"] and "stations" in d:
            return f"[CO-OPS Stations: {len(d['stations'])}]\n" + "\n".join(f"  {s['id']}: {s['name']}" for s in d["stations"][:8])
        if "datasets" in d:
            return f"[NCEI Datasets: {len(d['datasets'])}]\n" + "\n".join(f"  {ds['id']}: {ds['name']}" for ds in d["datasets"][:10])
        if isinstance(d, list) and len(d) > 0 and isinstance(d[0], dict) and "DATE" in d[0]:
            rows = "\n".join(f"  {r['DATE']}: TMAX={r.get('TMAX','?')} TMIN={r.get('TMIN','?')} PRCP={r.get('PRCP','?')}" for r in d[:7])
            return f"[NCEI Daily Summaries @ {ts}]\n{rows}"
        if isinstance(d, list) and ep["id"] == "swpc_alerts":
            return f"[Space Weather Alerts @ {ts}: {len(d)}]\n" + "\n".join(f"  {str(a.get('message',''))[:120]}" for a in d[:4])
        return f"[NOAA {ep['name']} @ {ts}]: {json.dumps(d)[:400]}"
    except Exception as e:
        return f"[NOAA {ep['name']}: parse error — {e}]"

def upsert_noaa_kb(ep, result):
    content = summarize_noaa(result)
    ts      = result.get("fetched_at", _dt.datetime.now().strftime("%H:%M:%S"))
    entry   = {"name": f"NOAA: {ep['name']}", "item_id": ep["id"],
               "content": f"[NOAA Open Data — {ep['name']}]\nFetched: {ts}\nSource: {resolve_url(ep)}\n\n{content}",
               "fetched_at": ts, "map_connected": ep["id"] in MAP_CONNECTED_IDS}
    items = st.session_state.noaa_items
    idx   = next((i for i, x in enumerate(items) if x["item_id"] == ep["id"]), None)
    if idx is not None: items[idx] = entry
    else:               items.append(entry)

def extract_map_readings_from_noaa():
    readings = {}
    for ep_id, result in st.session_state.get("noaa_results", {}).items():
        if not result.get("success"): continue
        d  = result["data"]
        ep = result["ep"]
        ts = result.get("fetched_at", "?")
        # CO-OPS water levels
        if isinstance(d, dict) and "data" in d and ep_id.startswith("coops_") and ep_id not in ("coops_wind", "coops_predictions", "coops_stations_ny"):
            meta = d.get("metadata", {})
            vals = d.get("data", [])
            if vals:
                try:
                    fval = float(vals[-1].get("v", 0))
                    name = meta.get("name") or ep["name"]
                    readings[name] = {"level": f"{fval:.2f}", "unit": "ft MLLW", "source": f"CO-OPS @ {ts}",
                                      "status": "flood" if fval > 10 else "elevated" if fval > 5 else "normal"}
                except:
                    pass
        # CO-OPS next HIGH tide
        if isinstance(d, dict) and "predictions" in d and ep_id == "coops_predictions":
            next_high = next((p for p in d["predictions"] if p.get("type") == "H"), None)
            if next_high:
                readings["__next_high_tide__"] = {"level": next_high["v"], "unit": "ft MLLW",
                                                   "time": next_high["t"], "source": f"CO-OPS @ {ts}"}
        # CO-OPS wind
        if isinstance(d, dict) and "data" in d and ep_id == "coops_wind":
            wvals = d.get("data", [])
            if wvals:
                w = wvals[-1]
                readings["__battery_wind__"] = {"speed_knots": w.get("s","?"), "direction": w.get("dr","?"),
                                                 "gusts_knots": w.get("g","?"), "source": f"CO-OPS @ {ts}"}
        # NWS flood alerts
        if isinstance(d, dict) and "features" in d and "alert" in ep_id:
            for f in d["features"]:
                evt = f.get("properties", {}).get("event", "")
                if any(kw in evt.lower() for kw in ["flood", "surge", "coastal"]):
                    readings["__flood_alert__"] = {"event": evt, "severity": f["properties"].get("severity",""),
                                                   "headline": (f["properties"].get("headline") or "")[:120],
                                                   "source": f"NWS @ {ts}"}
                    break
        # NWS surface obs
        if isinstance(d, dict) and "properties" in d and "obs" in ep_id:
            p          = d["properties"]
            station_id = ep_id.replace("nws_obs_", "").upper()
            speed_ms   = p.get("windSpeed",    {}).get("value")
            gust_ms    = p.get("windGust",     {}).get("value")
            dir_deg    = p.get("windDirection",{}).get("value")
            precip_mm  = p.get("precipitationLastHour", {}).get("value")
            if speed_ms is not None and dir_deg is not None:
                readings[f"__nws_obs_{station_id}__"] = {
                    "station": station_id,
                    "speed_mph": round(speed_ms * 2.237, 1),
                    "gust_mph":  round(gust_ms * 2.237, 1) if gust_ms else None,
                    "dir_deg":   dir_deg,
                    "precip_in": round(precip_mm * 0.0393701, 2) if precip_mm else None,
                    "desc":      p.get("textDescription", ""),
                    "source":    f"NWS @ {ts}",
                }
    return readings

def auto_fetch_map_endpoints():
    ep_map = {ep["id"]: ep for ep in NOAA_ENDPOINTS}
    for ep_id in MAP_CONNECTED_IDS:
        ep = ep_map.get(ep_id)
        if ep and ep_id not in st.session_state.noaa_results:
            result = fetch_noaa_ep(ep)
            st.session_state.noaa_results[ep_id] = result
            if result["success"]:
                upsert_noaa_kb(ep, result)

def refresh_stale_endpoints():
    now    = _dt.datetime.now()
    ep_map = {ep["id"]: ep for ep in NOAA_ENDPOINTS}
    for ep_id, interval in REFRESH_INTERVALS.items():
        if interval == 0: continue
        result = st.session_state.noaa_results.get(ep_id)
        if result and result.get("fetched_at"):
            try:
                fetched  = _dt.datetime.strptime(result["fetched_at"], "%H:%M:%S").replace(
                    year=now.year, month=now.month, day=now.day)
                if (now - fetched).total_seconds() < interval: continue
            except:
                pass
        ep = ep_map.get(ep_id)
        if not ep: continue
        new_result = fetch_noaa_ep(ep)
        st.session_state.noaa_results[ep_id] = new_result
        if new_result["success"]:
            upsert_noaa_kb(ep, new_result)

def fetch_wind_obs():
    results = []
    for s in WIND_STATIONS:
        try:
            r = requests.get(f"https://api.weather.gov/stations/{s['id']}/observations/latest",
                             timeout=6, headers={"User-Agent": "EMBER/1.0"})
            if not r.ok: continue
            p = r.json()["properties"]
            def _mph(ms): return round(ms * 2.237, 0) if ms is not None else None
            def _in(mm):  return round(mm * 0.0393701, 2) if mm is not None else None
            results.append({**s,
                "speed_mph": _mph(p.get("windSpeed",           {}).get("value")),
                "gust_mph":  _mph(p.get("windGust",            {}).get("value")),
                "dir_deg":   p.get("windDirection", {}).get("value"),
                "temp_f":    round(p["temperature"]["value"]*9/5+32, 0) if p.get("temperature",{}).get("value") is not None else None,
                "precip_in": _in(p.get("precipitationLastHour",{}).get("value")),
                "desc":      p.get("textDescription", ""),
            })
        except:
            continue
    return results

def build_map(active_layers, show_radar=True, show_wind=True, wind_obs=None,
              live_readings=None, gauge_data=None, map_layers=None):
    live_readings = live_readings or {}
    wind_obs      = wind_obs or []
    gauge_data    = gauge_data or {}
    map_layers    = map_layers or []
    m = folium.Map(location=[40.7128, -74.006], zoom_start=10,
                   tiles="CartoDB dark_matter", prefer_canvas=True)
    # NEXRAD radar tiles with 5-min cache buster
    if show_radar:
        epoch_5min = int(_time.time() // 300)
        folium.TileLayer(
            tiles=f"https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{{z}}/{{x}}/{{y}}.png?_={epoch_5min}",
            name="NEXRAD Radar", attr="NEXRAD &copy; Iowa State MESONET",
            opacity=0.65, overlay=True, control=True,
        ).add_to(m)

    # ── Live tidal gauge layer (separate from static gauge markers) ────────────
    if gauge_data:
        tg_fg = folium.FeatureGroup(name="🌊 Live Tidal Gauges (CO-OPS)", show=True)
        for sid, gd in gauge_data.items():
            ld = gd.get("level")
            if not ld or not ld.get("lat") or not ld.get("lng"):
                # Try to find coords from the station list if level data has no coords
                continue
            lat, lng = ld.get("lat", 0), ld.get("lng", 0)
            if lat == 0 and lng == 0:
                continue
            color   = gauge_marker_color(gd)
            lft     = ld.get("level_ft", 0)
            status  = ld.get("status", "NORMAL")
            popup_h = build_gauge_popup(gd)

            # Pulsing circle — outer ring shows flood status, inner solid
            folium.CircleMarker(
                location=[lat, lng], radius=16,
                color=color, fill=False, weight=2, opacity=0.5,
            ).add_to(tg_fg)
            folium.CircleMarker(
                location=[lat, lng], radius=9,
                color=color, fill=True, fill_color=color, fill_opacity=0.85, weight=2,
                popup=folium.Popup(popup_h, max_width=280),
                tooltip=f"🌊 {ld.get('station_name','Station')} — {lft:.2f}ft MLLW — {status}",
            ).add_to(tg_fg)

            # Level label
            folium.Marker(
                location=[lat, lng],
                icon=folium.DivIcon(
                    html=f'<div style="font-family:monospace;font-size:10px;font-weight:700;'
                         f'color:{color};background:#07090dcc;padding:1px 4px;border-radius:3px;'
                         f'border:1px solid {color}55;white-space:nowrap;margin-top:14px;margin-left:12px">'
                         f'{lft:.2f}ft</div>',
                    icon_size=(60, 20), icon_anchor=(0, 0)
                )
            ).add_to(tg_fg)

        tg_fg.add_to(m)
    # Marker layers
    for key, layer in MAP_POINTS.items():
        if key not in active_layers: continue
        fg = folium.FeatureGroup(name=layer["label"])
        for f in layer["features"]:
            reading      = None
            marker_color = layer["color"]
            if key == "gauges" and live_readings:
                for site_name, r in live_readings.items():
                    if site_name.startswith("__"): continue
                    fname_word = f["name"].split(",")[0].lower().split()[0]
                    if fname_word in site_name.lower() or site_name.lower().split(" at ")[0] in f["name"].lower():
                        reading = r
                        marker_color = {"flood": "#f87171", "elevated": "#facc15", "normal": "#4ade80"}.get(r.get("status","normal"), layer["color"])
                        break
            live_html = ""
            if reading:
                sc = {"flood": "#f87171", "elevated": "#facc15", "normal": "#4ade80"}.get(reading.get("status","normal"), "#4ade80")
                live_html = (f'<div style="border-top:1px solid #1e2a40;padding-top:5px;margin-top:4px">'
                             f'<span style="color:{sc};font-weight:700">{reading.get("level","?")} {reading.get("unit","")}</span>'
                             f'<span style="color:#556;font-size:9px;margin-left:4px">{reading.get("status","").upper()}</span><br>'
                             f'<span style="color:#446;font-size:9px">{reading.get("source","")}</span></div>')
            popup_html = (f'<div style="font-family:monospace;font-size:11px">'
                          f'<b style="color:{marker_color}">{f["name"]}</b><br>'
                          f'<span style="color:#778">{f["note"]}</span>{live_html}</div>')
            folium.CircleMarker(
                location=[f["lat"], f["lng"]], radius=8,
                color=marker_color, fill=True, fill_color=marker_color, fill_opacity=0.6,
                popup=folium.Popup(popup_html, max_width=240),
                tooltip=f'{f["name"]}' + (f' — {reading.get("level","?")} {reading.get("unit","")}' if reading else "")
            ).add_to(fg)
        fg.add_to(m)
    # Wind arrows
    if show_wind and wind_obs:
        wfg = folium.FeatureGroup(name="Wind Observations")
        for o in wind_obs:
            if o.get("speed_mph") is None or o.get("dir_deg") is None: continue
            spd   = int(o["speed_mph"])
            gust  = int(o["gust_mph"]) if o.get("gust_mph") else None
            color = "#4ade80" if spd < 15 else "#facc15" if spd < 25 else "#fb923c" if spd < 40 else "#f87171"
            to_dir = (o["dir_deg"] + 180) % 360
            html = (f'<div style="font-family:monospace;text-align:center">'
                    f'<div style="transform:rotate({to_dir}deg);font-size:20px;color:{color}">↑</div>'
                    f'<div style="font-size:9px;font-weight:700;color:{color};background:#07090dcc;'
                    f'padding:1px 3px;border-radius:2px">{spd}{"g"+str(gust) if gust else ""}mph</div></div>')
            popup_txt = (f'<b style="color:{color}">{o["id"]} — {o["name"]}</b><br>'
                         f'Wind: {spd}mph from {int(o["dir_deg"])}°'
                         + (f' (gusts {gust}mph)' if gust else '')
                         + (f'<br>Precip (1h): {o["precip_in"]}"' if o.get("precip_in") is not None else '')
                         + (f'<br>Temp: {int(o["temp_f"])}°F' if o.get("temp_f") is not None else '')
                         + (f'<br>{o["desc"]}' if o.get("desc") else ''))
            folium.Marker(
                location=[o["lat"], o["lng"]],
                icon=folium.DivIcon(html=html, icon_size=(50, 40), icon_anchor=(25, 10)),
                popup=folium.Popup(f'<div style="font-family:monospace;font-size:11px">{popup_txt}</div>', max_width=220),
                tooltip=f'{o["id"]}: {spd}mph'
            ).add_to(wfg)
        wfg.add_to(m)
    # ── User-added map layers (NYC Open Data + ESRI Feature Layers) ───────────
    LAYER_COLORS = ["#f472b6","#818cf8","#2dd4bf","#fb7185","#a3e635","#fbbf24","#60a5fa","#c084fc"]
    for li, layer in enumerate(map_layers):
        if not layer.get("visible", True): continue
        lcolor = layer.get("color", LAYER_COLORS[li % len(LAYER_COLORS)])
        fg = folium.FeatureGroup(name=f"{layer.get('icon','📍')} {layer['name']}", show=True)

        for feat in layer.get("features", []):
            ftype = feat.get("type", "point")

            if ftype == "point":
                popup_h = layer.get("popup_fn")(feat) if layer.get("popup_fn") else (
                    f'<div style="font-family:monospace;font-size:11px">'
                    f'<b style="color:{lcolor}">{feat.get("label","") or layer["name"]}</b></div>'
                )
                folium.CircleMarker(
                    location=[feat["lat"], feat["lng"]], radius=6,
                    color=lcolor, fill=True, fill_color=lcolor, fill_opacity=0.7, weight=1.5,
                    popup=folium.Popup(popup_h, max_width=260),
                    tooltip=feat.get("label", layer["name"])[:60],
                ).add_to(fg)

            elif ftype == "polygon":
                try:
                    folium.GeoJson(
                        {"type": "Feature", "geometry": feat["geometry"], "properties": feat["props"]},
                        style_function=lambda f, c=lcolor: {
                            "fillColor": c, "color": c, "weight": 2,
                            "fillOpacity": 0.25, "opacity": 0.8
                        },
                        tooltip=str(list(feat["props"].values())[0])[:60] if feat["props"] else layer["name"],
                    ).add_to(fg)
                except:
                    pass

            elif ftype == "line":
                try:
                    folium.GeoJson(
                        {"type": "Feature", "geometry": feat["geometry"], "properties": feat["props"]},
                        style_function=lambda f, c=lcolor: {"color": c, "weight": 3, "opacity": 0.8},
                        tooltip=str(list(feat["props"].values())[0])[:60] if feat["props"] else layer["name"],
                    ).add_to(fg)
                except:
                    pass

        fg.add_to(m)

    folium.LayerControl().add_to(m)
    return m

def build_context(files, api_results, active_modules, esri_items, noaa_items=None, gauge_data=None):
    ctx = "=== NYC EMERGENCY MANAGEMENT KNOWLEDGE BASE ===\n\n"
    for key, mod in NYC_KB.items():
        if key in active_modules:
            ctx += f"--- {mod['label']} [{mod['source']}] ---\n{mod['data']}\n\n"
    if gauge_data:
        ctx += "--- LIVE TIDAL GAUGE READINGS (CO-OPS, 6-min updates) ---\n"
        for sid, gd in gauge_data.items():
            ld = gd.get("level")
            if not ld: continue
            nh = gd.get("next_high")
            nl = gd.get("next_low")
            ctx += (f"Station {sid} — {ld.get('station_name','?')}: "
                    f"{ld.get('level_ft','?')} ft MLLW | {ld.get('status','?')} | "
                    f"Trend: {ld.get('trend_str','?')} | "
                    f"Next HIGH: {nh['level_ft']:.2f}ft @ {nh['time'] if nh else 'N/A'} | "
                    f"Next LOW: {nl['level_ft']:.2f}ft @ {nl['time'] if nl else 'N/A'} | "
                    f"Fetched: {gd.get('fetched_at','?')}\n")
        ctx += "\n"
    if api_results:
        ctx += "--- LIVE API DATA ---\n"
        for r in api_results: ctx += summarize_api(r) + "\n"
        ctx += "\n"
    if noaa_items:
        ctx += "--- NOAA OPEN DATA (auto-fetched) ---\n"
        for item in noaa_items: ctx += item["content"] + "\n\n"
    if files:
        ctx += "--- UPLOADED DOCUMENTS ---\n"
        for f in files: ctx += f"[File: {f['name']}]\n{f['content'][:4000]}\n\n"
    if esri_items:
        ctx += "--- ESRI / LIVING ATLAS LAYERS ---\n"
        for item in esri_items: ctx += item["content"] + "\n\n"
    return ctx

def stream_ollama(messages, context):
    if not OLLAMA_API_KEY:
        yield "⚠ No API key. Set OLLAMA_API_KEY. Get one at https://ollama.com/settings/keys"
        return
    system_prompt = (f"You are EMBER — Emergency Management Body of Evidence & Resources — "
                     f"an AI for NYC emergency managers.\n\nKNOWLEDGE BASE:\n{context}\n\n"
                     f"RULES:\n1. Lead with operationally critical information first.\n"
                     f"2. Cite sources: [NYC OEM], [NWS], [FEMA], [USGS], [CO-OPS], [ESRI], etc.\n"
                     f"3. For location queries, prioritize zone and risk data.\n"
                     f"4. Flag data gaps. Use headers and bullets for action items.\n"
                     f"5. For life-safety queries, always include emergency contact numbers.\n"
                     f"6. Never hallucinate.")
    payload = {"model": OLLAMA_MODEL, "stream": True,
               "messages": [{"role": "system", "content": system_prompt}] + messages[-10:]}
    try:
        with requests.post(f"{OLLAMA_HOST}/api/chat", json=payload,
                           headers=OLLAMA_HEADERS, stream=True, timeout=90) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    obj   = json.loads(line)
                    token = obj.get("message", {}).get("content", "")
                    if token: yield token
                    if obj.get("done"): return
    except requests.exceptions.HTTPError as e:
        yield f"\n\n⚠ Ollama Cloud error {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        yield f"\n\n⚠ Connection error: {e}"

def search_agol(query, filter_expr="", item_type="", num=8, start=1):
    q      = query.strip() or "*"
    scope  = ["access:public"]
    if filter_expr: scope.append(f"({filter_expr})")
    if item_type:   scope.append(f'type:"{item_type}"')
    params = {"f": "json", "q": f"{q} {' AND '.join(scope)}",
              "num": str(num), "start": str(start), "sortField": "relevance", "sortOrder": "desc"}
    try:
        r = requests.get(f"{AGOL_BASE}/search", params=params, timeout=10)
        r.raise_for_status()
        d = r.json()
        if "error" in d: return [], 0, d["error"].get("message", "AGOL error")
        return d.get("results", []), d.get("total", 0), None
    except Exception as e:
        return [], 0, str(e)

def fetch_item_metadata(item_id):
    try:
        r = requests.get(f"{AGOL_BASE}/content/items/{item_id}", params={"f": "json"}, timeout=8)
        r.raise_for_status()
        item = r.json()
        try:
            dr   = requests.get(f"{AGOL_BASE}/content/items/{item_id}/data", params={"f": "json"}, timeout=8)
            data = dr.json() if dr.ok else None
        except:
            data = None
        return item, data, None
    except Exception as e:
        return None, None, str(e)

def format_item_for_context(item, data=None):
    if not item: return ""
    tags = ", ".join(item.get("tags", []))
    url  = item.get("url", "") or f"https://www.arcgis.com/home/item.html?id={item.get('id','')}"
    block = (f"[ESRI/Living Atlas: {item.get('title','')}]\n"
             f"  ID: {item.get('id','')} | Type: {item.get('type','')} | Owner: {item.get('owner','')}\n"
             f"  Description: {re.sub(r'<[^>]+>', '', item.get('description',''))[:600]}\n"
             f"  Tags: {tags} | Snippet: {item.get('snippet','')}\n"
             f"  Extent: {item.get('extent','N/A')} | Access: {item.get('access','')}\n"
             f"  Updated: {str(item.get('modified',''))[:10]} | URL: {url}")
    if data and isinstance(data, dict):
        if "layers" in data:
            block += "\n  Layers: " + ", ".join(f"{l.get('id')}:{l.get('name','')}" for l in data["layers"])
        if "operationalLayers" in data:
            block += "\n  Operational Layers: " + ", ".join(l.get("title","?") for l in data["operationalLayers"])
    return block

# ═══════════════════════════════════════════════════════════════════════════════
# NYC OPEN DATA (SOCRATA) HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

# Curated emergency-relevant NYC Open Data datasets with known geometry columns
NYC_OPEN_DATA_PRESETS = [
    {
        "id":       "fhrw-4uyv",
        "name":     "311 Service Requests (live)",
        "agency":   "311",
        "lat_col":  "latitude",
        "lng_col":  "longitude",
        "label_col":"complaint_type",
        "desc":     "Real-time 311 complaints — filterable by type, borough, date",
        "color":    "#60a5fa",
        "icon":     "📞",
        "filter":   None,
    },
    {
        "id":       "nuhi-jiwk",
        "name":     "FDNY Incidents (fire/EMS)",
        "agency":   "FDNY",
        "lat_col":  "latitude",
        "lng_col":  "longitude",
        "label_col":"incident_type_desc",
        "desc":     "FDNY incident data — fire, EMS, hazmat",
        "color":    "#f87171",
        "icon":     "🚒",
        "filter":   None,
    },
    {
        "id":       "2bnn-yakx",
        "name":     "NYC Cooling Centers",
        "agency":   "DOHMH",
        "lat_col":  "latitude",
        "lng_col":  "longitude",
        "label_col":"site_name",
        "desc":     "Active cooling center locations during heat emergencies",
        "color":    "#34d399",
        "icon":     "❄️",
        "filter":   None,
    },
    {
        "id":       "uqnk-2pcv",
        "name":     "Hurricane Evacuation Centers",
        "agency":   "OEM",
        "lat_col":  "latitude",
        "lng_col":  "longitude",
        "label_col":"facility_name",
        "desc":     "Designated hurricane evacuation shelter locations",
        "color":    "#facc15",
        "icon":     "🏫",
        "filter":   None,
    },
    {
        "id":       "43nn-pn8y",
        "name":     "NYPD Incidents",
        "agency":   "NYPD",
        "lat_col":  "latitude",
        "lng_col":  "longitude",
        "label_col":"ofns_desc",
        "desc":     "NYPD incident reports — filterable by type and date",
        "color":    "#a78bfa",
        "icon":     "🚔",
        "filter":   None,
    },
    {
        "id":       "5uac-w243",
        "name":     "NYCHA Developments",
        "agency":   "NYCHA",
        "lat_col":  "latitude",
        "lng_col":  "longitude",
        "label_col":"development",
        "desc":     "NYCHA public housing developments — vulnerable population locations",
        "color":    "#fb923c",
        "icon":     "🏢",
        "filter":   None,
    },
]

def search_nyc_open_data(query: str, app_token: str = "", limit: int = 20) -> list[dict]:
    """Search the NYC Open Data catalog using the Socrata catalog API."""
    try:
        params = {"q": query, "limit": limit, "only": "dataset"}
        headers = {}
        if app_token:
            headers["X-App-Token"] = app_token
        r = requests.get(
            "https://data.cityofnewyork.us/api/catalog/v1",
            params=params, headers=headers, timeout=10
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return [
            {
                "id":          d.get("resource", {}).get("id", ""),
                "name":        d.get("resource", {}).get("name", ""),
                "description": d.get("resource", {}).get("description", "")[:300],
                "agency":      d.get("classification", {}).get("owning_department", ""),
                "category":    d.get("classification", {}).get("categories", [""])[0] if d.get("classification", {}).get("categories") else "",
                "updated":     d.get("resource", {}).get("updatedAt", "")[:10],
                "columns":     d.get("resource", {}).get("columns_name", []),
                "permalink":   d.get("permalink", ""),
            }
            for d in results if d.get("resource", {}).get("id")
        ]
    except Exception as e:
        return []

def fetch_socrata_dataset(
    dataset_id: str,
    app_token: str = "",
    lat_col: str = "latitude",
    lng_col: str = "longitude",
    label_col: str = "",
    where_clause: str = "",
    limit: int = 500,
) -> dict:
    """
    Fetch rows from a Socrata dataset and return as a mappable dict.
    Uses the v2 /resource/ endpoint (GeoJSON output).
    Returns {"features": [...], "error": None} where each feature has lat/lng/label/props.
    """
    headers = {"Accept": "application/json"}
    if app_token:
        headers["X-App-Token"] = app_token

    params = {"$limit": limit, "$order": ":id"}
    if where_clause:
        params["$where"] = where_clause

    try:
        url = f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        rows = r.json()

        features = []
        skipped  = 0
        for row in rows:
            # Try to get lat/lng — could be in dedicated columns or in a location object
            lat, lng = None, None
            if lat_col in row and lng_col in row:
                try:
                    lat = float(row[lat_col])
                    lng = float(row[lng_col])
                except (TypeError, ValueError):
                    pass
            # Fallback: look for a .location dict
            if lat is None:
                for key in ("location", "geocoded_column", "the_geom"):
                    loc = row.get(key, {})
                    if isinstance(loc, dict):
                        try:
                            lat = float(loc.get("latitude") or loc.get("coordinates", [None, None])[1])
                            lng = float(loc.get("longitude") or loc.get("coordinates", [None, None])[0])
                            break
                        except (TypeError, ValueError, IndexError):
                            pass
            if lat is None or lng is None or lat == 0 or lng == 0:
                skipped += 1
                continue

            label = str(row.get(label_col, "")) if label_col else ""
            features.append({"lat": lat, "lng": lng, "label": label, "props": row})

        return {
            "features":    features,
            "total_rows":  len(rows),
            "skipped":     skipped,
            "dataset_id":  dataset_id,
            "error":       None,
        }
    except Exception as e:
        return {"features": [], "total_rows": 0, "skipped": 0, "dataset_id": dataset_id, "error": str(e)}

def socrata_popup_html(feature: dict, label_col: str, dataset_name: str, color: str) -> str:
    """Build a Folium popup for a Socrata data point."""
    props = feature["props"]
    label = feature["label"] or dataset_name

    # Top fields to show (skip long/system fields)
    skip_keys = {"latitude", "longitude", "location", "the_geom", "geocoded_column",
                 ":id", "@id", "x_coordinate_state_plane", "y_coordinate_state_plane"}
    show_props = {k: v for k, v in props.items()
                  if k not in skip_keys and not k.startswith(":") and v not in (None, "", [])}
    # Limit to 8 most informative fields
    show_props = dict(list(show_props.items())[:8])

    rows_html = "".join(
        f'<div style="margin-bottom:2px"><span style="color:#556">{k}:</span> '
        f'<span style="color:#aab">{str(v)[:80]}</span></div>'
        for k, v in show_props.items()
    )
    return (f'<div style="font-family:monospace;font-size:10px;max-width:250px">'
            f'<div style="font-weight:700;color:{color};margin-bottom:5px;font-size:11px">{label[:60]}</div>'
            f'{rows_html}'
            f'<div style="color:#446;font-size:9px;margin-top:4px;border-top:1px solid #1e2a40;padding-top:3px">'
            f'NYC Open Data · {dataset_name}</div>'
            f'</div>')

# ═══════════════════════════════════════════════════════════════════════════════
# ESRI FEATURE SERVICE → MAP HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_esri_feature_layer(service_url: str, max_features: int = 500) -> dict:
    """
    Query an ArcGIS Feature Service REST endpoint and return GeoJSON-like features.
    Works with any public ArcGIS Feature Service — no auth required.
    Appends /query if not already present.
    """
    # Normalize URL — ensure we hit the /query endpoint
    base = service_url.rstrip("/")
    if not base.endswith("/query"):
        # If it's an item URL (arcgis.com/home/item.html?id=...), can't query directly
        if "arcgis.com/home/item" in base:
            return {"features": [], "error": "Item page URL — use the Service URL (REST endpoint), not the item page URL"}
        query_url = base + "/query"
    else:
        query_url = base

    params = {
        "where":        "1=1",
        "outFields":    "*",
        "returnGeometry": "true",
        "f":            "geojson",
        "resultRecordCount": max_features,
    }
    try:
        r = requests.get(query_url, params=params, timeout=15,
                         headers={"User-Agent": "EMBER/1.0"})
        r.raise_for_status()
        geojson = r.json()

        if "error" in geojson:
            return {"features": [], "error": geojson["error"].get("message", "ArcGIS error")}

        features = []
        for feat in geojson.get("features", []):
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            gtype = geom.get("type", "")

            if gtype == "Point":
                coords = geom.get("coordinates", [])
                if len(coords) >= 2:
                    features.append({"type": "point", "lat": coords[1], "lng": coords[0], "props": props})
            elif gtype in ("Polygon", "MultiPolygon"):
                features.append({"type": "polygon", "geometry": geom, "props": props})
            elif gtype in ("LineString", "MultiLineString"):
                features.append({"type": "line", "geometry": geom, "props": props})

        return {"features": features, "total": len(features), "error": None}
    except Exception as e:
        return {"features": [], "total": 0, "error": str(e)}

def esri_feature_popup_html(feature: dict, layer_name: str, color: str) -> str:
    """Build a Folium popup for an ESRI feature."""
    props = feature["props"]
    skip  = {"OBJECTID", "ObjectID", "FID", "Shape_Area", "Shape_Length", "GlobalID"}
    show  = {k: v for k, v in props.items() if k not in skip and v not in (None, "")}
    rows  = "".join(
        f'<div><span style="color:#556">{k}:</span> <span style="color:#aab">{str(v)[:80]}</span></div>'
        for k, v in list(show.items())[:8]
    )
    name = next((str(v) for k, v in show.items() if any(x in k.upper() for x in ("NAME","TITLE","LABEL","DESC","SITE"))), layer_name)
    return (f'<div style="font-family:monospace;font-size:10px;max-width:240px">'
            f'<div style="font-weight:700;color:{color};margin-bottom:4px;font-size:11px">{name[:60]}</div>'
            f'{rows}'
            f'<div style="color:#446;font-size:9px;margin-top:4px;border-top:1px solid #1e2a40;padding-top:3px">'
            f'ESRI Feature Layer · {layer_name}</div>'
            f'</div>')

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE INIT
# ═══════════════════════════════════════════════════════════════════════════════

for k, v in [
    ("messages",     [{"role": "assistant", "content":
                        f"EMBER initialized — Emergency Management Body of Evidence & Resources\n"
                        f"Backend: Ollama Cloud · {OLLAMA_MODEL}\nJurisdiction: New York City\n\n"
                        f"Knowledge base loaded · NOAA feeds auto-fetching · Radar & wind on by default\n"
                        f"Tidal gauges: fetching live CO-OPS water levels for all NY stations\n"
                        f"Click a map marker or type a query to begin."}]),
    ("files",        []),
    ("api_results",  []),
    ("esri_items",   []),
    ("esri_results", []),
    ("esri_total",   0),
    ("esri_searched",False),
    ("noaa_results", {}),
    ("noaa_items",   []),
    ("show_radar",   True),
    ("show_wind",    True),
    ("gauge_data",   {}),       # live tidal gauge readings keyed by station_id
    ("gauge_stations", []),     # CO-OPS station list for NY (dynamic)
    ("gauge_fetched_at", _dt.datetime.min), # last fetch timestamp
    ("map_layers",  []),        # user-added map layers: [{id, name, type, color, icon, features, ...}]
    ("nyc_token",   ""),        # NYC Open Data app token (user-provided)
]:
    if k not in st.session_state:
        st.session_state[k] = v

# Fetch wind obs on first load
if "wind_obs" not in st.session_state:
    st.session_state.wind_obs            = fetch_wind_obs()
    st.session_state.wind_obs_fetched_at = _dt.datetime.now()

# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL AUTO-REFRESH (60s tick)
# ═══════════════════════════════════════════════════════════════════════════════

st_autorefresh(interval=60_000, key="global_autorefresh")

# Refresh wind obs if stale (>5 min)
_wind_fetched = st.session_state.get("wind_obs_fetched_at") or _dt.datetime.min
_wind_age = (_dt.datetime.now() - _wind_fetched).total_seconds()
if _wind_age > 300:
    st.session_state.wind_obs            = fetch_wind_obs()
    st.session_state.wind_obs_fetched_at = _dt.datetime.now()

# Refresh tidal gauges if stale (>6 min — CO-OPS updates every 6 min)
_gauge_fetched = st.session_state.get("gauge_fetched_at") or _dt.datetime.min
_gauge_age = (_dt.datetime.now() - _gauge_fetched).total_seconds()
if _gauge_age > 360 or not st.session_state.gauge_data:
    # Fetch station list once
    if not st.session_state.gauge_stations:
        st.session_state.gauge_stations = fetch_station_list("NY")
    # Fetch live data for all key NYC stations (+ any others in session)
    station_ids = list(FLOOD_THRESHOLDS.keys())
    st.session_state.gauge_data       = fetch_all_ny_gauges(station_ids)
    st.session_state.gauge_fetched_at = _dt.datetime.now()

# Seed map-connected NOAA endpoints and refresh stale ones
auto_fetch_map_endpoints()
refresh_stale_endpoints()

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🚨 EMBER")
    st.caption(f"Ollama Cloud · {OLLAMA_MODEL}")

    status = ping_ollama()
    if status == "no-key":
        st.markdown('<span class="pill p-yellow">⚠ NO API KEY</span>', unsafe_allow_html=True)
        st.info("Set OLLAMA_API_KEY. Get one at ollama.com/settings/keys")
    elif status is True:
        st.markdown('<span class="pill p-green">● OLLAMA CLOUD OK</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="pill p-red">● CLOUD UNREACHABLE</span>', unsafe_allow_html=True)

    st.divider()
    st.markdown("**KNOWLEDGE BASE**")
    active_kb = [k for k, m in NYC_KB.items() if st.checkbox(m["label"], value=True, key=f"kb_{k}")]

    st.divider()
    st.markdown("**MAP LAYERS**")
    layer_opts = {"hospitals": "🏥 Trauma Centers", "shelters": "🏫 Evac Shelters",
                  "gauges": "📡 Stream Gauges", "eoc": "🏛 EOC / Command", "floodRisk": "💧 Flood Risk Areas"}
    active_layers = [k for k, label in layer_opts.items() if st.checkbox(label, value=True, key=f"map_{k}")]

    st.markdown("**WEATHER OVERLAYS**")
    show_radar = st.checkbox("📡 NEXRAD Radar (auto-refresh)", key="show_radar",
                             help="Iowa State MESONET — tiles refresh every 5min automatically")
    show_wind  = st.checkbox("💨 Wind Observations (auto-refresh)", key="show_wind",
                             help="Live NWS surface obs — refreshes every 5min automatically")

    st.divider()
    st.markdown("**TIDAL GAUGES**")
    g_fetched = st.session_state.get("gauge_fetched_at")
    g_age_s   = int((_dt.datetime.now() - g_fetched).total_seconds()) if g_fetched else None
    g_age_str = f"last fetched {g_age_s//60}m ago" if g_age_s else "not yet fetched"
    st.caption(f"CO-OPS · auto-refresh 6min · {g_age_str}")
    if st.button("↺ Refresh Gauges Now", use_container_width=True):
        with st.spinner("Fetching live gauge data…"):
            st.session_state.gauge_data       = fetch_all_ny_gauges(list(FLOOD_THRESHOLDS.keys()))
            st.session_state.gauge_fetched_at = _dt.datetime.now()
        st.rerun()
    # Show current flood status for each gauge
    for sid, gd in st.session_state.gauge_data.items():
        ld = gd.get("level")
        if not ld: continue
        color = ld.get("color","#4ade80")
        st.markdown(
            f'<span class="pill" style="background:{color}18;color:{color};border:1px solid {color}33">'
            f'● {ld.get("station_name","?")[:18]}: {ld.get("level_ft","?")}ft — {ld.get("status","?")}'
            f'</span>',
            unsafe_allow_html=True
        )

    st.divider()
    st.markdown("**LIVE FEEDS** (sidebar)")
    if st.button("↺ Fetch All Feeds", use_container_width=True):
        with st.spinner("Fetching…"):
            st.session_state.api_results = [fetch_live(ep) for ep in LIVE_ENDPOINTS]
    for r in st.session_state.api_results:
        cls = "p-green" if r["success"] else "p-red"
        st.markdown(f'<span class="pill {cls}">{"●" if r["success"] else "○"} {r["name"]}</span>',
                    unsafe_allow_html=True)

    st.divider()
    st.markdown("**INGEST DOCUMENTS**")
    uploads = st.file_uploader("SOPs, GeoJSON, CSV, plans", accept_multiple_files=True,
                               type=["txt", "csv", "json", "geojson", "md"])
    if uploads:
        existing = {f["name"] for f in st.session_state.files}
        for up in uploads:
            if up.name not in existing:
                st.session_state.files.append({
                    "name": up.name,
                    "content": StringIO(up.read().decode("utf-8", errors="replace")).read()
                })
    for f in st.session_state.files:
        st.markdown(f'<span class="pill p-blue">📄 {f["name"]}</span>', unsafe_allow_html=True)
    if st.session_state.files and st.button("Clear Documents"):
        st.session_state.files = []

    st.divider()
    if st.button("Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN MAP
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("### 🗺️ NYC Operational Map")

# ── Tidal gauge live status strip ──────────────────────────────────────────────
gauge_data = st.session_state.gauge_data
if gauge_data:
    gauge_fetched = st.session_state.get("gauge_fetched_at")
    g_age_s = int((_dt.datetime.now() - gauge_fetched).total_seconds()) if gauge_fetched else None
    g_age_str = f"{g_age_s//60}m{g_age_s%60:02d}s ago" if g_age_s is not None else "?"
    st.markdown(
        f"**🌊 Live Tidal Gauges (CO-OPS)** "
        f"<span style='font-size:11px;color:#446'>· {g_age_str} · auto-refreshes every 6min</span>",
        unsafe_allow_html=True
    )
    gcols = st.columns(min(len(gauge_data), 6))
    for i, (sid, gd) in enumerate(gauge_data.items()):
        ld = gd.get("level")
        if not ld: continue
        with gcols[i % 6]:
            color  = ld.get("color", "#4ade80")
            status = ld.get("status", "NORMAL")
            lft    = ld.get("level_ft", 0)
            name   = ld.get("station_name", sid)
            nh     = gd.get("next_high")
            st.markdown(
                f'<div style="background:#0d1520;border:1px solid {color}44;border-radius:6px;'
                f'padding:8px 10px;font-family:monospace">'
                f'<div style="font-size:9px;color:#556;margin-bottom:2px">{name}</div>'
                f'<div style="font-size:18px;font-weight:700;color:{color}">{lft:.2f}ft</div>'
                f'<div style="font-size:9px;color:{color}">{status}</div>'
                f'<div style="font-size:8px;color:#446;margin-top:3px">{ld.get("trend_str","")}</div>'
                f'{f"""<div style="font-size:8px;color:#60a5fa;margin-top:2px">▲ {nh["level_ft"]:.2f}ft @ {nh["time"][-5:]}</div>""" if nh else ""}'
                f'</div>',
                unsafe_allow_html=True
            )

wind_obs = st.session_state.get("wind_obs", []) if show_wind else []

if show_wind and wind_obs:
    wind_fetched = st.session_state.get("wind_obs_fetched_at")
    age_s   = int((_dt.datetime.now() - wind_fetched).total_seconds()) if wind_fetched else None
    age_str = f"{age_s//60}m{age_s%60:02d}s ago" if age_s is not None else "?"
    st.markdown(
        f"**💨 Wind Observations** "
        f"<span style='font-size:11px;color:#446'>· {age_str} · auto-refreshes every 5min</span>",
        unsafe_allow_html=True
    )
    wcols = st.columns(min(len(wind_obs), 4))
    for i, o in enumerate(wind_obs):
        with wcols[i % 4]:
            spd  = int(o["speed_mph"]) if o.get("speed_mph") is not None else None
            gust = int(o["gust_mph"])  if o.get("gust_mph")  is not None else None
            st.metric(
                label=f"{o['id']} — {o['name']}",
                value=f"{spd}mph" + (f" g{gust}" if gust else "") if spd is not None else "—",
                delta=f"{int(o['dir_deg'])}° · {o.get('desc','')[:20]}" if o.get("dir_deg") is not None else None,
                delta_color="off"
            )

if st.session_state.map_layers:
    n_layers = len(st.session_state.map_layers)
    st.markdown(f"**🗂 Active User Layers ({n_layers})**", unsafe_allow_html=True)
    layer_cols = st.columns(min(n_layers, 4))
    for i, layer in enumerate(st.session_state.map_layers):
        with layer_cols[i % 4]:
            color = layer.get("color","#60a5fa")
            st.markdown(
                f'<div style="background:{color}12;border:1px solid {color}44;border-radius:5px;'
                f'padding:5px 8px;font-family:monospace;font-size:10px">'
                f'<span style="color:{color};font-weight:700">{layer["icon"]} {layer["name"][:28]}</span><br>'
                f'<span style="color:#446">{layer["count"]} features · {layer["type"].upper()}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

if show_radar:
    next_refresh = 300 - (int(_time.time()) % 300)
    st.caption(f"📡 NEXRAD radar active — next tile refresh in ~{next_refresh}s · Iowa State MESONET")



live_rdgs = {
    **build_live_readings(st.session_state.api_results),
    **extract_map_readings_from_noaa(),
}

if "__flood_alert__" in live_rdgs:
    a = live_rdgs["__flood_alert__"]
    st.error(f"⚠ **{a['event']}** ({a['severity']}) — {a['headline']}")

map_data = st_folium(
    build_map(active_layers, show_radar=show_radar, show_wind=show_wind,
              wind_obs=wind_obs, live_readings=live_rdgs,
              gauge_data=st.session_state.gauge_data,
              map_layers=st.session_state.map_layers),
    width="100%", height=380, returned_objects=["last_object_clicked_popup"]
)

if map_data and map_data.get("last_object_clicked_popup"):
    m2 = re.search(r'<b[^>]*>([^<]+)</b>', map_data["last_object_clicked_popup"] or "")
    if m2 and "pending_query" not in st.session_state:
        st.session_state.pending_query = f"Emergency considerations and risk profile for: {m2.group(1)}"

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab_chat, tab_noaa, tab_nyc, tab_esri = st.tabs([
    "💬 EMBER Chat",
    "📡 NOAA Data Stack",
    "🗽 NYC Open Data",
    "⊕ ESRI / Living Atlas",
])

# ── NOAA Tab ──────────────────────────────────────────────────────────────────
with tab_noaa:
    st.markdown("#### NOAA Open Data Stack")
    st.caption("Auto-fetches map-connected endpoints · All fetched data auto-added to KB · No API key required")

    n_fetched = len(st.session_state.noaa_results)
    n_live    = sum(1 for r in st.session_state.noaa_results.values() if r.get("success"))
    n_kb      = len(st.session_state.noaa_items)
    n_map     = sum(1 for x in st.session_state.noaa_items if x.get("map_connected"))

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Fetched", n_fetched)
    s2.metric("Live / OK", n_live)
    s3.metric("In KB", n_kb)
    s4.metric("Map-connected", n_map)
    st.divider()

    nc1, nc2 = st.columns([3, 2])
    with nc1: noaa_search = st.text_input("Search endpoints…", placeholder="flood, tide, temperature, alerts…", key="noaa_search")
    with nc2: noaa_cat    = st.selectbox("Category", ["All","NWS","CO-OPS","NCEI","SPC","SWPC"], key="noaa_cat")

    filtered_eps = [ep for ep in NOAA_ENDPOINTS if
        (noaa_cat == "All" or ep["cat"] == noaa_cat) and
        (not noaa_search or
         noaa_search.lower() in ep["name"].lower() or
         noaa_search.lower() in ep["desc"].lower() or
         any(noaa_search.lower() in t for t in ep.get("tags", [])))]

    for ep in filtered_eps:
        result   = st.session_state.noaa_results.get(ep["id"])
        in_kb    = any(x["item_id"] == ep["id"] for x in st.session_state.noaa_items)
        is_map   = ep["id"] in MAP_CONNECTED_IDS
        interval = REFRESH_INTERVALS.get(ep["id"], 0)
        ts       = result.get("fetched_at", "—") if result else "—"

        map_badge = '<span class="pill" style="background:#34d39918;color:#34d399;border:1px solid #34d39933">🗺 MAP</span>' if is_map else ""
        kb_badge  = '<span class="pill p-green">✓ KB</span>' if in_kb else ""
        ok_str    = ("● OK" if result and result.get("success") else "○ ERR" if result else "○")
        ok_cls    = "p-green" if result and result.get("success") else "p-red"
        ref_txt   = f"↺ {interval//60}min" if interval else ""

        st.markdown(f"""<div class="esri-card" style="border-left:3px solid {ep['color']}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start">
              <div>
                <div style="font-weight:700;color:#dde;margin-bottom:2px">{ep['icon']} {ep['name']}</div>
                <div style="font-size:10px;color:#556;margin-bottom:4px">{ep['desc']}</div>
                <div>{map_badge}{kb_badge}
                  {"".join(f'<span class="pill" style="background:{ep["color"]}18;color:{ep["color"]};border:1px solid {ep["color"]}33">{t}</span>' for t in ep.get("tags",[])[:3])}
                </div>
              </div>
              <div style="font-size:9px;color:#334;text-align:right;white-space:nowrap">
                <span class="pill {ok_cls}">{ok_str}</span><br>
                {f"@ {ts}" if ts != "—" else ""}<br>{ref_txt}
              </div>
            </div>
        </div>""", unsafe_allow_html=True)

        b1, b2, b3 = st.columns([1, 1, 2])
        with b1:
            if st.button("▶ Fetch now", key=f"nfetch_{ep['id']}", use_container_width=True):
                with st.spinner("Fetching…"):
                    new_result = fetch_noaa_ep(ep)
                st.session_state.noaa_results[ep["id"]] = new_result
                if new_result["success"]:
                    upsert_noaa_kb(ep, new_result)
                st.rerun()
        with b2:
            st.link_button("↗ URL", resolve_url(ep))
        with b3:
            if result and result.get("success"):
                with st.expander("Preview"):
                    st.code(summarize_noaa(result), language=None)
        st.markdown("---")

    if st.session_state.noaa_items:
        st.markdown(f"**{n_kb} NOAA feed(s) in KB** — auto-updated on refresh")
        for i, ni in enumerate(st.session_state.noaa_items):
            c1, c2 = st.columns([5, 1])
            map_tag = " 🗺" if ni.get("map_connected") else ""
            with c1:
                st.markdown(f'<span class="pill p-green">▶ {ni["name"][:50]}{map_tag} · {ni.get("fetched_at","?")}</span>',
                            unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"rm_noaa_{i}"):
                    st.session_state.noaa_items.pop(i)
                    st.rerun()

# ── NYC Open Data Tab ─────────────────────────────────────────────────────────
with tab_nyc:
    st.markdown("#### 🗽 NYC Open Data")
    st.caption("Powered by Socrata SODA API · data.cityofnewyork.us · App token recommended (free at opendata.cityofnewyork.us)")

    # ── Token input ────────────────────────────────────────────────────────────
    with st.expander("🔑 NYC Open Data App Token (optional but recommended)", expanded=not st.session_state.nyc_token):
        st.markdown(
            "An app token removes rate limits. Get one free at "
            "[opendata.cityofnewyork.us](https://opendata.cityofnewyork.us/) → Sign In → Manage → App Tokens"
        )
        token_input = st.text_input("Paste your app token", value=st.session_state.nyc_token,
                                     type="password", key="nyc_token_input",
                                     placeholder="e.g. aBcDeFgHiJkLmNoP123456789")
        if st.button("Save Token", key="save_nyc_token"):
            st.session_state.nyc_token = token_input
            st.success("Token saved for this session.")

    nyc_token = st.session_state.nyc_token

    st.divider()

    # ── Preset emergency datasets ──────────────────────────────────────────────
    st.markdown("**Emergency-Relevant Datasets (one-click)**")
    st.caption("Click ▶ to fetch and add directly to the map. Data is sampled (up to 500 records).")

    preset_cols = st.columns(3)
    for pi, preset in enumerate(NYC_OPEN_DATA_PRESETS):
        with preset_cols[pi % 3]:
            already_on_map = any(l["id"] == f"nyc_{preset['id']}" for l in st.session_state.map_layers)
            st.markdown(
                f'<div class="esri-card" style="border-left:3px solid {preset["color"]};min-height:90px">'
                f'<div style="font-weight:700;color:{preset["color"]};margin-bottom:2px">{preset["icon"]} {preset["name"]}</div>'
                f'<div style="font-size:9px;color:#556;margin-bottom:4px">{preset["agency"]} · {preset["id"]}</div>'
                f'<div style="font-size:10px;color:#778">{preset["desc"][:80]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if already_on_map:
                if st.button(f"✓ On Map", key=f"preset_rm_{preset['id']}", use_container_width=True):
                    st.session_state.map_layers = [l for l in st.session_state.map_layers if l["id"] != f"nyc_{preset['id']}"]
                    st.rerun()
            else:
                if st.button(f"▶ Add to Map", key=f"preset_add_{preset['id']}", use_container_width=True):
                    with st.spinner(f"Fetching {preset['name']}…"):
                        result = fetch_socrata_dataset(
                            preset["id"], nyc_token,
                            lat_col=preset["lat_col"], lng_col=preset["lng_col"],
                            label_col=preset["label_col"], limit=500
                        )
                    if result["error"]:
                        st.error(f"Error: {result['error']}")
                    elif not result["features"]:
                        st.warning(f"No mappable records returned (dataset may lack lat/lng in recent records)")
                    else:
                        color   = preset["color"]
                        def make_popup_fn(ds_name, col, clr):
                            def fn(feat):
                                return socrata_popup_html(feat, col, ds_name, clr)
                            return fn
                        st.session_state.map_layers.append({
                            "id":       f"nyc_{preset['id']}",
                            "name":     preset["name"],
                            "type":     "socrata",
                            "color":    color,
                            "icon":     preset["icon"],
                            "features": result["features"],
                            "visible":  True,
                            "popup_fn": make_popup_fn(preset["name"], preset["label_col"], color),
                            "count":    len(result["features"]),
                            "source":   f"NYC Open Data · {preset['id']}",
                        })
                        st.success(f"✓ Added {len(result['features'])} features to map")
                        st.rerun()

    st.divider()

    # ── Custom dataset search ──────────────────────────────────────────────────
    st.markdown("**Search NYC Open Data Catalog**")
    sc1, sc2 = st.columns([4, 1])
    with sc1: nyc_query  = st.text_input("Search datasets…", placeholder="flood zones, shelters, hospitals, 311, FDNY…", key="nyc_query")
    with sc2: do_nyc_search = st.button("🔍 Search", use_container_width=True, key="nyc_search_btn")

    if do_nyc_search and nyc_query:
        with st.spinner("Searching NYC Open Data catalog…"):
            nyc_results = search_nyc_open_data(nyc_query, nyc_token, limit=15)
        st.session_state["nyc_search_results"] = nyc_results
        st.session_state["nyc_search_query"]   = nyc_query

    if st.session_state.get("nyc_search_results"):
        results  = st.session_state["nyc_search_results"]
        st.caption(f"{len(results)} datasets found for '{st.session_state.get('nyc_search_query','')}'")

        for ds in results:
            cols_str = ", ".join(ds["columns"][:6]) if ds["columns"] else "—"
            has_geo  = any(c.lower() in ("latitude","longitude","the_geom","location","geocoded_column")
                          for c in (ds["columns"] or []))
            geo_badge = '<span class="pill p-green">📍 mappable</span>' if has_geo else '<span class="pill p-yellow">⚠ no geometry</span>'

            st.markdown(f"""<div class="esri-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start">
                  <div>
                    <div style="font-weight:700;color:#dde;margin-bottom:2px">{ds['name']}</div>
                    <div style="font-size:9px;color:#556;margin-bottom:4px">
                      {ds['agency']} · {ds['category']} · updated {ds['updated']} · ID: <code>{ds['id']}</code>
                    </div>
                    <div style="font-size:10px;color:#778;margin-bottom:4px">{ds['description'][:120]}</div>
                    <div style="font-size:9px;color:#446">Columns: {cols_str}</div>
                  </div>
                  <div>{geo_badge}</div>
                </div>
            </div>""", unsafe_allow_html=True)

            if has_geo:
                ncola, ncolb, ncolc = st.columns([2, 2, 2])
                with ncola:
                    lat_guess  = next((c for c in (ds["columns"] or []) if "lat" in c.lower()), "latitude")
                    lng_guess  = next((c for c in (ds["columns"] or []) if "lon" in c.lower() or "lng" in c.lower()), "longitude")
                    label_guess= next((c for c in (ds["columns"] or []) if any(x in c.lower() for x in ("name","type","desc","title"))), "")
                    lat_col_in = st.text_input("Lat column", value=lat_guess, key=f"lat_{ds['id']}")
                with ncolb:
                    lng_col_in = st.text_input("Lng column", value=lng_guess, key=f"lng_{ds['id']}")
                with ncolc:
                    lbl_col_in = st.text_input("Label column", value=label_guess, key=f"lbl_{ds['id']}")

                on_map = any(l["id"] == f"nyc_{ds['id']}" for l in st.session_state.map_layers)
                if on_map:
                    if st.button(f"✕ Remove from Map", key=f"rm_{ds['id']}", use_container_width=True):
                        st.session_state.map_layers = [l for l in st.session_state.map_layers if l["id"] != f"nyc_{ds['id']}"]
                        st.rerun()
                else:
                    if st.button(f"▶ Add '{ds['name'][:30]}' to Map", key=f"add_{ds['id']}", use_container_width=True):
                        with st.spinner(f"Fetching {ds['name']}…"):
                            result = fetch_socrata_dataset(
                                ds["id"], nyc_token,
                                lat_col=lat_col_in, lng_col=lng_col_in,
                                label_col=lbl_col_in, limit=500
                            )
                        if result["error"]:
                            st.error(f"Error: {result['error']}")
                        elif not result["features"]:
                            st.warning("No mappable records — check lat/lng column names")
                        else:
                            color   = "#60a5fa"
                            def make_popup_fn2(dname, lcol, clr):
                                def fn(feat): return socrata_popup_html(feat, lcol, dname, clr)
                                return fn
                            st.session_state.map_layers.append({
                                "id":       f"nyc_{ds['id']}",
                                "name":     ds["name"],
                                "type":     "socrata",
                                "color":    color,
                                "icon":     "🗽",
                                "features": result["features"],
                                "visible":  True,
                                "popup_fn": make_popup_fn2(ds["name"], lbl_col_in, color),
                                "count":    len(result["features"]),
                                "source":   f"NYC Open Data · {ds['id']}",
                            })
                            st.success(f"✓ Added {len(result['features'])} features to map")
                            st.rerun()
            else:
                if ds.get("permalink"):
                    st.link_button("↗ View on NYC Open Data", ds["permalink"])

            st.markdown("---")

    st.divider()

    # ── Custom endpoint ────────────────────────────────────────────────────────
    st.markdown("**Custom Dataset URL**")
    st.caption("Paste any NYC Open Data resource URL or dataset ID to fetch and map it")
    ccol1, ccol2 = st.columns([3, 1])
    with ccol1:
        custom_id = st.text_input("Dataset ID or URL", placeholder="e.g. fhrw-4uyv or https://data.cityofnewyork.us/resource/fhrw-4uyv.json", key="nyc_custom_id")
    with ccol2:
        custom_lat = st.text_input("Lat col", value="latitude", key="nyc_custom_lat")

    ccol3, ccol4, ccol5 = st.columns([1, 1, 2])
    with ccol3: custom_lng   = st.text_input("Lng col", value="longitude", key="nyc_custom_lng")
    with ccol4: custom_label = st.text_input("Label col", value="", key="nyc_custom_label")
    with ccol5:
        custom_where = st.text_input("WHERE filter (optional SoQL)", placeholder="status='Active'", key="nyc_custom_where")

    if st.button("▶ Fetch & Add to Map", key="nyc_custom_fetch", use_container_width=True) and custom_id:
        # Extract ID from URL if needed
        ds_id = custom_id.strip()
        if "/" in ds_id:
            ds_id = ds_id.rstrip("/").split("/")[-1].replace(".json","").replace(".geojson","")
        with st.spinner("Fetching dataset…"):
            result = fetch_socrata_dataset(
                ds_id, nyc_token,
                lat_col=custom_lat, lng_col=custom_lng,
                label_col=custom_label, where_clause=custom_where, limit=500
            )
        if result["error"]:
            st.error(f"Error: {result['error']}")
        elif not result["features"]:
            st.warning(f"No mappable records returned. Fetched {result['total_rows']} rows but {result['skipped']} lacked valid lat/lng.")
        else:
            color = "#f472b6"
            def make_custom_popup(lcol, clr):
                def fn(feat): return socrata_popup_html(feat, lcol, ds_id, clr)
                return fn
            st.session_state.map_layers.append({
                "id":       f"nyc_{ds_id}",
                "name":     f"NYC OD: {ds_id}",
                "type":     "socrata",
                "color":    color,
                "icon":     "🗽",
                "features": result["features"],
                "visible":  True,
                "popup_fn": make_custom_popup(custom_label, color),
                "count":    len(result["features"]),
                "source":   f"NYC Open Data · {ds_id}",
            })
            st.success(f"✓ Added {len(result['features'])} features to map")
            st.rerun()

    # ── Active map layers ──────────────────────────────────────────────────────
    nyc_active = [l for l in st.session_state.map_layers if l["type"] == "socrata"]
    if nyc_active:
        st.divider()
        st.markdown(f"**{len(nyc_active)} NYC Open Data layer(s) on map:**")
        for i, layer in enumerate(nyc_active):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f'<span class="pill p-blue">{layer["icon"]} {layer["name"][:50]} · {layer["count"]} features</span>',
                    unsafe_allow_html=True
                )
            with c2:
                if st.button("✕", key=f"rm_nyc_layer_{i}"):
                    st.session_state.map_layers = [l for l in st.session_state.map_layers if l["id"] != layer["id"]]
                    st.rerun()

# ── ESRI Tab ───────────────────────────────────────────────────────────────────
with tab_esri:
    st.markdown("#### Search ArcGIS Online & Living Atlas")
    st.caption("Public layers, no authentication required. Inject metadata into the EMBER knowledge base.")

    col1, col2, col3 = st.columns([3, 2, 2])
    with col1: esri_query        = st.text_input("Search layers, maps, services…", placeholder="e.g. NYC flood zones")
    with col2: esri_filter_label = st.selectbox("Filter", list(LIVING_ATLAS_FILTERS.keys()))
    with col3: esri_type         = st.selectbox("Item Type", ITEM_TYPES)
    esri_filter = LIVING_ATLAS_FILTERS[esri_filter_label]

    col_s, col_p = st.columns([2, 3])
    with col_s: do_search = st.button("🔍 Search ArcGIS Online", use_container_width=True)
    with col_p: esri_page = st.number_input("Page", min_value=1, value=1, step=1, label_visibility="collapsed")

    if do_search and esri_query:
        with st.spinner("Searching ArcGIS Online…"):
            results, total, err = search_agol(esri_query, esri_filter, esri_type, num=8, start=(esri_page-1)*8+1)
            st.session_state.esri_results  = results
            st.session_state.esri_total    = total
            st.session_state.esri_searched = True
            if err: st.error(f"Search error: {err}")

    if st.session_state.esri_searched:
        results      = st.session_state.esri_results
        total        = st.session_state.esri_total
        injected_ids = {i["item_id"] for i in st.session_state.esri_items}
        if not results:
            st.info("No results. Try broader search terms.")
        else:
            st.caption(f"{total:,} results found")
            for item in results:
                is_la    = "esri" in (item.get("owner", "")).lower()
                tags     = ", ".join((item.get("tags") or [])[:6])
                updated  = str(item.get("modified", ""))[:10]
                injected = item["id"] in injected_ids
                st.markdown(f"""<div class="esri-card">
                    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px">
                      <span class="pill p-blue">{item.get('type','')}</span>
                      {"<span class='pill p-purple'>Living Atlas</span>" if is_la else ""}
                      {"<span class='pill p-green'>✓ In KB</span>" if injected else ""}
                    </div>
                    <div style="font-weight:700;color:#dde;margin-bottom:4px">{item.get('title','')}</div>
                    <div style="font-size:10px;color:#555;margin-bottom:4px">{item.get('owner','')} · {updated}</div>
                    <div style="font-size:11px;color:#778;margin-bottom:6px">{(item.get('snippet') or '')[:160]}</div>
                    {f'<div style="font-size:9px;color:#3a3e58">{tags}</div>' if tags else ''}
                </div>""", unsafe_allow_html=True)
                ca, cb, cc, cd = st.columns([2, 2, 1, 1])
                with ca:
                    if st.button("⊕ Inspect Metadata", key=f"inspect_{item['id']}", use_container_width=True):
                        with st.spinner("Fetching metadata…"):
                            full_item, data, err = fetch_item_metadata(item["id"])
                        if err:
                            st.error(f"Error: {err}")
                        else:
                            with st.expander("📋 Full Metadata", expanded=True):
                                st.markdown(f"**ID:** `{full_item.get('id','')}` | **Type:** {full_item.get('type','')} | **Owner:** {full_item.get('owner','')}")
                                if full_item.get("url"): st.markdown(f"**Service URL:** [{full_item['url']}]({full_item['url']})")
                                st.markdown(f"**Tags:** {', '.join(full_item.get('tags',[]))}")
                                desc = re.sub(r'<[^>]+>', '', full_item.get('description', ''))
                                if desc: st.markdown(f"**Description:** {desc[:800]}")
                                if data:
                                    if "layers" in data: st.markdown("**Layers:** " + ", ".join(f"{l.get('id')}:{l.get('name','')}" for l in data["layers"]))
                                    if "operationalLayers" in data: st.markdown("**Operational Layers:** " + ", ".join(l.get("title","?") for l in data["operationalLayers"]))
                                    st.json(data, expanded=False)
                                st.json(full_item, expanded=False)
                with cb:
                    if not injected:
                        if st.button("+ Add to KB", key=f"inject_{item['id']}", use_container_width=True):
                            full_item, data, _ = fetch_item_metadata(item["id"])
                            ctx_text = format_item_for_context(full_item or item, data)
                            st.session_state.esri_items.append({"name": f"ESRI: {item.get('title','')}", "item_id": item["id"], "content": ctx_text})
                            st.session_state.pending_query = f"I just added '{item.get('title','')}' to the KB. Summarize what it contains and how it supports NYC emergency management."
                            st.rerun()
                    else:
                        st.button("✓ In KB", key=f"injected_{item['id']}", disabled=True, use_container_width=True)
                with cc: st.link_button("↗ AGOL", f"https://www.arcgis.com/home/item.html?id={item['id']}")
                with cd:
                    if item.get("url"): st.link_button("↗ Service", item["url"])

                # Add to Map button — only for Feature Layers / Map Services with a URL
                if item.get("url") and item.get("type") in ("Feature Layer", "Feature Service", "Map Service"):
                    esri_on_map = any(l["id"] == f"esri_{item['id']}" for l in st.session_state.map_layers)
                    if esri_on_map:
                        if st.button(f"✕ Remove from Map", key=f"esri_rm_map_{item['id']}", use_container_width=True):
                            st.session_state.map_layers = [l for l in st.session_state.map_layers if l["id"] != f"esri_{item['id']}"]
                            st.rerun()
                    else:
                        if st.button(f"🗺 Add to Map", key=f"esri_map_{item['id']}", use_container_width=True):
                            service_url = item["url"]
                            # Append /0 if it's a service root, not a layer
                            if "/FeatureServer" in service_url and not service_url.split("/FeatureServer")[-1].strip("/").isdigit():
                                service_url = service_url.rstrip("/") + "/0"
                            with st.spinner(f"Fetching {item.get('title','')} layer…"):
                                result = fetch_esri_feature_layer(service_url, max_features=500)
                            if result["error"]:
                                st.error(f"Error fetching layer: {result['error']}")
                            elif not result["features"]:
                                st.warning("No features returned — layer may be empty or require authentication")
                            else:
                                color  = "#a78bfa"
                                iname  = item.get("title", item["id"])
                                def make_esri_popup(nm, clr):
                                    def fn(feat): return esri_feature_popup_html(feat, nm, clr)
                                    return fn
                                st.session_state.map_layers.append({
                                    "id":        f"esri_{item['id']}",
                                    "name":      iname,
                                    "type":      "esri",
                                    "color":     color,
                                    "icon":      "⊕",
                                    "features":  result["features"],
                                    "visible":   True,
                                    "popup_fn":  make_esri_popup(iname, color),
                                    "count":     result["total"],
                                    "source":    f"ESRI · {service_url}",
                                })
                                st.success(f"✓ Added {result['total']} features to map")
                                st.rerun()

    if st.session_state.esri_items:
        st.divider()
        st.markdown(f"**{len(st.session_state.esri_items)} ESRI layer(s) in KB:**")
        for i, ei in enumerate(st.session_state.esri_items):
            c1, c2 = st.columns([5, 1])
            with c1: st.markdown(f'<span class="pill p-purple">⊕ {ei["name"][:60]}</span>', unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"rm_esri_{i}"):
                    st.session_state.esri_items.pop(i)
                    st.rerun()

    # ESRI layers currently on map
    esri_map_layers = [l for l in st.session_state.map_layers if l["type"] == "esri"]
    if esri_map_layers:
        st.divider()
        st.markdown(f"**{len(esri_map_layers)} ESRI layer(s) on map:**")
        for i, layer in enumerate(esri_map_layers):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f'<span class="pill p-purple">⊕ {layer["name"][:50]} · {layer["count"]} features</span>', unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"rm_esri_map_{i}"):
                    st.session_state.map_layers = [l for l in st.session_state.map_layers if l["id"] != layer["id"]]
                    st.rerun()

# ── Chat Tab ──────────────────────────────────────────────────────────────────
with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    with st.expander("▸ Quick Queries"):
        qcols = st.columns(2)
        quick = [
            "Storm surge risk — Lower Manhattan",
            "Zone 1 assets at risk from Cat 2 hurricane",
            "Trauma centers and hospital surge capacity",
            "Current NWS alerts for NYC",
            "Heat emergency protocol thresholds",
            "Flash flood — basement apartment risk",
            "Critical infrastructure in FEMA Zone AE",
            "What do the current water levels indicate?",
        ]
        for i, q in enumerate(quick):
            if qcols[i % 2].button(q, key=f"quick_{i}", use_container_width=True):
                st.session_state.pending_query = q

    def run_query(prompt):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        ctx  = build_context(
            st.session_state.files, st.session_state.api_results,
            active_kb, st.session_state.esri_items,
            st.session_state.get("noaa_items", []),
            st.session_state.get("gauge_data", {}),
        )
        msgs = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full = ""
            for token in stream_ollama(msgs, ctx):
                full += token
                placeholder.markdown(full + "▋")
            placeholder.markdown(full)
        st.session_state.messages.append({"role": "assistant", "content": full})

    if "pending_query" in st.session_state:
        run_query(st.session_state.pop("pending_query"))

    if prompt := st.chat_input("Incident type + location… e.g. 'Cat 2 hurricane at Coney Island'"):
        run_query(prompt)
