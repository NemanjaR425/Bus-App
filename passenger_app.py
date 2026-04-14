import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #1f77b4; }
    </style>
    """, unsafe_allow_html=True)

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

ROUTE_ORDER = ["Igalo (Center)", "Topla", "Main Bus Station (Glavna)", "Meljine", "Zelenika"]

# --- 3. QR / URL PARAMETER LOGIC ---
# This reads the URL to see if a station was scanned (e.g. ?station=Topla)
query_params = st.query_params
url_station = query_params.get("station")

# Determine which station the dropdown should highlight by default
if url_station in ROUTE_ORDER:
    initial_index = ROUTE_ORDER.index(url_station)
else:
    initial_index = 0

# --- 4. MAIN INTERFACE ---
st.title("🚌 Herceg Novi Live Bus")

st.subheader("Plan your departure")
# The dropdown is ALWAYS visible and allows manual selection override
selected_stop = st.selectbox(
    "Check arrival time for:", 
    options=ROUTE_ORDER, 
    index=initial_index,
    help="Select a station to see how long until the bus arrives there."
)

# Visual confirmation if they scanned a QR code
if url_station and url_station == selected_stop:
    st.info(f"📍 QR Scan Detected: Showing times for {url_station}")

# --- 5. DATA & ROUTE-AWARE ETA ---
bus_ref = db.collection("buses").document("Line_1").get()

if bus_ref.exists:
    bus_data = bus_ref.to_dict()
    bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
    last_seen = bus_data.get('last_updated')

    # Build waypoints for the pre-defined route order
    target_idx = ROUTE_ORDER.index(selected_stop)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        directions_result = gmaps.directions(
            origin=(bus_lat, bus_lon),
            destination=(STATIONS[selected_stop]['lat'], STATIONS[selected_stop]['lon']),
            waypoints=route_waypoints,
            optimize_waypoints=False,
            mode="driving",
            departure_time="now"
        )
        
        if directions_result:
            total_seconds = sum(leg.get('duration_in_traffic', leg['duration'])['value'] for leg in directions_result[0]['legs'])
            eta_text = f"{total_seconds // 60} mins"
        else:
            eta_text = "Route finding..."
    except:
        eta_text = "API Error"

    # Metrics Display
    m1, m2, m3 = st.columns(3)
    m1.metric("Line", "Line 1 (Eastbound)")
    m2.metric("Target Station", selected_stop)
    m3.metric("Estimated Arrival", eta_text)

    # --- 6. MAP ---
    view = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
    bus_marker = pd.DataFrame([{
        'lon': bus_lon, 'lat': bus_lat, 
        'icon_data': {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}
    }])
    
    st.pydeck_chart(pdk.Deck(
        layers=[
            # All stations (Blue)
            pdk.Layer("ScatterplotLayer", data=pd.DataFrame([{'lat': c['lat'], 'lon': c['lon']} for c in STATIONS.values()]), get_position="[lon, lat]", get_color="[0, 100, 255, 100]", get_radius=100),
            # Selected station (Red)
            pdk.Layer("ScatterplotLayer", data=pd.DataFrame([STATIONS[selected_stop]]), get_position="[lon, lat]", get_color="[255, 0, 0, 200]", get_radius=180),
            # Live Bus
            pdk.Layer("IconLayer", data=bus_marker, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
        ], 
        initial_view_state=view,
        tooltip={"text": "Bus Location"}
    ))
    
    if st.button("Manual Refresh 🔄", use_container_width=True):
        st.rerun()
else:
    st.info("Bus is currently not broadcasting. Please check later.")
