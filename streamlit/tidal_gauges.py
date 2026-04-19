"""
tidal_gauges.py — NOAA CO-OPS tidal gauge live feed for EMBER

All free, no API key required. Data updates every 6 minutes from CO-OPS.

Key endpoints:
  Metadata API:  https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/
  Data API:      https://api.tidesandcurrents.noaa.gov/api/prod/datagetter
  Chart embeds:  https://tidesandcurrents.noaa.gov/stationhome.html?id={station_id}

NYC key stations:
  8518750  The Battery, Manhattan  (primary surge gauge)
  8516945  Kings Point, Long Island Sound
  8531680  Sandy Hook, NJ
  8510560  Montauk, NY
  8518995  Governors Island, NY
  8517741  Bergen Point West Reach, NJ
"""

import requests
import datetime as _dt

COOPS_DATA_API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
COOPS_META_API = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
APP_NAME       = "EMBER"

# ── Flood threshold reference levels (ft MLLW) for each station ───────────────
# Based on NWS and CO-OPS flood stage definitions for NYC-area stations.
# action = advisory, minor = nuisance flooding, moderate = significant, major = severe
FLOOD_THRESHOLDS = {
    "8518750": {"name": "The Battery",   "action": 4.5,  "minor": 5.5,  "moderate": 6.5,  "major": 8.5},
    "8516945": {"name": "Kings Point",   "action": 4.5,  "minor": 5.5,  "moderate": 6.5,  "major": 8.5},
    "8531680": {"name": "Sandy Hook",    "action": 4.5,  "minor": 5.5,  "moderate": 6.5,  "major": 8.5},
    "8510560": {"name": "Montauk",       "action": 3.5,  "minor": 4.5,  "moderate": 5.5,  "major": 7.0},
    "8518995": {"name": "Governors Is.", "action": 4.5,  "minor": 5.5,  "moderate": 6.5,  "major": 8.5},
    "8517741": {"name": "Bergen Point",  "action": 4.5,  "minor": 5.5,  "moderate": 6.5,  "major": 8.5},
}

def get_flood_status(station_id: str, level_ft: float) -> dict:
    """Return flood status dict for a given station and water level."""
    thresh = FLOOD_THRESHOLDS.get(station_id, {"action": 4.5, "minor": 5.5, "moderate": 6.5, "major": 8.5})
    if   level_ft >= thresh["major"]:    status, color = "MAJOR FLOOD",    "#dc2626"
    elif level_ft >= thresh["moderate"]: status, color = "MODERATE FLOOD", "#f87171"
    elif level_ft >= thresh["minor"]:    status, color = "MINOR FLOOD",    "#fb923c"
    elif level_ft >= thresh["action"]:   status, color = "ACTION STAGE",   "#facc15"
    else:                                status, color = "NORMAL",          "#4ade80"
    return {"status": status, "color": color, "level_ft": level_ft,
            "thresholds": thresh, "pct_to_minor": min(100, (level_ft / thresh["minor"]) * 100)}


def fetch_station_list(state: str = "NY") -> list[dict]:
    """
    Fetch all active CO-OPS water level stations for a state.
    Returns list of {id, name, lat, lng, state} dicts.
    """
    try:
        r = requests.get(
            f"{COOPS_META_API}/stations.json",
            params={"type": "waterlevels", "state": state},
            timeout=10, headers={"User-Agent": "EMBER/1.0"}
        )
        r.raise_for_status()
        stations = r.json().get("stations", [])
        return [
            {
                "id":    s["id"],
                "name":  s["name"],
                "lat":   float(s.get("lat", 0)),
                "lng":   float(s.get("lng", 0)),
                "state": s.get("state", state),
            }
            for s in stations
            if s.get("lat") and s.get("lng")
        ]
    except Exception as e:
        return []


