"""
EMBER — Emergency Management Body of Evidence & Resources
Streamlit version · Ollama Cloud + ArcGIS Online / Living Atlas

Setup:
    pip install -r requirements.txt
    export OLLAMA_API_KEY=your_key_here
    streamlit run streamlit/app.py
"""

import json, os, re
from io import StringIO
import folium, requests, streamlit as st
from streamlit_folium import st_folium

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_API_KEY = st.secrets.get("OLLAMA_API_KEY", os.environ.get("OLLAMA_API_KEY", ""))
OLLAMA_HOST    = st.secrets.get("OLLAMA_HOST",    os.environ.get("OLLAMA_HOST",    "https://ollama.com"))
OLLAMA_MODEL   = st.secrets.get("OLLAMA_MODEL",   os.environ.get("OLLAMA_MODEL",   "gpt-oss:120b-cloud"))
AGOL_BASE      = "https://www.arcgis.com/sharing/rest"

HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {OLLAMA_API_KEY}"}

st.set_page_config(page_title="EMBER — NYC Emergency Management", page_icon="🚨", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Mono', monospace !important; }
.stApp { background: #07090d; color: #e0e0e8; }
section[data-testid="stSidebar"] { background: #090c12 !important; border-right: 1px solid #111820; }
.pill { display:inline-block; padding:2px 8px; border-radius:12px; font-size:10px; font-weight:700; letter-spacing:0.05em; margin:2px; }
.p-green  { background:#4ade8020; color:#4ade80; border:1px solid #4ade8044; }
.p-red    { background:#f8717120; color:#f87171; border:1px solid #f8717144; }
.p-blue   { background:#60a5fa20; color:#60a5fa; border:1px solid #60a5fa44; }
.p-purple { background:#a78bfa20; color:#a78bfa; border:1px solid #a78bfa44; }
.p-yellow { background:#facc1520; color:#facc15; border:1px solid #facc1544; }
.esri-card { background:#0d1117; border:1px solid #1a1e2e; border-radius:6px; padding:10px 12px; margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

# ── NYC KB data ───────────────────────────────────────────────────────────────
NYC_KB = {
    "floodZones":             {"label":"Flood Zones (FEMA)",      "source":"FEMA NFHL / NYC OEM", "data":"Zone A: High-risk coastal/tidal flood areas — Lower Manhattan, Red Hook (Brooklyn), Rockaway Peninsula (Queens), Staten Island east shore.\nZone AE: Special Flood Hazard Areas with established base flood elevations. Coney Island, Howard Beach, Broad Channel, southern Staten Island.\nZone VE: Coastal high-hazard areas with wave action. Far Rockaway, Breezy Point, Sea Gate.\nZone X (shaded): Moderate flood risk, 0.2% annual chance.\nPost-Sandy (2012): ~88,000 buildings damaged; $19B in damage."},
    "evacZones":              {"label":"Evacuation Zones",         "source":"NYC OEM",             "data":"Zone 1 (Highest Risk): Mandatory evacuation Cat 1+ hurricanes. Rockaways, Coney Island, South Beach SI, Red Hook waterfront.\nZone 2: Evacuation advised Cat 2+. Zones 3-6: progressively lower risk inland.\nShelters: 30+ hurricane evacuation centers, ~600,000 primary capacity.\nContraflow routes: FDR Drive, BQE, Staten Island Expressway."},
    "criticalInfrastructure": {"label":"Critical Infrastructure", "source":"NYC OEM / CISA",      "data":"Hospitals: 11 Level 1 Trauma Centers. Bellevue (Manhattan), Kings County (Brooklyn), Lincoln (Bronx), Staten Island University, Jamaica (Queens).\nPower: ConEd East River substations critical. Underground feeders in Lower Manhattan flooded during Sandy.\nSubway: 245 miles track, 472 stations. 52 stations in flood zones.\nWater: DEP 14 reservoirs, 2 city tunnels. Newtown Creek & North River WWTPs flooded in Sandy.\nAirports: JFK (Zone A/AE), LaGuardia (Zone A)."},
    "hazardProfiles":         {"label":"Hazard Profiles",         "source":"NYC OEM HMP 2023",    "data":"HURRICANES: Sandy (2012, Cat 1) — $19B damage. Primary risk: storm surge.\nEXTREME HEAT: 115-150 deaths/year. Protocol activates at Heat Index >= 100F. 500+ cooling centers.\nCOASTAL/URBAN FLOODING: Ida 2021 — 13 deaths in basement apartments.\nWINTER STORMS: Jonas 2016 — 27 inches, travel ban.\nEARTHQUAKE: Low risk. Historical 1884 M5.5.\nTERRORISM/HAZMAT: Highest-risk US city (DHS)."},
    "resources":              {"label":"Contacts & Resources",    "source":"NYC OEM / 311",       "data":"NYC OEM: 718-422-8700 | nyc.gov/oem\nFDNY: 911 | 718-999-2000 | NYPD: 911 | 646-610-5000\nNYC Health: 311 | FEMA Region 2: 212-680-3600\nNWS OKX: 631-924-0517 | Con Edison: 1-800-75-CONED\nNotify NYC: nyc.gov/notifynyc"},
}

LIVE_ENDPOINTS = [
    {"name":"NWS Alerts — NY",    "url":"https://api.weather.gov/alerts/active?area=NY",                                                                         "type":"weather"},
    {"name":"NWS Forecast — NYC", "url":"https://api.weather.gov/gridpoints/OKX/33,37/forecast",                                                                 "type":"forecast"},
    {"name":"USGS Stream Gauges", "url":"https://waterservices.usgs.gov/nwis/iv/?format=json&stateCd=ny&parameterCd=00065&siteStatus=active",                    "type":"flood"},
    {"name":"FEMA Disasters",     "url":"https://www.fema.gov/api/open/v2/disasterDeclarationsSummaries?state=NY&$top=10&$orderby=declarationDate%20desc",       "type":"fema"},
    {"name":"NYC 311",            "url":"https://data.cityofnewyork.us/resource/erm2-nwe9.json?$limit=5&$order=created_date%20DESC",                             "type":"civic"},
]

MAP_POINTS = {
    "hospitals":  {"label":"Trauma Centers","color":"#f87171","features":[{"name":"Bellevue Hospital","lat":40.7394,"lng":-73.9754,"note":"Level 1 Trauma | Manhattan"},{"name":"Kings County Hospital","lat":40.6551,"lng":-73.9444,"note":"Level 1 Trauma | Brooklyn"},{"name":"Lincoln Medical Center","lat":40.8168,"lng":-73.9249,"note":"Level 1 Trauma | Bronx"},{"name":"Jamaica Hospital","lat":40.7003,"lng":-73.7958,"note":"Level 1 Trauma | Queens"},{"name":"Staten Island University","lat":40.5766,"lng":-74.1159,"note":"Level 1 Trauma | Staten Island"}]},
    "shelters":   {"label":"Evac Shelters", "color":"#60a5fa","features":[{"name":"Boys & Girls HS","lat":40.6797,"lng":-73.9434,"note":"Evac Center | Brooklyn"},{"name":"Brandeis HS","lat":40.7960,"lng":-73.9804,"note":"Evac Center | Manhattan"},{"name":"August Martin HS","lat":40.6719,"lng":-73.7770,"note":"Evac Center | Queens"},{"name":"Lehman HS","lat":40.8780,"lng":-73.8985,"note":"Evac Center | Bronx"}]},
    "gauges":     {"label":"Stream Gauges", "color":"#4ade80","features":[{"name":"Battery Park Tidal Gauge","lat":40.7003,"lng":-74.0141,"note":"NOAA 8518750 — primary surge gauge"},{"name":"Kings Point Tidal Gauge","lat":40.8105,"lng":-73.7659,"note":"NOAA 8516945"},{"name":"Jamaica Bay (Inwood)","lat":40.6226,"lng":-73.7576,"note":"NOAA tidal — Zone A"}]},
    "eoc":        {"label":"EOC / Command", "color":"#facc15","features":[{"name":"NYC EOC","lat":40.6967,"lng":-73.9896,"note":"Primary EOC — 165 Cadman Plaza East"},{"name":"Pier 92 Backup EOC","lat":40.7671,"lng":-74.0029,"note":"Backup EOC"},{"name":"FEMA Region 2","lat":40.7143,"lng":-74.0071,"note":"26 Federal Plaza"}]},
    "floodRisk":  {"label":"Flood Risk",    "color":"#fb923c","features":[{"name":"Red Hook, Brooklyn","lat":40.6745,"lng":-74.0097,"note":"Zone AE — Sandy 2012"},{"name":"Coney Island","lat":40.5755,"lng":-73.9707,"note":"Zone AE — 10ft+ surge"},{"name":"Rockaway Peninsula","lat":40.5874,"lng":-73.8261,"note":"Zone VE/AE — highest surge"},{"name":"Howard Beach","lat":40.6570,"lng":-73.8378,"note":"Zone AE"},{"name":"South Beach, SI","lat":40.5842,"lng":-74.0783,"note":"Zone AE — Sandy impact"},{"name":"Lower Manhattan (FiDi)","lat":40.7074,"lng":-74.0104,"note":"Zone AE — utility risk"},{"name":"Breezy Point","lat":40.5587,"lng":-73.9290,"note":"Zone VE — wave action"}]},
}

LIVING_ATLAS_FILTERS = {
    "All Public":         "",
    "Living Atlas Only":  "owner:esri_livingatlas",
    "Flood / Hydrology":  "tags:flood OR tags:hydrology",
    "Hurricanes":         "tags:hurricane OR tags:storm surge",
    "Wildfire":           "tags:wildfire OR tags:fire perimeter",
    "Emergency Mgmt":     "tags:emergency management OR tags:disaster",
    "Critical Infra":     "tags:critical infrastructure",
    "Climate / Weather":  "tags:climate OR tags:weather",
    "NYC / New York":     "tags:New York City OR tags:NYC",
    "FEMA":               "tags:FEMA OR owner:FEMA",
}

ITEM_TYPES = ["","Feature Layer","Map Service","Image Service","Vector Tile Layer","Web Map","Web Scene","Feature Collection","StoryMap","Dashboard"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def ping_ollama():
    if not OLLAMA_API_KEY: return "no-key"
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", headers=HEADERS, timeout=5)
        return r.ok
    except: return False

def fetch_live(ep):
    try:
        r = requests.get(ep["url"], timeout=7); r.raise_for_status()
        return {"success":True,"data":r.json(),"name":ep["name"],"type":ep["type"]}
    except Exception as e:
        return {"success":False,"error":str(e),"name":ep["name"],"type":ep["type"]}

def summarize_api(result):
    if not result["success"]: return f"[{result['name']}: unavailable — {result['error']}]"
    d, t = result["data"], result["type"]
    try:
        if t=="weather" and "features" in d:
            alerts="; ".join(f"{f['properties']['event']} — {str(f['properties'].get('headline',''))[:80]}" for f in d["features"][:3])
            return f"NWS Active Alerts (NY): {len(d['features'])} total. {alerts or 'None'}"
        if t=="forecast" and "properties" in d:
            return "NWS Forecast NYC: "+"; ".join(f"{p['name']}: {p['shortForecast']}, {p['temperature']}°{p['temperatureUnit']}" for p in d["properties"]["periods"][:3])
        if t=="flood" and "value" in d:
            return "USGS NY Gauges: "+"; ".join(f"{g['sourceInfo']['siteName']}: {g['values'][0]['value'][0]['value'] if g.get('values') else 'N/A'} ft" for g in d["value"]["timeSeries"][:4])
        if t=="fema" and "DisasterDeclarationsSummaries" in d:
            return "FEMA NY: "+"; ".join(f"{x['incidentType']} — {x['declarationTitle']}" for x in d["DisasterDeclarationsSummaries"][:3])
        if t=="civic" and isinstance(d,list):
            return "NYC 311: "+"; ".join(f"{x.get('complaint_type','?')}: {x.get('descriptor','?')} ({x.get('borough','?')})" for x in d[:3])
        return f"[{result['name']}: received]"
    except: return f"[{result['name']}: parse error]"

def build_context(files, api_results, active_modules, esri_items, noaa_items=None):
    ctx = "=== NYC EMERGENCY MANAGEMENT KNOWLEDGE BASE ===\n\n"
    for key, mod in NYC_KB.items():
        if key in active_modules:
            ctx += f"--- {mod['label']} [{mod['source']}] ---\n{mod['data']}\n\n"
    if api_results:
        ctx += "--- LIVE API DATA ---\n"
        for r in api_results: ctx += summarize_api(r)+"\n"
        ctx += "\n"
    if files:
        ctx += "--- UPLOADED DOCUMENTS ---\n"
        for f in files: ctx += f"[File: {f['name']}]\n{f['content'][:4000]}\n\n"
    if noaa_items:
        ctx += "--- NOAA OPEN DATA (user-fetched) ---\n"
        for item in noaa_items: ctx += item["content"]+"\n\n"
    if esri_items:
        ctx += "--- ESRI / LIVING ATLAS LAYERS (user-selected) ---\n"
        for item in esri_items: ctx += item["content"]+"\n\n"
    return ctx

def stream_ollama(messages, context):
    if not OLLAMA_API_KEY:
        yield "⚠ No API key. Set OLLAMA_API_KEY. Get one at https://ollama.com/settings/keys"
        return
    system_prompt = f"""You are EMBER — Emergency Management Body of Evidence & Resources — an AI for NYC emergency managers.

KNOWLEDGE BASE:
{context}

RULES:
1. Lead with operationally critical information first.
2. Cite sources: [NYC OEM], [NWS], [FEMA], [USGS], [ESRI Living Atlas], etc.
3. For location queries, prioritize zone and risk data.
4. Flag data gaps. Use headers and bullets for action items.
5. For life-safety queries, always include emergency contact numbers.
6. For ESRI layer queries, describe the layer's coverage, update frequency, and operational relevance.
7. Never hallucinate."""
    payload = {"model":OLLAMA_MODEL,"stream":True,"messages":[{"role":"system","content":system_prompt}]+messages[-10:]}
    try:
        with requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, headers=HEADERS, stream=True, timeout=90) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    obj = json.loads(line)
                    token = obj.get("message",{}).get("content","")
                    if token: yield token
                    if obj.get("done"): return
    except requests.exceptions.HTTPError as e:
        yield f"\n\n⚠ Ollama Cloud error {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        yield f"\n\n⚠ Connection error: {e}"

def search_agol(query, filter_expr="", item_type="", num=8, start=1):
    q = query.strip() or "*"
    scope = ["access:public"]
    if filter_expr: scope.append(f"({filter_expr})")
    if item_type:   scope.append(f'type:"{item_type}"')
    full_q = f"{q} {' AND '.join(scope)}"
    params = {"f":"json","q":full_q,"num":str(num),"start":str(start),"sortField":"relevance","sortOrder":"desc"}
    try:
        r = requests.get(f"{AGOL_BASE}/search", params=params, timeout=10); r.raise_for_status()
        d = r.json()
        if "error" in d: return [], 0, d["error"].get("message","AGOL error")
        return d.get("results",[]), d.get("total",0), None
    except Exception as e:
        return [], 0, str(e)

def fetch_item_metadata(item_id):
    try:
        r = requests.get(f"{AGOL_BASE}/content/items/{item_id}", params={"f":"json"}, timeout=8)
        r.raise_for_status(); item = r.json()
        try:
            dr = requests.get(f"{AGOL_BASE}/content/items/{item_id}/data", params={"f":"json"}, timeout=8)
            data = dr.json() if dr.ok else None
        except: data = None
        return item, data, None
    except Exception as e:
        return None, None, str(e)

def format_item_for_context(item, data=None):
    if not item: return ""
    tags = ", ".join(item.get("tags",[]))
    extent = str(item.get("extent","N/A"))
    url = item.get("url","") or f"https://www.arcgis.com/home/item.html?id={item.get('id','')}"
    block = f"""[ESRI/Living Atlas Item: {item.get('title','')}]
  Item ID:     {item.get('id','')}
  Type:        {item.get('type','')}
  Owner:       {item.get('owner','')}
  Description: {re.sub(r'<[^>]+>','',item.get('description',''))[:600]}
  Tags:        {tags}
  Snippet:     {item.get('snippet','')}
  Extent:      {extent}
  Spatial Ref: {item.get('spatialReference',{}).get('wkid','unknown') if isinstance(item.get('spatialReference'),dict) else 'unknown'}
  Access:      {item.get('access','')}
  Updated:     {str(item.get('modified',''))[:10]}
  Service URL: {url}
  Views:       {item.get('numViews',0)}"""
    if data and isinstance(data, dict):
        if "layers" in data:
            block += "\n  Layers: " + ", ".join(f"{l.get('id','?')}:{l.get('name','?')}" for l in data["layers"])
        if "operationalLayers" in data:
            block += "\n  Operational Layers: " + ", ".join(l.get("title","?") for l in data["operationalLayers"])
    return block

def fetch_wind_obs():
    """Fetch current wind and precip obs from NWS for NYC-area stations."""
    stations = [
        {"id":"KNYC","name":"Central Park","lat":40.7789,"lng":-73.9692},
        {"id":"KJFK","name":"JFK Airport","lat":40.6413,"lng":-73.7781},
        {"id":"KEWR","name":"Newark","lat":40.6895,"lng":-74.1745},
        {"id":"KLGA","name":"LaGuardia","lat":40.7772,"lng":-73.8726},
    ]
    results = []
    for s in stations:
        try:
            r = requests.get(
                f"https://api.weather.gov/stations/{s['id']}/observations/latest",
                timeout=6, headers={"User-Agent":"EMBER/1.0"}
            )
            if not r.ok: continue
            p = r.json()["properties"]
            speed_mph = round(p["windSpeed"]["value"] * 0.621371, 0) if p.get("windSpeed",{}).get("value") is not None else None
            gust_mph  = round(p["windGust"]["value"]  * 0.621371, 0) if p.get("windGust",{}).get("value")  is not None else None
            dir_deg   = p.get("windDirection",{}).get("value")
            temp_f    = round(p["temperature"]["value"] * 9/5 + 32, 0) if p.get("temperature",{}).get("value") is not None else None
            precip_in = round(p["precipitationLastHour"]["value"] * 0.0393701, 2) if p.get("precipitationLastHour",{}).get("value") is not None else None
            results.append({**s, "speed_mph":speed_mph, "gust_mph":gust_mph,
                             "dir_deg":dir_deg, "temp_f":temp_f,
                             "precip_in":precip_in, "desc":p.get("textDescription","")})
        except: continue
    return results

def build_map(active_layers, show_radar=False, show_wind=False, wind_obs=None):
    m = folium.Map(location=[40.7128,-74.006], zoom_start=10, tiles="CartoDB dark_matter", prefer_canvas=True)

    # ── NEXRAD radar tile overlay ──────────────────────────────────────────────
    if show_radar:
        folium.TileLayer(
            tiles="https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/nexrad-n0q-900913/{z}/{x}/{y}.png",
            name="NEXRAD Radar",
            attr='NEXRAD &copy; Iowa State MESONET',
            opacity=0.65,
            overlay=True,
            control=True,
        ).add_to(m)

    # ── Marker layers ──────────────────────────────────────────────────────────
    for key, layer in MAP_POINTS.items():
        if key not in active_layers: continue
        fg = folium.FeatureGroup(name=layer["label"])
        for f in layer["features"]:
            folium.CircleMarker(location=[f["lat"],f["lng"]], radius=8, color=layer["color"], fill=True,
                fill_color=layer["color"], fill_opacity=0.5,
                popup=folium.Popup(f'<div style="font-family:monospace;font-size:11px"><b style="color:{layer["color"]}">{f["name"]}</b><br>{f["note"]}</div>', max_width=220),
                tooltip=f["name"]).add_to(fg)
        fg.add_to(m)

    # ── Wind observation arrows ────────────────────────────────────────────────
    if show_wind and wind_obs:
        wind_fg = folium.FeatureGroup(name="Wind Observations")
        for o in wind_obs:
            if o.get("speed_mph") is None or o.get("dir_deg") is None: continue
            spd  = int(o["speed_mph"])
            gust = int(o["gust_mph"]) if o.get("gust_mph") else None
            color = "#4ade80" if spd < 15 else "#facc15" if spd < 25 else "#fb923c" if spd < 40 else "#f87171"
            to_dir = (o["dir_deg"] + 180) % 360  # arrow points TO direction
            html = f"""<div style="
                font-family:monospace;text-align:center;
                transform:rotate({to_dir}deg);font-size:20px;
                color:{color};filter:drop-shadow(0 0 3px {color}88);
                ">↑</div>
                <div style="font-size:9px;font-family:monospace;font-weight:700;
                color:{color};background:#07090dcc;padding:1px 3px;
                border-radius:2px;white-space:nowrap;text-align:center;
                ">{spd}{f"g{gust}" if gust else ""}mph</div>"""
            popup_txt = (
                f"<b style='color:{color}'>{o['id']} — {o['name']}</b><br>"
                f"Wind: {spd}mph from {int(o['dir_deg'])}°"
                + (f" (gusts {gust}mph)" if gust else "")
                + (f"<br>Precip (1h): {o['precip_in']}\"" if o.get('precip_in') is not None else "")
                + (f"<br>Temp: {int(o['temp_f'])}°F" if o.get('temp_f') is not None else "")
                + (f"<br>{o['desc']}" if o.get('desc') else "")
            )
            folium.Marker(
                location=[o["lat"], o["lng"]],
                icon=folium.DivIcon(html=html, icon_size=(50,40), icon_anchor=(25,10)),
                popup=folium.Popup(f'<div style="font-family:monospace;font-size:11px">{popup_txt}</div>', max_width=220),
                tooltip=f"{o['id']}: {spd}mph"
            ).add_to(wind_fg)
        wind_fg.add_to(m)

    folium.LayerControl().add_to(m)
    return m

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("messages",[{"role":"assistant","content":f"EMBER initialized\nBackend: Ollama Cloud · {OLLAMA_MODEL}\nJurisdiction: New York City\n\nKnowledge base + ESRI/Living Atlas search ready. Use the sidebar to search ArcGIS Online, inspect metadata, and inject layers into the KB."}]),("files",[]),("api_results",[]),("esri_items",[]),("esri_results",[]),("esri_total",0),("esri_searched",False)]:
    if k not in st.session_state: st.session_state[k] = v

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚨 EMBER")
    st.caption(f"Ollama Cloud · {OLLAMA_MODEL}")

    status = ping_ollama()
    if status=="no-key": st.markdown('<span class="pill p-yellow">⚠ NO API KEY</span>', unsafe_allow_html=True); st.info("Set OLLAMA_API_KEY. Get one at ollama.com/settings/keys")
    elif status is True:  st.markdown('<span class="pill p-green">● OLLAMA CLOUD OK</span>', unsafe_allow_html=True)
    else:                 st.markdown('<span class="pill p-red">● CLOUD UNREACHABLE</span>', unsafe_allow_html=True)

    st.divider()
    st.markdown("**KNOWLEDGE BASE**")
    active_kb = [k for k,m in NYC_KB.items() if st.checkbox(m["label"],value=True,key=f"kb_{k}")]

    st.divider()
    st.markdown("**MAP LAYERS**")
    layer_opts = {"hospitals":"🏥 Trauma Centers","shelters":"🏫 Evac Shelters","gauges":"📡 Stream Gauges","eoc":"🏛 EOC / Command","floodRisk":"💧 Flood Risk Areas"}
    active_layers = [k for k,label in layer_opts.items() if st.checkbox(label,value=True,key=f"map_{k}")]

    st.markdown("**WEATHER OVERLAYS**")
    show_radar = st.checkbox("📡 NEXRAD Radar", value=False, key="show_radar",
                             help="Iowa State MESONET composite reflectivity tiles — ~5min latency, no key required")
    show_wind  = st.checkbox("💨 Wind Observations", value=False, key="show_wind",
                             help="Live NWS surface obs from KNYC, KJFK, KEWR, KLGA")
    if show_wind:
        if st.button("↺ Refresh Wind", use_container_width=True):
            with st.spinner("Fetching wind obs…"):
                st.session_state.wind_obs = fetch_wind_obs()
        if "wind_obs" not in st.session_state:
            with st.spinner("Fetching wind obs…"):
                st.session_state.wind_obs = fetch_wind_obs()
    wind_obs = st.session_state.get("wind_obs", []) if show_wind else []

    st.divider()
    st.markdown("**LIVE FEEDS**")
    if st.button("↺ Fetch All Feeds",use_container_width=True):
        with st.spinner("Fetching…"): st.session_state.api_results=[fetch_live(ep) for ep in LIVE_ENDPOINTS]
    for r in st.session_state.api_results:
        st.markdown(f'<span class="pill {"p-green" if r["success"] else "p-red"}">{"●" if r["success"] else "○"} {r["name"]}</span>', unsafe_allow_html=True)

    st.divider()
    st.markdown("**INGEST DOCUMENTS**")
    uploads = st.file_uploader("SOPs, GeoJSON, CSV, plans", accept_multiple_files=True, type=["txt","csv","json","geojson","md"])
    if uploads:
        existing={f["name"] for f in st.session_state.files}
        for up in uploads:
            if up.name not in existing: st.session_state.files.append({"name":up.name,"content":StringIO(up.read().decode("utf-8",errors="replace")).read()})
    for f in st.session_state.files: st.markdown(f'<span class="pill p-blue">📄 {f["name"]}</span>', unsafe_allow_html=True)
    if st.session_state.files and st.button("Clear Documents"): st.session_state.files=[]

    st.divider()
    if st.button("Clear Chat",use_container_width=True): st.session_state.messages=[]; st.rerun()

# ── Main layout ────────────────────────────────────────────────────────────────
st.markdown("### 🗺️ NYC Operational Map")

if show_wind and wind_obs:
    st.markdown("**💨 Current Wind Observations**")
    wind_cols = st.columns(min(len(wind_obs), 4))
    for i, o in enumerate(wind_obs):
        with wind_cols[i % 4]:
            spd  = int(o["speed_mph"]) if o.get("speed_mph") is not None else None
            gust = int(o["gust_mph"])  if o.get("gust_mph")  is not None else None
            st.metric(
                label=f"{o['id']} — {o['name']}",
                value=f"{spd}mph" + (f" g{gust}" if gust else "") if spd is not None else "—",
                delta=f"{int(o['dir_deg'])}° · {o.get('desc','')[:20]}" if o.get("dir_deg") is not None else None,
                delta_color="off"
            )

if show_radar:
    st.caption("📡 NEXRAD radar overlay active — ~5min latency · Iowa State MESONET")

map_data = st_folium(build_map(active_layers, show_radar=show_radar, show_wind=show_wind, wind_obs=wind_obs),
                     width="100%", height=360, returned_objects=["last_object_clicked_popup"])

if map_data and map_data.get("last_object_clicked_popup"):
    m2=re.search(r'<b[^>]*>([^<]+)</b>',map_data["last_object_clicked_popup"] or "")
    if m2 and "pending_query" not in st.session_state: st.session_state.pending_query=f"Emergency considerations and risk profile for: {m2.group(1)}"

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_chat, tab_noaa, tab_esri = st.tabs(["💬 EMBER Chat", "📡 NOAA Data Stack", "⊕ ESRI / Living Atlas"])

# ── NOAA Tab ──────────────────────────────────────────────────────────────────
NOAA_ENDPOINTS_FLAT = [
    # NWS
    {"id":"nws_alerts_ny",    "cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"Active Alerts — NY",              "url":"https://api.weather.gov/alerts/active?area=NY",                                                                                        "desc":"All active NWS alerts for New York State",                                "tags":["alerts","flood","tornado","winter storm"]},
    {"id":"nws_alerts_severe","cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"Extreme/Severe Alerts Only",       "url":"https://api.weather.gov/alerts/active?area=NY&severity=Extreme,Severe&status=Actual",                                                    "desc":"Only extreme and severe active alerts",                                    "tags":["extreme","severe","priority"]},
    {"id":"nws_forecast_nyc", "cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"7-Day Forecast — NYC",             "url":"https://api.weather.gov/gridpoints/OKX/33,37/forecast",                                                                                 "desc":"NWS OKX 7-day text forecast for NYC metro",                               "tags":["forecast","7-day","temperature"]},
    {"id":"nws_forecast_hrly","cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"Hourly Forecast — NYC",            "url":"https://api.weather.gov/gridpoints/OKX/33,37/forecast/hourly",                                                                          "desc":"Hour-by-hour forecast — temp, wind, precipitation probability",           "tags":["hourly","wind","precipitation"]},
    {"id":"nws_grid_wind",    "cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"Wind & Precip Grid — NYC",         "url":"https://api.weather.gov/gridpoints/OKX/33,37",                                                                                          "desc":"Full NWS gridpoint — wind speed, gusts, direction, QPF, precip prob",    "tags":["wind","QPF","precipitation","grid"]},
    {"id":"nws_obs_knyc",     "cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"Observations — Central Park",      "url":"https://api.weather.gov/stations/KNYC/observations/latest",                                                                             "desc":"Latest surface observation from Central Park",                            "tags":["observations","current conditions","temperature"]},
    {"id":"nws_obs_kjfk",     "cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"Observations — JFK Airport",       "url":"https://api.weather.gov/stations/KJFK/observations/latest",                                                                             "desc":"Latest surface observation from JFK",                                     "tags":["observations","airport","coastal"]},
    {"id":"nws_products_okx", "cat":"NWS",   "color":"#60a5fa","icon":"🌩","name":"Text Products — NWS OKX",          "url":"https://api.weather.gov/products?office=OKX&limit=10",                                                                                  "desc":"Latest NWS text products: AFD, Coastal Hazards, etc.",                   "tags":["AFD","forecast discussion","text products"]},
    # CO-OPS
    {"id":"coops_battery",    "cat":"CO-OPS","color":"#34d399","icon":"🌊","name":"Water Level — The Battery",         "url":"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8518750&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER",    "desc":"Real-time water level at The Battery — primary NYC surge gauge",          "tags":["water level","surge","battery"]},
    {"id":"coops_predictions","cat":"CO-OPS","color":"#34d399","icon":"🌊","name":"Tidal Predictions — Battery (48h)", "url":"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&range=48&station=8518750&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json&application=EMBER","desc":"High/low tide predictions — next 48 hours",                               "tags":["tide predictions","high tide","low tide"]},
    {"id":"coops_kings_point","cat":"CO-OPS","color":"#34d399","icon":"🌊","name":"Water Level — Kings Point",         "url":"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8516945&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER",    "desc":"Real-time water level — Long Island Sound",                              "tags":["water level","long island sound"]},
    {"id":"coops_sandy_hook", "cat":"CO-OPS","color":"#34d399","icon":"🌊","name":"Water Level — Sandy Hook, NJ",      "url":"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8531680&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json&application=EMBER",    "desc":"Real-time water level at Sandy Hook — outer harbor reference",           "tags":["water level","sandy hook","outer harbor"]},
    {"id":"coops_wind",       "cat":"CO-OPS","color":"#34d399","icon":"🌊","name":"Wind — The Battery Station",        "url":"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8518750&product=wind&time_zone=lst_ldt&units=english&format=json&application=EMBER",                     "desc":"Real-time wind speed and direction at The Battery",                      "tags":["wind","meteorological"]},
    {"id":"coops_stations",   "cat":"CO-OPS","color":"#34d399","icon":"🌊","name":"All CO-OPS Stations — NY",          "url":"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels&state=NY",                                       "desc":"All active water level stations in New York state",                       "tags":["stations","inventory"]},
    # NCEI
    {"id":"ncei_datasets",    "cat":"NCEI",  "color":"#f59e0b","icon":"📊","name":"NCEI Dataset Catalog",              "url":"https://www.ncei.noaa.gov/access/services/support/v3/datasets.json",                                                                    "desc":"Full catalog of all NCEI datasets",                                       "tags":["catalog","datasets","metadata"]},
    {"id":"ncei_daily_cp",    "cat":"NCEI",  "color":"#f59e0b","icon":"📊","name":"Daily Summaries — Central Park (7d)","url":"https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094728&dataTypes=TMAX,TMIN,PRCP,SNOW,AWND&startDate=STARTDATE&endDate=ENDDATE&format=json&units=standard","desc":"Last 7 days of daily weather from Central Park",                          "tags":["daily summaries","temperature","precipitation","snow"],"dynamic":True},
    {"id":"ncei_daily_jfk",   "cat":"NCEI",  "color":"#f59e0b","icon":"📊","name":"Daily Summaries — JFK (7d)",         "url":"https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=USW00094789&dataTypes=TMAX,TMIN,PRCP,SNOW,AWND&startDate=STARTDATE&endDate=ENDDATE&format=json&units=standard","desc":"Last 7 days of daily weather from JFK Airport",                          "tags":["daily summaries","jfk","coastal"],"dynamic":True},
    {"id":"ncei_storm_meta",  "cat":"NCEI",  "color":"#f59e0b","icon":"📊","name":"Storm Events Dataset Metadata",      "url":"https://www.ncei.noaa.gov/access/services/support/v3/datasets/storm-events.json",                                                      "desc":"Metadata for NCEI storm events database",                                "tags":["storm events","metadata","historical"]},
    # SPC
    {"id":"spc_watches",      "cat":"SPC",   "color":"#f87171","icon":"⚡","name":"Active Watches (Tornado/SVR)",       "url":"https://www.spc.noaa.gov/products/watch/ActiveWW.txt",                                                                                 "desc":"Currently active SPC watches",                                            "tags":["watches","tornado","severe thunderstorm"],"text":True},
    {"id":"spc_day1",         "cat":"SPC",   "color":"#f87171","icon":"⚡","name":"Day 1 Convective Outlook",           "url":"https://www.spc.noaa.gov/products/outlook/day1otlk.txt",                                                                               "desc":"SPC Day 1 convective outlook — categorical severe risk",                  "tags":["convective","outlook","severe"],"text":True},
    # SWPC
    {"id":"swpc_alerts",      "cat":"SWPC",  "color":"#a78bfa","icon":"☀️","name":"Space Weather Alerts",              "url":"https://services.swpc.noaa.gov/products/alerts.json",                                                                                   "desc":"Current space weather alerts, watches, warnings",                         "tags":["space weather","geomagnetic","solar flare","GPS"]},
    {"id":"swpc_solar_wind",  "cat":"SWPC",  "color":"#a78bfa","icon":"☀️","name":"Solar Wind — DSCOVR Real-Time",      "url":"https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json",                                                                 "desc":"Real-time solar wind plasma from DSCOVR satellite",                      "tags":["solar wind","real-time","DSCOVR"]},
    {"id":"swpc_kp",          "cat":"SWPC",  "color":"#a78bfa","icon":"☀️","name":"Planetary K-Index (1-min)",          "url":"https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",                                                                        "desc":"1-minute Kp index — geomagnetic disturbance level",                      "tags":["Kp index","geomagnetic"]},
]

import datetime as _dt

def _resolve_url(ep):
    url = ep["url"]
    if ep.get("dynamic"):
        today    = _dt.date.today().isoformat()
        week_ago = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
        url = url.replace("STARTDATE", week_ago).replace("ENDDATE", today)
    return url

def _fetch_noaa_ep(ep):
    url = _resolve_url(ep)
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent":"EMBER/1.0"})
        r.raise_for_status()
        if ep.get("text") or "text/plain" in r.headers.get("content-type",""):
            return {"success":True,"data":r.text,"text":True,"ep":ep}
        return {"success":True,"data":r.json(),"text":False,"ep":ep}
    except Exception as e:
        return {"success":False,"error":str(e),"ep":ep}

def _summarize_noaa(result):
    if not result["success"]: return f"[{result['ep']['name']}: failed — {result['error']}]"
    d, ep = result["data"], result["ep"]
    try:
        if result.get("text"): return f"[NOAA {ep['name']}]\n{str(d)[:800]}"
        if "features" in d and "alert" in ep["id"]:
            alerts = "\n".join(f"  - {f['properties']['event']} ({f['properties']['severity']}): {str(f['properties'].get('headline',''))[:90]}" for f in d["features"][:5])
            return f"[NWS Alerts: {len(d['features'])} active]\n{alerts or '  None'}"
        if "forecast" in ep["id"] and "properties" in d and "periods" in d.get("properties",{}):
            periods = "\n".join(f"  {p['name']}: {p['shortForecast']}, {p['temperature']}°{p['temperatureUnit']}" for p in d["properties"]["periods"][:6])
            return f"[NWS Forecast]\n{periods}"
        if "grid" in ep["id"] and "properties" in d:
            p = d["properties"]
            ws = p.get("windSpeed",{}).get("values",[])[:6]
            speeds = ", ".join(f"{(v['value']*0.621371):.0f}mph" for v in ws if v.get("value") is not None)
            qpf = p.get("quantitativePrecipitation",{}).get("values",[])[:6]
            inches = ", ".join(f"{(v['value']*0.0393701):.2f}\"" for v in qpf if v.get("value") is not None)
            return f"[NWS Gridpoint Wind & Precip]\n  Wind (next 6h): {speeds}\n  QPF (next 6h): {inches}"
        if "obs" in ep["id"] and "properties" in d:
            p = d["properties"]
            tempF = f"{(p['temperature']['value']*9/5+32):.1f}°F" if p.get("temperature",{}).get("value") is not None else "?"
            windMph = f"{(p['windSpeed']['value']*0.621371):.1f}mph" if p.get("windSpeed",{}).get("value") is not None else "?"
            return f"[NWS Obs — {ep['name']}]\n  Temp: {tempF} | Wind: {windMph} | {p.get('textDescription','?')}"
        if "coops_battery" in ep["id"] and "data" in d:
            latest = d["data"][-1] if d.get("data") else {}
            return f"[CO-OPS Battery Water Level]\n  Latest: {latest.get('v','?')} ft MLLW @ {latest.get('t','?')}"
        if "predictions" in ep["id"] and "predictions" in d:
            preds = "\n".join(f"  {'HIGH' if p['type']=='H' else 'low '} {p['v']}ft @ {p['t']}" for p in d["predictions"][:6])
            return f"[CO-OPS Tidal Predictions]\n{preds}"
        if "stations" in ep["id"] and "stations" in d:
            return f"[CO-OPS Stations: {len(d['stations'])}]\n" + "\n".join(f"  {s['id']}: {s['name']}" for s in d["stations"][:8])
        if "datasets" in ep["id"] and "datasets" in d:
            return f"[NCEI Datasets: {len(d['datasets'])}]\n" + "\n".join(f"  {ds['id']}: {ds['name']}" for ds in d["datasets"][:10])
        if isinstance(d, list) and len(d) > 0 and isinstance(d[0], dict) and "DATE" in d[0]:
            rows = "\n".join(f"  {r['DATE']}: TMAX={r.get('TMAX','?')} TMIN={r.get('TMIN','?')} PRCP={r.get('PRCP','?')}" for r in d[:7])
            return f"[NCEI Daily Summaries]\n{rows}"
        if isinstance(d, list) and ep["id"] == "swpc_alerts":
            return f"[Space Weather Alerts: {len(d)}]\n" + "\n".join(f"  {str(a.get('message',''))[:120]}" for a in d[:4])
        return f"[NOAA {ep['name']}]: {json.dumps(d)[:400]}"
    except Exception as e:
        return f"[NOAA {ep['name']}: parse error — {e}]"

with tab_noaa:
    st.markdown("#### NOAA Open Data Stack")
    st.caption("No API key required · NWS · CO-OPS Tides & Currents · NCEI Climate · SPC · SWPC Space Weather")

    if "noaa_results" not in st.session_state: st.session_state.noaa_results = {}
    if "noaa_items"   not in st.session_state: st.session_state.noaa_items   = []

    nc1, nc2 = st.columns([3,2])
    with nc1: noaa_search = st.text_input("Search endpoints…", placeholder="flood, tide, temperature, alerts, solar wind…", key="noaa_search")
    with nc2: noaa_cat    = st.selectbox("Category", ["All","NWS","CO-OPS","NCEI","SPC","SWPC"], key="noaa_cat")

    filtered_eps = [ep for ep in NOAA_ENDPOINTS_FLAT if
        (noaa_cat == "All" or ep["cat"] == noaa_cat) and
        (not noaa_search or
         noaa_search.lower() in ep["name"].lower() or
         noaa_search.lower() in ep["desc"].lower() or
         any(noaa_search.lower() in t for t in ep.get("tags",[])))
    ]

    injected_noaa_ids = {i["item_id"] for i in st.session_state.noaa_items}
    st.caption(f"{len(filtered_eps)} endpoint{'s' if len(filtered_eps)!=1 else ''} · {len(st.session_state.noaa_results)} fetched · {len(injected_noaa_ids)} in KB")

    for ep in filtered_eps:
        result  = st.session_state.noaa_results.get(ep["id"])
        injected = ep["id"] in injected_noaa_ids

        st.markdown(f"""<div class="esri-card" style="border-left:3px solid {ep['color']}">
            <div style="font-weight:700;color:#dde;margin-bottom:2px">{ep['icon']} {ep['name']}</div>
            <div style="font-size:10px;color:#556;margin-bottom:4px">{ep['desc']}</div>
            <div>{"".join(f'<span class="pill" style="background:{ep["color"]}18;color:{ep["color"]};border:1px solid {ep["color"]}33;margin:1px">{t}</span>' for t in ep.get("tags",[])[:4])}</div>
        </div>""", unsafe_allow_html=True)

        btn1, btn2, btn3, status_col = st.columns([1,1,1,2])

        with btn1:
            if st.button("▶ Fetch", key=f"nfetch_{ep['id']}", use_container_width=True):
                with st.spinner(f"Fetching…"):
                    st.session_state.noaa_results[ep["id"]] = _fetch_noaa_ep(ep)
                st.rerun()

        with btn2:
            if result and result["success"]:
                if not injected:
                    if st.button("+ Add to KB", key=f"ninject_{ep['id']}", use_container_width=True):
                        content = _summarize_noaa(result)
                        st.session_state.noaa_items.append({
                            "name": f"NOAA: {ep['name']}",
                            "item_id": ep["id"],
                            "content": f"[NOAA Open Data — {ep['name']}]\nSource: {_resolve_url(ep)}\n\n{content}"
                        })
                        st.session_state.pending_query = f"I just added '{ep['name']}' NOAA data to the knowledge base. Summarize the data and flag any emergency-relevant readings for NYC."
                        st.rerun()
                else:
                    st.button("✓ In KB", key=f"ninjected_{ep['id']}", disabled=True, use_container_width=True)

        with btn3:
            st.link_button("↗ URL", _resolve_url(ep))

        with status_col:
            if result:
                if result["success"]:
                    st.markdown('<span class="pill p-green">● OK</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="pill p-red">● ERR: {result["error"][:50]}</span>', unsafe_allow_html=True)

        if result and result["success"]:
            with st.expander("Preview"):
                st.code(_summarize_noaa(result), language=None)

        st.markdown("---")

    if st.session_state.noaa_items:
        st.markdown(f"**{len(st.session_state.noaa_items)} NOAA feed(s) in KB:**")
        for i, ni in enumerate(st.session_state.noaa_items):
            c1, c2 = st.columns([5,1])
            with c1: st.markdown(f'<span class="pill p-green">▶ {ni["name"][:60]}</span>', unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"rm_noaa_{i}"):
                    st.session_state.noaa_items.pop(i)
                    st.rerun()

# ── ESRI Tab ──────────────────────────────────────────────────────────────────
with tab_esri:
    st.markdown("#### Search ArcGIS Online & Living Atlas")
    st.caption("Public layers, no authentication required. Inject metadata directly into the EMBER knowledge base.")

    col1, col2, col3 = st.columns([3, 2, 2])
    with col1: esri_query = st.text_input("Search layers, maps, services…", placeholder="e.g. NYC flood zones, hurricane surge, FEMA disaster")
    with col2: esri_filter_label = st.selectbox("Filter", list(LIVING_ATLAS_FILTERS.keys()))
    with col3: esri_type = st.selectbox("Item Type", ITEM_TYPES)

    esri_filter = LIVING_ATLAS_FILTERS[esri_filter_label]

    col_search, col_page = st.columns([2,3])
    with col_search:
        do_search = st.button("🔍 Search ArcGIS Online", use_container_width=True)
    with col_page:
        esri_page = st.number_input("Page", min_value=1, value=1, step=1, label_visibility="collapsed")

    if do_search and esri_query:
        with st.spinner("Searching ArcGIS Online…"):
            results, total, err = search_agol(esri_query, esri_filter, esri_type, num=8, start=(esri_page-1)*8+1)
            st.session_state.esri_results = results
            st.session_state.esri_total   = total
            st.session_state.esri_searched = True
            if err: st.error(f"Search error: {err}")

    if st.session_state.esri_searched:
        results = st.session_state.esri_results
        total   = st.session_state.esri_total
        injected_ids = {i["item_id"] for i in st.session_state.esri_items}

        if not results: st.info("No results. Try broader search terms.")
        else:
            st.caption(f"{total:,} results found")
            for item in results:
                is_living_atlas = "esri" in (item.get("owner","")).lower()
                tags = ", ".join((item.get("tags") or [])[:6])
                updated = str(item.get("modified",""))[:10]
                injected = item["id"] in injected_ids

                with st.container():
                    st.markdown(f"""<div class="esri-card">
                        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px">
                            <span class="pill p-blue">{item.get('type','')}</span>
                            {"<span class='pill p-purple'>Living Atlas</span>" if is_living_atlas else ""}
                            {"<span class='pill p-green'>✓ In KB</span>" if injected else ""}
                        </div>
                        <div style="font-weight:700;color:#dde;margin-bottom:4px">{item.get('title','')}</div>
                        <div style="font-size:10px;color:#555;margin-bottom:4px">{item.get('owner','')} · {updated}</div>
                        <div style="font-size:11px;color:#778;margin-bottom:6px">{(item.get('snippet') or '')[:160]}</div>
                        {f'<div style="font-size:9px;color:#3a3e58">{tags}</div>' if tags else ''}
                    </div>""", unsafe_allow_html=True)

                    col_a, col_b, col_c, col_d = st.columns([2,2,1,1])
                    with col_a:
                        if st.button("⊕ Inspect Metadata", key=f"inspect_{item['id']}", use_container_width=True):
                            with st.spinner("Fetching full metadata…"):
                                full_item, data, err = fetch_item_metadata(item["id"])
                            if err: st.error(f"Error: {err}")
                            else:
                                with st.expander("📋 Full Metadata", expanded=True):
                                    st.markdown(f"**Item ID:** `{full_item.get('id','')}`")
                                    st.markdown(f"**Type:** {full_item.get('type','')}")
                                    st.markdown(f"**Owner:** {full_item.get('owner','')}")
                                    st.markdown(f"**Updated:** {str(full_item.get('modified',''))[:10]}")
                                    st.markdown(f"**Views:** {full_item.get('numViews',0):,}")
                                    if full_item.get("url"): st.markdown(f"**Service URL:** [{full_item['url']}]({full_item['url']})")
                                    st.markdown(f"**Tags:** {', '.join(full_item.get('tags',[]))}")
                                    desc = re.sub(r'<[^>]+>','',full_item.get('description',''))
                                    if desc: st.markdown(f"**Description:** {desc[:800]}")
                                    if full_item.get('extent'): st.markdown(f"**Extent:** {full_item['extent']}")
                                    if data:
                                        if "layers" in data:
                                            st.markdown(f"**Layers ({len(data['layers'])}):** "+", ".join(f"{l.get('id')}:{l.get('name','')}" for l in data["layers"]))
                                        if "operationalLayers" in data:
                                            st.markdown(f"**Operational Layers:** "+", ".join(l.get("title","?") for l in data["operationalLayers"]))
                                        st.json(data, expanded=False)
                                    st.json(full_item, expanded=False)
                    with col_b:
                        if not injected:
                            if st.button("+ Add to KB", key=f"inject_{item['id']}", use_container_width=True):
                                full_item, data, _ = fetch_item_metadata(item["id"])
                                ctx_text = format_item_for_context(full_item or item, data)
                                st.session_state.esri_items.append({"name":f"ESRI: {item.get('title','')}","item_id":item["id"],"content":ctx_text})
                                st.session_state.pending_query = f"I just added the '{item.get('title','')}' layer to the knowledge base. Summarize what this layer contains and how it could support NYC emergency management operations."
                                st.rerun()
                        else:
                            st.button("✓ In KB", key=f"injected_{item['id']}", disabled=True, use_container_width=True)
                    with col_c:
                        st.link_button("↗ AGOL", f"https://www.arcgis.com/home/item.html?id={item['id']}")
                    with col_d:
                        if item.get("url"): st.link_button("↗ Service", item["url"])

    if st.session_state.esri_items:
        st.divider()
        st.markdown(f"**{len(st.session_state.esri_items)} ESRI layer(s) in knowledge base:**")
        for i, ei in enumerate(st.session_state.esri_items):
            c1, c2 = st.columns([5,1])
            with c1: st.markdown(f'<span class="pill p-purple">⊕ {ei["name"][:60]}</span>', unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"rm_esri_{i}"): st.session_state.esri_items.pop(i); st.rerun()

# ── Chat Tab ───────────────────────────────────────────────────────────────────
with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    with st.expander("▸ Quick Queries"):
        qcols = st.columns(2)
        quick = ["Storm surge risk — Lower Manhattan","Zone 1 assets at risk from Cat 2 hurricane","Trauma centers and hospital surge capacity","Current NWS alerts for NYC","Heat emergency protocol thresholds","Flash flood — basement apartment risk","Critical infrastructure in FEMA Zone AE","How can the ESRI layers in my KB support this incident?"]
        for i, q in enumerate(quick):
            if qcols[i%2].button(q, key=f"quick_{i}", use_container_width=True): st.session_state.pending_query=q

    def run_query(prompt):
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        noaa_items = st.session_state.get("noaa_items", [])
        ctx = build_context(st.session_state.files, st.session_state.api_results, active_kb, st.session_state.esri_items, noaa_items)
        msgs = [{"role":m["role"],"content":m["content"]} for m in st.session_state.messages[-10:]]
        with st.chat_message("assistant"):
            ph = st.empty(); full=""
            for token in stream_ollama(msgs, ctx): full+=token; ph.markdown(full+"▋")
            ph.markdown(full)
        st.session_state.messages.append({"role":"assistant","content":full})

    if "pending_query" in st.session_state: run_query(st.session_state.pop("pending_query"))
    if prompt := st.chat_input("Incident type + location, or ask about any ESRI layer in your KB…"): run_query(prompt)
