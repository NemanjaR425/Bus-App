import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import googlemaps

# --- 1. CONFIG & SECRETS ---
st.set_page_config(page_title="Town Bus Tracker", layout="wide")

st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    @supports (padding: env(safe-area-inset-top)) {
        .main .block-container { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }
    }
    </style>
    """, unsafe_allow_html=True)

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase Init Error: {e}")

db = firestore.client()

try:
    gmaps = googlemaps.Client(key=st.secrets["api_key"])
except Exception as e:
    st.error(f"Google Maps Key Error: {e}")

# --- 2. APP LOGIC ---
st.title("🚌 Local Bus Tracker")
mode = st.sidebar.radio("Choose Mode", ["Passenger", "Driver Login"])

if mode == "Driver Login":
    st.subheader("Driver Dashboard")
    bus_id = st.text_input("Enter Bus ID", value="Line_1")
    st.info("Set coordinates and click update. Try 42.4511, 18.5255 for Herceg Novi center.")
    lat = st.number_input("Current Lat", value=42.451100, format="%.6f")
    lon = st.number_input("Current Lon", value=18.525500, format="%.6f")
    
    if st.button("Update Location"):
        db.collection("buses").document(bus_id).set({
            "lat": lat, "lon": lon, "last_updated": datetime.now()
        })
        st.success(f"Location updated for {bus_id}!")

else:
    # --- PASSENGER MODE ---
    bus_ref = db.collection("buses").document("Line_1").get()
    
    if bus_ref.exists:
        bus_data = bus_ref.to_dict()
        bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
        stat_lat, stat_lon = 42.4572, 18.5283 
        
        # 3. Calculate ETA with Debugging Info
        eta_text = "Calculating..."
        try:
            matrix = gmaps.distance_matrix(
                origins=(bus_lat, bus_lon),
                destinations=(stat_lat, stat_lon),
                mode="driving", departure_time="now"
            )
            
            # --- DEBUG BLOCK ---
            # This will show the raw Google response on your app screen
            with st.expander("🔍 Click to see Google API Debug Info"):
                st.write(matrix)
            # ------------------

            res = matrix['rows'][0]['elements'][0]
            if res['status'] == 'OK':
                eta_text = res['duration_in_traffic']['text'] if 'duration_in_traffic' in res else res['duration']['text']
            else:
                eta_text = f"Google Status: {res['status']}"
        except Exception as e:
            eta_text = f"App Error: {str(e)}"

        c1, c2 = st.columns(2)
        c1.metric("Next Bus", "Line 1")
        c2.metric("Estimated Arrival", eta_text)

        # 4. Map Setup
        bus_df = pd.DataFrame([{'lon': bus_lon, 'lat': bus_lat}])
        stat_df = pd.DataFrame([{'lon': stat_lon, 'lat': stat_lat}])
        bus_df['icon_data'] = [{"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}]

        view_state = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=14)
        
        layers = [
            pdk.Layer("ScatterplotLayer", data=stat_df, get_position="[lon, lat]", get_color="[200, 30, 0, 160]", get_radius=100),
            pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=4, size_scale=15)
        ]

        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))
        if st.button("Refresh Map"): st.rerun()
    else:
        st.warning("No live bus data found. Go to Driver Mode and click Update.")
