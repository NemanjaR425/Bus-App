import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps
from datetime import datetime

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# --- 2. DATA DEFINITIONS (Move this UP to avoid NameError) ---
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}

ROUTE_ORDER = ["Igalo (Center)", "Topla", "Main Bus Station (Glavna)", "Meljine", "Zelenika"]

# --- 3. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. QR & SESSION STATE LOGIC ---
query_params = st.query_params
url_station = query_params.get("station")

# Check if we have a station in the URL, otherwise default to the first one
if "selected_station" not in st.session_state:
    if url_station in ROUTE_ORDER:
        st.session_state.selected_station = url_station
    else:
        st.session_state.selected_station = ROUTE_ORDER[0]

# --- 5. MAIN INTERFACE ---
st.title("🚌 Herceg Novi Live Bus")

# Dropdown linked to session state
selected_stop = st.selectbox(
    "Where are you waiting?",
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="station_dropdown"
)

# If the dropdown changes, update the session state
if selected_stop != st.session_state.selected_station:
    st.session_state.selected_station = selected_stop
    st.rerun()

# --- 6. MULTI-BUS & ETA LOGIC ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    bus_lat, bus_lon = bus['lat'], bus['lon']
    
    # Pre-defined route calculation
    target_idx = ROUTE_ORDER.index(selected_stop)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        res = gmaps.directions(
            origin=(bus_lat, bus_lon),
            destination=(STATIONS[selected_stop]['lat'], STATIONS[selected_stop]['lon']),
            waypoints=route_waypoints,
            optimize_waypoints=False,
            mode="driving",
            departure_time="now"
        )
        if res:
            seconds = sum(l.get('duration_in_traffic', l['duration'])['value'] for l in res[0]['legs'])
            all_bus_etas.append({"id": bus['bus_id'], "seconds": seconds, "lat": bus_lat, "lon": bus_lon})
    except:
        continue

# --- 7. RENDER METRICS & INTERACTIVE MAP ---
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    next_bus = all_bus_etas[0]
    
    st.metric("Next Arrival", f"{next_bus['seconds'] // 60} mins")

    # Map Markers
    bus_markers = pd.DataFrame([{
        'lon': b['lon'], 'lat': b['lat'], 'name': b['id'],
        'icon_data': {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}
    } for b in all_bus_etas])

    station_markers = pd.DataFrame([
        {'name': n, 'lat': c['lat'], 'lon': c['lon']} for n, c in STATIONS.items()
    ])

    view = pdk.ViewState(latitude=42.4572, longitude=18.5283, zoom=12)

    # Layers
    s_layer = pdk.Layer("ScatterplotLayer", data=station_markers, id="s-layer", get_position="[lon, lat]", get_color="[0, 100, 255, 160]", get_radius=150, pickable=True)
    b_layer = pdk.Layer("IconLayer", data=bus_markers, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)

    # Render Map with Selection
    map_event = st.pydeck_chart(
        pdk.Deck(layers=[s_layer, b_layer], initial_view_state=view, tooltip={"text": "{name}"}),
        on_select="rerun",
        selection_mode="single-object"
    )

    # Handle Map Clicks
    if map_event and map_event.selection:
        selected_objs = map_event.selection.get("objects", {}).get("s-layer")
        if selected_objs:
            new_selection = selected_objs[0]["name"]
            if new_selection != st.session_state.selected_station:
                st.session_state.selected_station = new_selection
                st.rerun()
else:
    st.warning("No buses currently active.")
