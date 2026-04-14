import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import googlemaps

# --- 1. CONFIG & SECRETS ---
st.set_page_config(page_title="Town Bus Tracker", layout="wide")

# Safe Area CSS Fix for Mobile
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
    }
    @supports (padding: env(safe-area-inset-top)) {
        .main .block-container {
            padding-top: env(safe-area-inset-top);
            padding-bottom: env(safe-area-inset-bottom);
        }
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 2. APP LOGIC ---
st.title("🚌 Local Bus Tracker")

# Sidebar for switching modes
mode = st.sidebar.radio("Choose Mode", ["Passenger", "Driver Login"])

if mode == "Driver Login":
    st.subheader("Driver Dashboard")
    bus_id = st.text_input("Enter Bus ID", value="Line_1")
    
    # We moved the inputs OUTSIDE the "Start Broadcasting" button
    st.info("Set the coordinates and click update to broadcast.")
    lat = st.number_input("Current Lat", value=42.45, format="%.6f")
    lon = st.number_input("Current Lon", value=18.53, format="%.6f")
    
    # Now this button will work because it's at the top level of the Driver Mode
    if st.button("Update Location"):
        db.collection("buses").document(bus_id).set({
            "lat": lat,
            "lon": lon,
            "last_updated": datetime.now()
        })
        st.success(f"Location updated for {bus_id} at {datetime.now().strftime('%H:%M:%S')}!")

else:
    # --- PASSENGER MODE ---
    # 1. Fetch Bus Location
    bus_ref = db.collection("buses").document("Line_1").get()
    
    if bus_ref.exists:
        bus_data = bus_ref.to_dict()
        bus_lat = bus_data['lat']
        bus_lon = bus_data['lon']
        
        # 2. Station Data (Example: The town center)
        station_lat, station_lon = 42.457, 18.528 
        
        # 3. Calculate ETA using Google Maps
        try:
            matrix = gmaps.distance_matrix(
                origins=(bus_lat, bus_lon),
                destinations=(station_lat, station_lon),
                mode="driving",
                departure_time="now"
            )
            eta_text = matrix['rows'][0]['elements'][0]['duration_in_traffic']['text']
        except:
            eta_text = "Calculating..."

        # 4. Display ETA Info
        col1, col2 = st.columns(2)
        col1.metric("Next Bus", "Line 1")
        col2.metric("Estimated Arrival", eta_text)

        # 5. Map View
        view_state = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=14)
        
        # Layers: Bus Icon and Station Point
        layers = [
            pdk.Layer(
                "ScatterplotLayer",
                data=[{"lat": station_lat, "lon": station_lon}],
                get_position="[lon, lat]",
                get_color="[200, 30, 0, 160]",
                get_radius=100,
            ),
            pdk.Layer(
                "IconLayer",
                data=[{"lat": bus_lat, "lon": bus_lon}],
                get_position="[lon, lat]",
                get_icon='{"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}',
                get_size=4,
                size_scale=15,
            )
        ]

        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))
        
        if st.button("Refresh Location"):
            st.rerun()
    else:
        st.warning("Waiting for live bus data...")
