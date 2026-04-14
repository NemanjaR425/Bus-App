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

# --- 2. DEFINE STATIONS ---
# You can manually add more Herceg Novi stops here
STATIONS = {
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}

# --- 3. APP LOGIC ---
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
        st.warning("Waiting for GPS signal... Please ensure location services are enabled.")

else:
    # --- PASSENGER MODE ---
    bus_ref = db.collection("buses").document("Line_1").get()
    
    if bus_ref.exists:
        bus_data = bus_ref.to_dict()
        bus_lat, bus_lon = bus_data['lat'], bus_data['lon']
        
        # 4. Station Selection
        st.subheader("Check Arrival Time")
        selected_station_name = st.selectbox("Select your stop:", list(STATIONS.keys()))
        target_station = STATIONS[selected_station_name]
        
        # 5. Calculate ETA to Selected Station
        eta_text = "Calculating..."
        try:
            matrix = gmaps.distance_matrix(
                origins=(bus_lat, bus_lon),
                destinations=(target_station['lat'], target_station['lon']),
                mode="driving", 
                departure_time="now"
            )
            res = matrix['rows'][0]['elements'][0]
            if res['status'] == 'OK':
                eta_text = res['duration_in_traffic']['text'] if 'duration_in_traffic' in res else res['duration']['text']
            else:
                eta_text = "Route Error"
        except Exception as e:
            eta_text = "Service Error"

        # Display Metrics
        c1, c2 = st.columns(2)
        c1.metric("Current Route", "Line 1")
        c2.metric(f"Arrival at {selected_station_name}", eta_text)

        # 6. Map Setup
        bus_df = pd.DataFrame([{'lon': bus_lon, 'lat': bus_lat}])
        
        # Create a DataFrame for all stations to show them on the map
        stations_df = pd.DataFrame([
            {'name': name, 'lat': coord['lat'], 'lon': coord['lon']} 
            for name, coord in STATIONS.items()
        ])
        
        # Icon data for the bus marker
        bus_df['icon_data'] = [{
            "url": "https://img.icons8.com/color/48/bus.png",
            "width": 128, "height": 128, "anchorY": 128
        }]

        view_state = pdk.ViewState(latitude=bus_lat, longitude=bus_lon, zoom=13)
        
        layers = [
            # Layer for all static stations (Blue dots)
            pdk.Layer(
                "ScatterplotLayer",
                data=stations_df,
                get_position="[lon, lat]",
                get_color="[0, 100, 255, 160]",
                get_radius=80,
                pickable=True
            ),
            # Layer for the selected station (Red dot)
            pdk.Layer(
                "ScatterplotLayer",
                data=pd.DataFrame([target_station]),
                get_position="[lon, lat]",
                get_color="[255, 0, 0, 200]",
                get_radius=120,
            ),
            # Layer for the live bus
            pdk.Layer(
                "IconLayer",
                data=bus_df,
                get_position="[lon, lat]",
                get_icon="icon_data",
                get_size=4,
                size_scale=15,
            )
        ]

        st.pydeck_chart(pdk.Deck(
            layers=layers, 
            initial_view_state=view_state,
            tooltip={"text": "{name}"}
        ))
        
        if st.button("Refresh Map"):
            st.rerun()
    else:
        st.warning("No live bus data found.")
