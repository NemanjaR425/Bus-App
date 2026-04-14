import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import googlemaps

# --- 1. CONFIG & SECRETS ---
st.set_page_config(page_title="Town Bus Tracker", layout="wide")

# Safe Area CSS Fix for Mobile Devices
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
    try:
        cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase Init Error: {e}")

db = firestore.client()

# Initialize Google Maps (Option A: Flat secret)
try:
    gmaps = googlemaps.Client(key=st.secrets["api_key"])
except Exception as e:
    st.error(f"Google Maps Key Error: {e}")

# --- 2. APP LOGIC ---
st.title("🚌 Local Bus Tracker")

# Sidebar for switching modes
mode = st.sidebar.radio("Choose Mode", ["Passenger", "Driver Login"])

if mode == "Driver Login":
    st.subheader("Driver Dashboard")
    bus_id = st.text_input("Enter Bus ID", value="Line_1")
    
    st.info("Set the coordinates and click update to broadcast.")
    # Default coordinates for Herceg Novi area
    lat = st.number_input("Current Lat", value=42.450000, format="%.6f")
    lon = st.number_input("Current Lon", value=18.530000, format="%.6f")
    
    if st.button("Update Location"):
        db.collection("buses").document(bus_id).set({
            "lat": lat,
            "lon": lon,
            "last_updated": datetime.now()
        })
        st.success(f"Location updated for {bus_id} at {datetime.now().strftime('%H:%M:%S')}!")

else:
    # --- PASSENGER MODE ---
    # 1. Fetch Bus Location from Firestore
    bus_ref = db.collection("buses").document("Line_1").get()
    
    if bus_ref.exists:
        bus_data = bus_ref.to_dict()
        bus_lat = bus_data['lat']
        bus_lon = bus_data['lon']
        
        # 2. Station Data (Example: Herceg Novi Main Station)
        station_lat, station_lon = 42.4572, 18.5283 
        
        # 3. Calculate ETA using Google Maps Distance Matrix
        try:
            matrix = gmaps.distance_matrix(
                origins=(bus_lat, bus_lon),
                destinations=(station_lat, station_lon),
                mode="driving",
                departure_time="now"
            )
            if matrix['rows'][0]['elements'][0]['status'] == 'OK':
                eta_text = matrix['rows'][0]['elements'][0]['duration_in_traffic']['text']
            else:
                eta_text = "Route not found"
        except Exception as e:
            eta_text = "ETA Unavailable"
            print(f"Maps Error: {e}")

        # 4. Display ETA Info
        col1, col2 = st.columns(2)
        col1.metric("Next Bus", "Line 1")
        col2.metric("Estimated Arrival", eta_text)

        # 5. Map View Configuration
        view_state = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=14)
        
        # Data wrapped in lists [] to prevent "Unexpected {" errors
        bus_position = [{"lat": bus_lat, "lon": bus_lon}]
        station_position = [{"lat": station_lat, "lon": station_lon}]
        
        layers = [
            pdk.Layer(
                "ScatterplotLayer",
                data=station_position,
                get_position="[lon, lat]",
                get_color="[200, 30, 0, 160]",
                get_radius=100,
            ),
            pdk.Layer(
                "IconLayer",
                data=bus_position,
                get_position="[lon, lat]",
                get_icon='{"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}',
                get_size=4,
                size_scale=15,
            )
        ]

        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))
        
        if st.button("Manual Refresh"):
            st.rerun()
    else:
        st.warning("Waiting for live bus data... Please update location in Driver Mode first.")
