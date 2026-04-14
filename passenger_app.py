import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG & DATA ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

# --- 2. INIT ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 3. THE STATE ENGINE (CRITICAL ORDER) ---
if "selected_station" not in st.session_state:
    qp = st.query_params
    st.session_state.selected_station = qp.get("station") if qp.get("station") in ROUTE_ORDER else ROUTE_ORDER[0]

# --- 4. UI: THE DROPDOWN ---
st.title("🚌 Herceg Novi Live Bus")

# We use the 'key' to allow manual changes to update state immediately
selected_stop = st.selectbox(
    "Where are you waiting?",
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="station_selector"
)

# If dropdown changes, update the 'source of truth'
if selected_stop != st.session_state.selected_station:
    st.session_state.selected_station = selected_stop
    st.rerun()

# --- 5. DATA FETCHING & ETA ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    target = st.session_state.selected_station
    target_idx = ROUTE_ORDER.index(target)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        res = gmaps.directions(
            origin=(bus['lat'], bus['lon']),
            destination=(STATIONS[target]['lat'], STATIONS[target]['lon']),
            waypoints=route_waypoints,
            optimize_waypoints=False,
            mode="driving",
            departure_time="now"
        )
        if res:
            seconds = sum(l.get('duration_in_traffic', l['duration'])['value'] for l in res[0]['legs'])
            all_bus_etas.append({"id": bus.get('bus_id'), "seconds": seconds, "lat": bus['lat'], "lon": bus['lon']})
    except:
        continue

# Display Metric
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"Next Bus to {st.session_state.selected_station}", f"{all_bus_etas[0]['seconds'] // 60} mins")
else:
    st.warning("No buses active.")

# --- 6. THE MAP ---
station_df = pd.DataFrame([
    {
        'name': n, 'lat': c['lat'], 'lon': c['lon'], 
        'color': [255, 0, 0, 255] if n == st.session_state.selected_station else [0, 100, 255, 160]
    } for n, c in STATIONS.items()
])

bus_df = pd.DataFrame(all_bus_etas)
if not bus_df.empty:
    bus_df['icon_data'] = [{"url": "https://img.icons8.com/color/48/bus.png", "width": 100, "height": 100, "anchorY": 100} for _ in range(len(bus_df))]

view = pdk.ViewState(latitude=42.4572, longitude=18.5283, zoom=12.5)

# Layer definitions
s_layer = pdk.Layer("ScatterplotLayer", data=station_df, id="stops", get_position="[lon, lat]", get_color="color", get_radius=180, pickable=True)
b_layer = pdk.Layer("IconLayer", data=bus_df, id="buses", get_position="[lon, lat]", get_icon="icon_data", get_size=5, size_scale=15)

# Render Map
map_data = st.pydeck_chart(
    pdk.Deck(layers=[s_layer, b_layer], initial_view_state=view, tooltip={"text": "{name}"}),
    on_select="rerun",
    selection_mode="single-object"
)

# --- 7. HANDLE MAP CLICK (AT THE END) ---
if map_data and map_data.selection:
    # Check specifically for our 'stops' layer
    selected_objs = map_data.selection.get("objects", {}).get("stops")
    if selected_objs:
        new_pick = selected_objs[0]["name"]
        if new_pick != st.session_state.selected_station:
            st.session_state.selected_station = new_pick
            st.rerun()
