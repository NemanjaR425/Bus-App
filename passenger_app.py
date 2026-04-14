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
    /* Make the metric labels a bit bolder */
    [data-testid="stMetricLabel"] { font-weight: bold; font-size: 16px; }
    /* Custom styling for the header area */
    .header-container { background-color: #ffffff; padding: 20px; border-radius: 15px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

STATIONS = {
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}

# --- 3. MAIN INTERFACE ---
st.title("🚌 Herceg Novi Live Bus")

# Main Page Selection (Replacing the Sidebar)
st.subheader("Where are you waiting?")
selected_stop = st.selectbox(
    "Select your bus stop for a live ETA:", 
    options=list(STATIONS.keys()),
    label_visibility="collapsed" # Hides the label for a cleaner look since we have a subheader
)
target = STATIONS[selected_stop]

# Fetch Live Bus Data
bus_ref = db.collection("buses").document("Line_1").get()

if bus_ref.exists:
    bus_data = bus_ref.to_dict()
    bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
    last_seen = bus_data.get('last_updated')

    # ETA Calculation
    try:
        matrix = gmaps.distance_matrix(
            (bus_lat, bus_lon), 
            (target['lat'], target['lon']), 
            mode="driving", 
            departure_time="now"
        )
        eta = matrix['rows'][0]['elements'][0]['duration_in_traffic']['text']
    except:
        eta = "Unavailable"

    # Display Metrics in a clean row
    m1, m2, m3 = st.columns(3)
    m1.metric("Bus Status", "🟢 Live Tracking")
    m2.metric("Target Stop", selected_stop)
    m3.metric("Estimated Arrival", eta)

    # --- 4. MAP SETUP ---
    bus_df = pd.DataFrame([{
        'lon': bus_lon, 
        'lat': bus_lat, 
        'icon_data': {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}
    }])
    stat_df = pd.DataFrame([{'name': n, 'lat': c['lat'], 'lon': c['lon']} for n, c in STATIONS.items()])
    
    view = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
    
    layers = [
        # All stations
        pdk.Layer("ScatterplotLayer", data=stat_df, get_position="[lon, lat]", get_color="[0, 100, 255, 100]", get_radius=100, pickable=True),
        # Highlighted selected station
        pdk.Layer("ScatterplotLayer", data=pd.DataFrame([target]), get_position="[lon, lat]", get_color="[255, 0, 0, 200]", get_radius=180),
        # Live Bus
        pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
    ]
    
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name}"}))
    
    # Footer info
    c1, c2 = st.columns([4, 1])
    if last_seen:
        c1.caption(f"Bus last seen at {last_seen.strftime('%H:%M:%S')}")
    if c2.button("Refresh 🔄", use_container_width=True):
        st.rerun()

else:
    st.info("Bus Line 1 is currently offline. Please check back later.")