def fetch_water_level(station_id: str) -> dict | None:
    """
    Fetch the most recent water level reading for a station.
    Returns dict with current level, trend, quality flag.
    Uses 'recent' (last hour) to get trend calculation.
    """
    try:
        r = requests.get(
            COOPS_DATA_API,
            params={
                "date":        "recent",
                "station":     station_id,
                "product":     "water_level",
                "datum":       "MLLW",
                "time_zone":   "lst_ldt",
                "units":       "english",
                "format":      "json",
                "application": APP_NAME,
            },
            timeout=10, headers={"User-Agent": "EMBER/1.0"}
        )
        r.raise_for_status()
        d    = r.json()
        vals = d.get("data", [])
        if not vals:
            return None

        latest  = vals[-1]
        prev    = vals[-2] if len(vals) >= 2 else None
        level   = float(latest["v"]) if latest.get("v") else None
        if level is None:
            return None

        trend_val = None
        trend_str = "—"
        if prev and prev.get("v"):
            delta     = level - float(prev["v"])
            trend_val = round(delta, 3)
            trend_str = f"{'↑' if delta >= 0 else '↓'} {abs(delta):.3f} ft/6min"

        meta = d.get("metadata", {})
        flood = get_flood_status(station_id, level)

        return {
            "station_id":  station_id,
            "station_name":meta.get("name", ""),
            "level_ft":    round(level, 2),
            "trend_ft":    trend_val,
            "trend_str":   trend_str,
            "timestamp":   latest.get("t", ""),
            "quality":     latest.get("q", ""),
            "lat":         float(meta.get("lat", 0)),
            "lng":         float(meta.get("lon", 0)),
            **flood,
        }
    except Exception as e:
        return None


def fetch_predictions(station_id: str, hours: int = 48) -> list[dict]:
    """
    Fetch high/low tide predictions for the next N hours.
    Returns list of {type, level_ft, time} sorted ascending.
    """
    try:
        r = requests.get(
            COOPS_DATA_API,
            params={
                "date":        "today",
                "range":       str(hours),
                "station":     station_id,
                "product":     "predictions",
                "datum":       "MLLW",
                "time_zone":   "lst_ldt",
                "interval":    "hilo",
                "units":       "english",
                "format":      "json",
                "application": APP_NAME,
            },
            timeout=10, headers={"User-Agent": "EMBER/1.0"}
        )
        r.raise_for_status()
        preds = r.json().get("predictions", [])
        return [
            {
                "type":     "HIGH" if p["type"] == "H" else "low",
                "level_ft": float(p["v"]),
                "time":     p["t"],
                "is_high":  p["type"] == "H",
            }
            for p in preds
        ]
    except Exception:
        return []


def fetch_gauge_full(station_id: str) -> dict:
    """
    Fetch both live level and next predictions for a station.
    Returns combined dict ready for map popup rendering.
    """
    level = fetch_water_level(station_id)
    preds = fetch_predictions(station_id, hours=48)

    next_high = next((p for p in preds if p["is_high"]),  None)
    next_low  = next((p for p in preds if not p["is_high"]), None)

    chart_url = f"https://tidesandcurrents.noaa.gov/stationhome.html?id={station_id}"
    api_url   = (f"{COOPS_DATA_API}?date=recent&station={station_id}"
                 f"&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json")

    return {
        "station_id":  station_id,
        "chart_url":   chart_url,
        "api_url":     api_url,
        "level":       level,
        "predictions": preds,
        "next_high":   next_high,
        "next_low":    next_low,
        "fetched_at":  _dt.datetime.now().strftime("%H:%M:%S"),
    }


def fetch_all_ny_gauges(station_ids: list[str] | None = None) -> dict[str, dict]:
    """
    Fetch live data for a list of station IDs (or the default NYC set).
    Returns dict keyed by station_id.
    """
    if station_ids is None:
        station_ids = list(FLOOD_THRESHOLDS.keys())

    results = {}
    for sid in station_ids:
        results[sid] = fetch_gauge_full(sid)
    return results


