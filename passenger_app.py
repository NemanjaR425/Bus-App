import streamlit as st
import pd as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps
from datetime import datetime

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
ROUTE_ORDER = ["Igalo (Center)", "Topla", "Main Bus Station (Glavna)", "Meljine", "Zelenika"]

# --- 3. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. SESSION STATE & QR LOGIC ---
query_params = st.query_params
url_station = query_params.get("station")

# Initialize the selection in session state if it doesn't exist
if "selected_station" not in st.session_state:
    if url_station in ROUTE_ORDER:
        st.session_state.selected_station = url_station
    else:
        st.session_state.selected_station = ROUTE_ORDER[0]

# --- 5. INTERFACE ---
st.title("🚌 Herceg Novi Live Bus")

# Callback function to update session state when dropdown is used manually
def on_dropdown_change():
    st.session_state.selected_station = st.session_state.dropdown_key

# The Selectbox: Use 'key' to link it to session state
selected_stop = st.selectbox(
    "Where are you waiting?",
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="dropdown_key",
    on_change=on_dropdown_change
)

# Sync the local variable with session state
current_station = st.session_state.selected_station

# --- 6. MULTI-BUS & ROUTE-AWARE ETA ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    bus_lat, bus_lon = bus['lat'], bus['lon']
    
    # Calculate waypoints up to the CURRENTLY SELECTED station
    target_idx = ROUTE_ORDER.index(current_station)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        res = gmaps.directions(
            origin=(bus_lat, bus_lon),
            destination=(STATIONS[current_station]['lat'], STATIONS[current_station]['lon']),
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

# --- 7. RENDER RESULTS ---
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    next_bus = all_bus_etas[0]
    
    st.metric(f"Next Bus to {current_station}", f"{next_bus['seconds'] // 60} mins")

    # Map Data
    station_markers = pd.DataFrame([{'name': n, 'lat': c['lat'], 'lon': c['lon']} for n, c in STATIONS.items()])
    bus_markers = pd.DataFrame([{'lat': b['lat'], 'lon': b['lon'], 'name': b['id']} for b in all_bus_etas])

    # Highlight the selected station in Red, others in Blue
    station_markers['color'] = station_markers['name'].apply(
        lambda x: [255, 0, 0, 200] if x == current_station else [0, 100, 255, 160]
    )

    view = pdk.ViewState(latitude=42.4572, longitude=18.5283, zoom=12.5)

    s_layer = pdk.Layer(
        "ScatterplotLayer", 
        data=station_markers, 
        id="s-layer", 
        get_position="[lon, lat]", 
        get_color="color", 
        get_radius=150, 
        pickable=True
    )
    
    b_layer = pdk.Layer(
        "IconLayer", 
        data=bus_markers, 
        get_position="[lon, lat]", 
        get_icon=lambda x: {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}, 
        get_size=4, 
        size_scale=15
    )

    map_event = st.pydeck_chart(
        pdk.Deck(layers=[s_layer, b_layer], initial_view_state=view, tooltip={"text": "{name}"}),
        on_select="rerun",
        selection_mode="single-object"
    )

    # Handle Map Clicks: If user clicks a dot, update session state and refresh
    if map_event and map_event.selection:
        selected_objs = map_event.selection.get("objects", {}).get("s-layer")
        if selected_objs:
            clicked_name = selected_objs[0]["name"]
            if clicked_name != st.session_state.selected_station:
                st.session_state.selected_station = clicked_name
                st.rerun()
else:
    st.warning("No buses currently active on Line 1.")
