import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

st.set_page_config(page_title="Herceg Novi Bus Tracker", layout="wide")

# Custom UI for Passenger focus
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# Initialize Firebase
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

st.title("🚌 HN Bus Live Tracker")

# Read bus data (Passenger can't write to this)
bus_ref = db.collection("buses").document("Line_1").get()

if bus_ref.exists:
    bus_data = bus_ref.to_dict()
    bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Plan Your Trip")
        selected_stop = st.selectbox("Where are you waiting?", list(STATIONS.keys()))
        target = STATIONS[selected_stop]
        
        # Calculate ETA
        try:
            matrix = gmaps.distance_matrix((bus_lat, bus_lon), (target['lat'], target['lon']), mode="driving", departure_time="now")
            eta = matrix['rows'][0]['elements'][0]['duration_in_traffic']['text']
        except:
            eta = "Unavailable"
            
        st.metric(label=f"Arrival at {selected_stop}", value=eta)
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()

    with col2:
        # Map Display
        bus_df = pd.DataFrame([{'lon': bus_lon, 'lat': bus_lat, 'icon_data': {"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}}])
        stat_df = pd.DataFrame([{'name': n, 'lat': c['lat'], 'lon': c['lon']} for n, c in STATIONS.items()])
        
        view = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
        layers = [
            pdk.Layer("ScatterplotLayer", data=stat_df, get_position="[lon, lat]", get_color="[0, 100, 255, 100]", get_radius=100, pickable=True),
            pdk.Layer("ScatterplotLayer", data=pd.DataFrame([target]), get_position="[lon, lat]", get_color="[255, 0, 0, 200]", get_radius=150),
            pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
        ]
        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, tooltip={"text": "{name}"}))
else:
    st.info("Waiting for the bus to start its route...")
