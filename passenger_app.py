import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps
from datetime import datetime

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #1f77b4; font-weight: bold; }
    .stSelectbox { margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INITIALIZATION ---
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error("Firebase Auth Error. Check your secrets.")

db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# Station Database
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}

# Pre-defined Route Order
ROUTE_ORDER = ["Igalo (Center)", "Topla", "Main Bus Station (Glavna)", "Meljine", "Zelenika"]

# --- 3. QR / URL PARAMETER LOGIC ---
query_params = st.query_params
url_station = query_params.get("station")

initial_index = 0
if url_station in ROUTE_ORDER:
    initial_index = ROUTE_ORDER.index(url_station)

# --- 4. PASSENGER INTERFACE ---
st.title("🚌 Herceg Novi Live Bus")

st.subheader("Where are you waiting?")
selected_stop = st.selectbox(
    "Select a station to see next arrival:", 
    options=ROUTE_ORDER, 
    index=initial_index,
    label_visibility="collapsed"
)

# --- 5. MULTI-BUS LOGIC ---
# Fetch all buses currently broadcasting on Line 1
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()

all_bus_etas = []
target_coords = STATIONS[selected_stop]

for doc in buses_ref:
    bus = doc.to_dict()
    bus_lat, bus_lon = bus['lat'], bus['lon']
    
    # Building the specific route waypoints for this bus to reach the user
    target_idx = ROUTE_ORDER.index(selected_stop)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        directions_result = gmaps.directions(
            origin=(bus_lat, bus_lon),
            destination=(target_coords['lat'], target_coords['lon']),
            waypoints=route_waypoints,
            optimize_waypoints=False,
            mode="driving",
            departure_time="now"
        )
        
        if directions_result:
            # Sum up durations for all segments of the route
            total_seconds = sum(
                leg.get('duration_in_traffic', leg['duration'])['value'] 
                for leg in directions_result[0]['legs']
            )
            all_bus_etas.append({
                "id": bus['bus_id'],
                "seconds": total_seconds,
                "lat": bus_lat,
                "lon": bus_lon,
                "last_seen": bus['last_updated']
            })
    except:
        continue

# --- 6. RENDER RESULTS ---
if all_bus_etas:
    # Sort by who arrives first
    all_bus_etas.sort(key=lambda x: x['seconds'])
    next_bus = all_bus_etas[0]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Buses Active", len(all_bus_etas))
    m2.metric("Target Station", selected_stop)
    m3.metric("Next Arrival", f"{next_bus['seconds'] // 60} mins")

    # Prepare Map Markers
    bus_markers = []
    for b in all_bus_etas:
        # Use a different color/icon for the absolute next bus
        icon_url = "https://img.icons8.com/color/48/bus.png" if b['id'] == next_bus['id'] else "https://img.icons8.com/plasticine/48/bus.png"
        bus_markers.append({
            'lon': b['lon'], 'lat': b['lat'], 'name': b['id'],
            'icon_data': {"url": icon_url, "width": 128, "height": 128, "anchorY": 128}
        })

    view = pdk.ViewState(latitude=42.4531, longitude=18.5375, zoom=12.5)
    
    layers = [
        # All Stations
        pdk.Layer("ScatterplotLayer", data=pd.DataFrame([{'lat': c['lat'], 'lon': c['lon'], 'name': n} for n, c in STATIONS.items()]), get_position="[lon, lat]", get_color="[0, 100, 255, 100]", get_radius=120),
        # Destination Highlight
        pdk.Layer("ScatterplotLayer", data=pd.DataFrame([target_coords]), get_position="[lon, lat]", get_color="[255, 0, 0, 200]", get_radius=200),
        # All Buses
        pdk.Layer("IconLayer", data=pd.DataFrame(bus_markers), get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
    ]
    
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name}"}))
    
    st.caption(f"Showing the closest of {len(all_bus_etas)} active buses. Data refreshes on interaction.")
    if st.button("Refresh Live Map 🔄", use_container_width=True):
        st.rerun()
else:
    st.warning("No buses are currently broadcasting on Line 1. Please check the official schedule.")
    # Show static map of stations anyway
    st.map(pd.DataFrame([{'lat': c['lat'], 'lon': c['lon']} for c in STATIONS.values()]))
