import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import googlemaps
from streamlit_js_eval import get_geolocation

# --- 1. CONFIG & SECRETS ---
st.set_page_config(page_title="Town Bus Tracker", layout="wide")

# Mobile Safe Area UI Fix
st.markdown("""
    <style>
    .main .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    @supports (padding: env(safe-area-inset-top)) {
        .main .block-container { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }
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

# Initialize Google Maps
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
    
    # Trigger browser GPS
    loc = get_geolocation()
    
    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        
        st.success(f"GPS Signal Acquired: {lat}, {lon}")
        
        if st.button("🛰️ Broadcast My Live Location"):
            db.collection("buses").document(bus_id).set({
                "lat": lat,
                "lon": lon,
                "last_updated": datetime.now()
            })
            st.info(f"Location updated for {bus_id} at {datetime.now().strftime('%H:%M:%S')}")
    else:
        st.warning("Waiting for GPS signal... Please ensure location services are enabled on your device.")

else:
    # --- PASSENGER MODE ---
    bus_ref = db.collection("buses").document("Line_1").get()
    
    if bus_ref.exists:
        bus_data = bus_ref.to_dict()
        bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
        
        # Station: Herceg Novi Main Bus Station
        stat_lat, stat_lon = 42.4572, 18.5283 
        
        # 3. Calculate ETA
        eta_text = "Calculating..."
        try:
            matrix = gmaps.distance_matrix(
                origins=(bus_lat, bus_lon),
                destinations=(stat_lat, stat_lon),
                mode="driving", 
                departure_time="now"
            )
            res = matrix['rows'][0]['elements'][0]
            if res['status'] == 'OK':
                eta_text = res['duration_in_traffic']['text'] if 'duration_in_traffic' in res else res['duration']['text']
            else:
                eta_text = "Out of Range"
        except Exception as e:
            eta_text = "Service Error"

        # 4. Display Metrics
        c1, c2 = st.columns(2)
        c1.metric("Next Bus", "Line 1")
        c2.metric("Estimated Arrival", eta_text)

        # 5. Map Setup
        bus_df = pd.DataFrame([{'lon': bus_lon, 'lat': bus_lat}])
        stat_df = pd.DataFrame([{'lon': stat_lon, 'lat': stat_lat}])
        
        # Icon data for the bus marker
        bus_df['icon_data'] = [{
            "url": "https://img.icons8.com/color/48/bus.png",
            "width": 128, "height": 128, "anchorY": 128
        }]

        view_state = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=14)
        
        layers = [
            pdk.Layer(
                "ScatterplotLayer",
                data=stat_df,
                get_position="[lon, lat]",
                get_color="[200, 30, 0, 160]",
                get_radius=100,
            ),
            pdk.Layer(
                "IconLayer",
                data=bus_df,
                get_position="[lon, lat]",
                get_icon="icon_data",
                get_size=4,
                size_scale=15,
            )
        ]

        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))
        
        if st.button("Refresh Manually"):
            st.rerun()
    else:
        st.warning("No live bus data found. Use Driver Mode to start broadcasting.")
