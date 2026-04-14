import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# Styling
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { font-size: 28px; color: #1f77b4; }
    </style>
    """, unsafe_allow_html=True)

# Init Firebase & Gmaps
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

st.title("🚌 Herceg Novi Live Bus")

# Sidebar Controls
st.sidebar.header("Navigation")
selected_stop = st.sidebar.selectbox("Where are you waiting?", list(STATIONS.keys()))
target = STATIONS[selected_stop]

# Fetch Live Bus Data
bus_ref = db.collection("buses").document("Line_1").get()

if bus_ref.exists:
    bus_data = bus_ref.to_dict()
    bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
    last_seen = bus_data.get('last_updated')

    # 1. Calculation
    try:
        matrix = gmaps.distance_matrix((bus_lat, bus_lon), (target['lat'], target['lon']), mode="driving", departure_time="now")
        eta = matrix['rows'][0]['elements'][0]['duration_in_traffic']['text']
    except:
        eta = "Unavailable"

    # 2. Header Metrics
    c1, c2, c3 = st.columns(3)
    c1.metric("Status", "🟢 Live")
    c2.metric("Destination", selected_stop)
    c3.metric("Arriving In", eta)

    # 3. Map Layers
    bus_df = pd.DataFrame([{'lon': bus_lon, 'lat': bus_lat, 'icon_data': {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}}])
    stat_df = pd.DataFrame([{'name': n, 'lat': c['lat'], 'lon': c['lon']} for n, c in STATIONS.items()])
    
    view = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
    
    layers = [
        pdk.Layer("ScatterplotLayer", data=stat_df, get_position="[lon, lat]", get_color="[0, 100, 255, 100]", get_radius=100, pickable=True),
        pdk.Layer("ScatterplotLayer", data=pd.DataFrame([target]), get_position="[lon, lat]", get_color="[255, 0, 0, 200]", get_radius=180),
        pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
    ]
    
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name}"}))
    
    if last_seen:
        st.caption(f"Last updated: {last_seen.strftime('%H:%M:%S')}")
    
    if st.button("Refresh Live Map", use_container_width=True):
        st.rerun()
else:
    st.info("Bus Line 1 is currently offline. Please check back later.")