def build_gauge_popup(gauge_data: dict, station_meta: dict | None = None) -> str:
    """
    Build an HTML popup for a tidal gauge Folium/Leaflet marker.
    Includes: live level, flood status bar, trend, next HIGH/LOW, chart link.
    """
    level_data = gauge_data.get("level")
    next_high  = gauge_data.get("next_high")
    next_low   = gauge_data.get("next_low")
    chart_url  = gauge_data.get("chart_url", "#")
    ts         = gauge_data.get("fetched_at", "?")
    sid        = gauge_data.get("station_id", "")

    # Station name from level data or meta
    name = (level_data.get("station_name") if level_data else None) or \
           (station_meta.get("name") if station_meta else None) or sid

    if not level_data:
        return (f'<div style="font-family:monospace;font-size:11px;min-width:180px">'
                f'<b style="color:#4ade80">📡 {name}</b><br>'
                f'<span style="color:#556">No data available</span><br>'
                f'<a href="{chart_url}" target="_blank" style="color:#60a5fa;font-size:9px">↗ NOAA Chart</a>'
                f'</div>')

    lft      = level_data["level_ft"]
    color    = level_data["color"]
    status   = level_data["status"]
    trend    = level_data["trend_str"]
    thresh   = level_data.get("thresholds", {})
    pct      = min(100, level_data.get("pct_to_minor", 0))

    # Build a tiny inline progress bar showing level vs flood stage
    bar_fill  = f'background:{color};width:{pct:.0f}%;height:6px;border-radius:3px;display:inline-block'
    bar_track = 'background:#1a1e28;width:100%;height:6px;border-radius:3px;margin:4px 0'

    next_high_str = f"{next_high['level_ft']:.2f}ft @ {next_high['time']}" if next_high else "—"
    next_low_str  = f"{next_low['level_ft']:.2f}ft @ {next_low['time']}"   if next_low  else "—"

    minor_thresh = thresh.get("minor", "—")
    major_thresh = thresh.get("major", "—")

    return f"""<div style="font-family:monospace;font-size:11px;min-width:220px;max-width:260px">
  <div style="font-weight:700;color:{color};margin-bottom:4px;font-size:12px">📡 {name}</div>
  <div style="color:#556;font-size:9px;margin-bottom:6px">Station {sid} · CO-OPS · @ {ts}</div>

  <div style="font-size:18px;font-weight:700;color:{color};margin-bottom:2px">
    {lft:.2f} ft <span style="font-size:10px">MLLW</span>
  </div>
  <div style="font-size:10px;color:{color};margin-bottom:4px">
    {status} &nbsp;·&nbsp; {trend}
  </div>

  <div style="{bar_track}"><div style="{bar_fill}"></div></div>
  <div style="font-size:8px;color:#446;margin-bottom:8px">
    Minor flood: {minor_thresh}ft &nbsp;|&nbsp; Major flood: {major_thresh}ft
  </div>

  <div style="border-top:1px solid #1e2a40;padding-top:6px;margin-bottom:6px">
    <div style="color:#aab;margin-bottom:2px">
      ▲ Next HIGH: <b style="color:#60a5fa">{next_high_str}</b>
    </div>
    <div style="color:#aab">
      ▼ Next low:  <b style="color:#778">{next_low_str}</b>
    </div>
  </div>

  <div style="border-top:1px solid #1e2a40;padding-top:5px">
    <a href="{chart_url}" target="_blank"
       style="color:#60a5fa;font-size:9px;text-decoration:none">
      ↗ View 48h chart on NOAA Tides & Currents
    </a>
  </div>
</div>"""


# ── Convenience: marker color from gauge data ─────────────────────────────────
def gauge_marker_color(gauge_data: dict) -> str:
    level_data = gauge_data.get("level")
    if not level_data:
        return "#4ade80"
    return level_data.get("color", "#4ade80")
