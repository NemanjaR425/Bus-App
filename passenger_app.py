import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# --- 2. DATA DEFINITIONS ---
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

# --- 3. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. SESSION STATE LOGIC ---
# This is the "Source of Truth"
if "selected_station" not in st.session_state:
    query_params = st.query_params
    url_station = query_params.get("station")
    st.session_state.selected_station = url_station if url_station in ROUTE_ORDER else ROUTE_ORDER[0]

# --- 5. INTERFACE ---
st.title("🚌 Herceg Novi Live Bus")

# We create the selectbox. We DON'T use a dynamic key here to prevent flickering.
# Instead, we use the 'index' to force it to follow the session state.
selected_stop = st.selectbox(
    "Where are you waiting?",
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="manual_dropdown"
)

# If the user manually changes the dropdown, update the state
if selected_stop != st.session_state.selected_station:
    st.session_state.selected_station = selected_stop
    st.rerun()

# --- 6. MULTI-BUS & ETA CALCULATION ---
# This runs every time the app reruns (on click or dropdown change)
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    target_idx = ROUTE_ORDER.index(st.session_state.selected_station)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        res = gmaps.directions(
            origin=(bus['lat'], bus['lon']),
            destination=(STATIONS[st.session_state.selected_station]['lat'], STATIONS[st.session_state.selected_station]['lon']),
            waypoints=route_waypoints,
            optimize_waypoints=False,
            mode="driving",
            departure_time="now"
        )
        if res:
            seconds = sum(l.get('duration_in_traffic', l['duration'])['value'] for l in res[0]['legs'])
            all_bus_etas.append({"id": bus['bus_id'], "seconds": seconds, "lat": bus['lat'], "lon": bus['lon']})
    except:
        continue

# --- 7. RENDER RESULTS & MAP ---
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    next_bus = all_bus_etas[0]
    st.metric(f"Next Bus to {st.session_state.selected_station}", f"{next_bus['seconds'] // 60} mins")

# Map markers
station_markers = pd.DataFrame([
    {
        'name': n, 'lat': c['lat'], 'lon': c['lon'], 
        'color': [255, 0, 0, 200] if n == st.session_state.selected_station else [0, 100, 255, 160]
    } for n, c in STATIONS.items()
])

view = pdk.ViewState(latitude=42.4572, longitude=18.5283, zoom=12.5)
s_layer = pdk.Layer("ScatterplotLayer", data=station_markers, id="s-layer", get_position="[lon, lat]", get_color="color", get_radius=150, pickable=True)
b_layer = pdk.Layer("IconLayer", data=pd.DataFrame(all_bus_etas), get_position="[lon, lat]", get_icon=lambda x: {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}, get_size=4, size_scale=15)

# THE MAP EVENT
map_event = st.pydeck_chart(
    pdk.Deck(layers=[s_layer, b_layer], initial_view_state=view, tooltip={"text": "{name}"}),
    on_select="rerun",
    selection_mode="single-object"
)

# CRITICAL FIX: The logic to catch the click and force the rerun
if map_event and map_event.selection:
    selected_objs = map_event.selection.get("objects", {}).get("s-layer")
    if selected_objs:
        clicked_name = selected_objs[0]["name"]
        # Only rerun if the selection actually changed
        if clicked_name != st.session_state.selected_station:
            st.session_state.selected_station = clicked_name
            st.rerun()
