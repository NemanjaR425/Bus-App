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

# Define stations with coordinates
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}

# 🚩 DEFINED ROUTE ORDER (Eastbound Example)
ROUTE_ORDER = [
    "Igalo (Center)", 
    "Topla", 
    "Main Bus Station (Glavna)", 
    "Meljine", 
    "Zelenika"
]

st.title("🚌 Herceg Novi Live Bus")

# Main Page Selection
st.subheader("Where are you waiting?")
selected_stop = st.selectbox(
    "Select your bus stop:", 
    options=ROUTE_ORDER,
    label_visibility="collapsed"
)

# Fetch Live Bus Data
bus_ref = db.collection("buses").document("Line_1").get()

if bus_ref.exists:
    bus_data = bus_ref.to_dict()
    bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
    
    # --- 3. ROUTE LOGIC ---
    # Find the index of the user's selected stop
    target_idx = ROUTE_ORDER.index(selected_stop)
    
    # Create the list of stops the bus MUST visit to get to the user
    # Note: This simple version assumes the bus is moving through the list in order.
    waypoints = []
    for stop_name in ROUTE_ORDER:
        # If we haven't reached the user's stop yet, add it as a waypoint
        # You could add logic here to check if the bus has already passed a stop
        stop_coords = STATIONS[stop_name]
        waypoints.append(f"{stop_coords['lat']},{stop_coords['lon']}")
        if stop_name == selected_stop:
            break

    # --- 4. CALCULATE ETA VIA ROUTE ---
    try:
        # We use directions instead of distance_matrix for complex waypoint routing
        directions_result = gmaps.directions(
            origin=(bus_lat, bus_lon),
            destination=(STATIONS[selected_stop]['lat'], STATIONS[selected_stop]['lon']),
            waypoints=waypoints[:-1], # All stops before the final destination
            optimize_waypoints=False, # Keep our predefined order!
            mode="driving",
            departure_time="now"
        )
        
        # Sum up the duration of all legs of the journey
        total_seconds = sum(leg['duration_in_traffic']['value'] for leg in directions_result[0]['legs'])
        eta_minutes = total_seconds // 60
        eta_text = f"{eta_minutes} mins"
    except:
        eta_text = "Calculated via direct road" # Fallback if routing fails

    # Display Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Bus Status", "🟢 On Route")
    m2.metric("Target Stop", selected_stop)
    m3.metric("Estimated Arrival", eta_text)

    # --- 5. MAP ---
    bus_df = pd.DataFrame([{'lon': bus_lon, 'lat': bus_lat, 'icon_data': {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}}])
    stat_df = pd.DataFrame([{'name': n, 'lat': c['lat'], 'lon': c['lon']} for n, c in STATIONS.items()])
    
    view = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
    layers = [
        pdk.Layer("ScatterplotLayer", data=stat_df, get_position="[lon, lat]", get_color="[0, 100, 255, 100]", get_radius=100),
        pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
    ]
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name}"}))
    
    if st.button("Refresh 🔄", use_container_width=True):
        st.rerun()
else:
    st.info("Bus Line 1 is currently offline.")
