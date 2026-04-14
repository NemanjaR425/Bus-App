import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# --- 2. DATA ---
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

# --- 3. INIT ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. STATE MANAGEMENT (The Engine) ---
if "selected_station" not in st.session_state:
    query_params = st.query_params
    url_station = query_params.get("station")
    st.session_state.selected_station = url_station if url_station in ROUTE_ORDER else ROUTE_ORDER[0]

# --- 5. UI COMPONENTS ---
st.title("🚌 Herceg Novi Live Bus")

# Dropdown uses session_state directly as its value source
selected_stop = st.selectbox(
    "Where are you waiting?",
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="manual_selection"
)

# Update state if dropdown is changed manually
if selected_stop != st.session_state.selected_station:
    st.session_state.selected_station = selected_stop
    st.rerun()

# --- 6. BUS DATA & ETA ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    # Route-aware ETA
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
            all_bus_etas.append({
                "id": bus.get('bus_id', 'Bus'), 
                "seconds": seconds, 
                "lat": bus['lat'], 
                "lon": bus['lon']
            })
    except:
        continue

# --- 7. RENDER RESULTS ---
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    next_bus = all_bus_etas[0]
    st.metric(f"Next Bus to {st.session_state.selected_station}", f"{next_bus['seconds'] // 60} mins")
else:
    st.warning("No active buses found.")

# --- 8. THE INTERACTIVE MAP ---
# Station Markers
station_df = pd.DataFrame([
    {
        'name': n, 'lat': c['lat'], 'lon': c['lon'], 
        'color': [255, 0, 0, 230] if n == st.session_state.selected_station else [0, 100, 255, 160]
    } for n, c in STATIONS.items()
])

# Bus Markers (Fixed the Icon logic)
bus_df = pd.DataFrame(all_bus_etas) if all_bus_etas else pd.DataFrame(columns=['lat', 'lon', 'id'])
# Add icon data explicitly to the dataframe
if not bus_df.empty:
    bus_df['icon_data'] = [
        {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128} 
        for _ in range(len(bus_df))
    ]

view = pdk.ViewState(latitude=42.4572, longitude=18.5283, zoom=12.5)

s_layer = pdk.Layer(
    "ScatterplotLayer", 
    data=station_df, 
    id="s-layer", 
    get_position="[lon, lat]", 
    get_color="color", 
    get_radius=150, 
    pickable=True
)

b_layer = pdk.Layer(
    "IconLayer", 
    data=bus_df, 
    id="b-layer",
    get_position="[lon, lat]", 
    get_icon="icon_data", 
    get_size=5, 
    size_scale=15
)

# Use st.pydeck_chart to capture selection
map_selection = st.pydeck_chart(
    pdk.Deck(layers=[s_layer, b_layer], initial_view_state=view, tooltip={"text": "{name}"}),
    on_select="rerun",
    selection_mode="single-object"
)

# HANDLE THE CLICK EVENT
if map_selection and map_selection.selection:
    # Check if a station was clicked
    objects = map_selection.selection.get("objects", {}).get("s-layer")
    if objects:
        clicked_station = objects[0]["name"]
        if clicked_station != st.session_state.selected_station:
            st.session_state.selected_station = clicked_station
            st.rerun()
