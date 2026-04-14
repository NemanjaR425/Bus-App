import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# --- 2. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}

# 🚩 THE PRE-DEFINED ROUTE SEQUENCE
ROUTE_ORDER = [
    "Igalo (Center)", 
    "Topla", 
    "Main Bus Station (Glavna)", 
    "Meljine", 
    "Zelenika"
]

st.title("🚌 Herceg Novi Live Bus")

st.subheader("Where are you waiting?")
selected_stop = st.selectbox("Select your bus stop:", options=ROUTE_ORDER, label_visibility="collapsed")

bus_ref = db.collection("buses").document("Line_1").get()

if bus_ref.exists:
    bus_data = bus_ref.to_dict()
    bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
    
    # --- 3. THE "ROUTE-FIX" LOGIC ---
    # We find where the user is in the route
    target_idx = ROUTE_ORDER.index(selected_stop)
    
    # We build a list of all stops the bus must visit BEFORE reaching the user
    # This forces the "Pre-Defined Route" behavior.
    route_waypoints = []
    for i in range(target_idx):
        stop_name = ROUTE_ORDER[i]
        coords = STATIONS[stop_name]
        route_waypoints.append(f"{coords['lat']},{coords['lon']}")

    try:
        # Use directions with waypoints to force the route
        directions_result = gmaps.directions(
            origin=(bus_lat, bus_lon),
            destination=(STATIONS[selected_stop]['lat'], STATIONS[selected_stop]['lon']),
            waypoints=route_waypoints, 
            optimize_waypoints=False, # CRITICAL: Do NOT let Google re-order our stops
            mode="driving",
            departure_time="now"
        )
        
        if directions_result:
            # Sum the duration of every "leg" of the journey
            # Leg 1: Bus to first waypoint, Leg 2: Waypoint to Waypoint, etc.
            total_seconds = sum(
                leg.get('duration_in_traffic', leg['duration'])['value'] 
                for leg in directions_result[0]['legs']
            )
            eta_text = f"{total_seconds // 60} mins"
        else:
            eta_text = "No Route"
    except Exception as e:
        eta_text = "API Error"
        st.error(f"Error: {e}")

    # --- 4. DISPLAY ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Status", "🟢 Live")
    m2.metric("Target", selected_stop)
    m3.metric("Arriving In", eta_text)

    # Map setup (same as before)
    view = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
    bus_df = pd.DataFrame([{'lon': bus_lon, 'lat': bus_lat, 'icon_data': {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}}])
    stat_df = pd.DataFrame([{'name': n, 'lat': c['lat'], 'lon': c['lon']} for n, c in STATIONS.items()])
    
    layers = [
        pdk.Layer("ScatterplotLayer", data=stat_df, get_position="[lon, lat]", get_color="[0, 100, 255, 100]", get_radius=100),
        pdk.Layer("ScatterplotLayer", data=pd.DataFrame([STATIONS[selected_stop]]), get_position="[lon, lat]", get_color="[255, 0, 0, 200]", get_radius=180),
        pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
    ]
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name}"}))
    
    if st.button("Refresh 🔄"):
        st.rerun()
