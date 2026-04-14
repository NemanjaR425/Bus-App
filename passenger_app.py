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
    .stSelectbox { margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INITIALIZATION ---
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error("Firebase Initialization Failed. Check your Secrets.")

db = firestore.client()

try:
    gmaps = googlemaps.Client(key=st.secrets["api_key"])
except Exception as e:
    st.error("Google Maps API Key missing or invalid.")

# Define stations in Herceg Novi
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}

# 🚩 DEFINED ROUTE ORDER (The physical sequence the bus follows)
ROUTE_ORDER = [
    "Igalo (Center)", 
    "Topla", 
    "Main Bus Station (Glavna)", 
    "Meljine", 
    "Zelenika"
]

# --- 3. PASSENGER INTERFACE ---
st.title("🚌 Herceg Novi Live Bus")

st.subheader("Where are you waiting?")
selected_stop = st.selectbox(
    "Select your bus stop:", 
    options=ROUTE_ORDER,
    label_visibility="collapsed"
)

# Fetch Live Bus Location from Firebase
bus_ref = db.collection("buses").document("Line_1").get()

if bus_ref.exists:
    bus_data = bus_ref.to_dict()
    bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
    last_seen = bus_data.get('last_updated')

    # --- 4. ROUTE-AWARE ETA CALCULATION ---
    eta_text = "Calculating..."
    
    try:
        # We use the Directions API to respect the road network
        directions_result = gmaps.directions(
            origin=(bus_lat, bus_lon),
            destination=(STATIONS[selected_stop]['lat'], STATIONS[selected_stop]['lon']),
            mode="driving",
            departure_time="now",
            traffic_model="best_guess"
        )
        
        if directions_result:
            # Extract duration with live traffic
            leg = directions_result[0]['legs'][0]
            # Use duration_in_traffic if available, otherwise standard duration
            eta_text = leg.get('duration_in_traffic', leg['duration'])['text']
        else:
            eta_text = "No Route Found"
            
    except Exception as e:
        eta_text = "API Error"
        st.error(f"Error fetching directions: {e}. Please ensure Directions API is enabled in Google Cloud Console.")

    # Display Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Status", "🟢 Live Tracking")
    m2.metric("Target Stop", selected_stop)
    m3.metric("Arriving In", eta_text)

    # --- 5. MAP DISPLAY ---
    # Create Bus Marker
    bus_df = pd.DataFrame([{
        'lon': bus_lon, 
        'lat': bus_lat, 
        'icon_data': {
            "url": "https://img.icons8.com/color/48/bus.png", 
            "width": 128, "height": 128, "anchorY": 128
        }
    }])
    
    # Create All Stations Markers
    stat_df = pd.DataFrame([
        {'name': n, 'lat': c['lat'], 'lon': c['lon']} 
        for n, c in STATIONS.items()
    ])
    
    view = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
    
    layers = [
        # Blue dots for all stops
        pdk.Layer(
            "ScatterplotLayer", 
            data=stat_df, 
            get_position="[lon, lat]", 
            get_color="[0, 100, 255, 100]", 
            get_radius=100, 
            pickable=True
        ),
        # Red dot for the user's selected stop
        pdk.Layer(
            "ScatterplotLayer", 
            data=pd.DataFrame([STATIONS[selected_stop]]), 
            get_position="[lon, lat]", 
            get_color="[255, 0, 0, 200]", 
            get_radius=180
        ),
        # Bus Icon
        pdk.Layer(
            "IconLayer", 
            data=bus_df, 
            get_position="[lon, lat]", 
            get_icon="icon_data", 
            get_size=4, 
            size_scale=15
        )
    ]
    
    st.pydeck_chart(pdk.Deck(
        layers=layers, 
        initial_view_state=view, 
        tooltip={"text": "{name}"}
    ))
    
    # Refresh logic
    c1, c2 = st.columns([4, 1])
    if last_seen:
        c1.caption(f"Bus last seen at {last_seen.strftime('%H:%M:%S')}")
    if c2.button("Refresh Map 🔄", use_container_width=True):
        st.rerun()

else:
    st.info("Bus Line 1 is currently offline. No driver is broadcasting location data.")
