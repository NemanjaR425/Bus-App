import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")
st.title("🚌 Herceg Novi Live Bus")

# --- 2. DATA (Hardcoded to ensure map always has points to show) ---
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

# --- 3. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. SELECTION ---
selected_station = st.selectbox("Where are you waiting?", options=ROUTE_ORDER)

# --- 5. BUS FETCHING ---
active_buses = []
try:
    # Querying Firestore for Line 1 buses
    docs = db.collection("active_buses").where("line", "==", "Line_1").stream()
    for doc in docs:
        data = doc.to_dict()
        active_buses.append({"lat": data['lat'], "lon": data['lon']})
except Exception as e:
    st.error(f"Database error: {e}")

# --- 6. THE MAP FIX ---
# Step A: Static Stop Data (This prevents the JSON crash)
stops_df = pd.DataFrame([{"name": k, "lat": v["lat"], "lon": v["lon"]} for k, v in STATIONS.items()])

# Step B: Create the Base Layer (Bus Stops)
layers = [
    pdk.Layer(
        "ScatterplotLayer",
        stops_df,
        get_position="[lon, lat]",
        get_color="[0, 150, 255, 200]",
        get_radius=150,
    )
]

# Step C: Only add the Bus Layer if there is data
if active_buses:
    bus_df = pd.DataFrame(active_buses)
    layers.append(
        pdk.Layer(
            "IconLayer",
            bus_df,
            get_position="[lon, lat]",
            get_icon='''{
                "url": "https://img.icons8.com/color/96/bus.png",
                "width": 128, "height": 128, "anchorY": 128
            }''',
            get_size=45,
        )
    )

# Step D: Render Map
st.pydeck_chart(pdk.Deck(
    layers=layers,
    initial_view_state=pdk.ViewState(
        latitude=STATIONS[selected_station]["lat"],
        longitude=STATIONS[selected_station]["lon"],
        zoom=13
    ),
    map_style="mapbox://styles/mapbox/light-v10"
))

# --- 7. ETA CALCULATION ---
if active_buses:
    # Calculate ETA using Google Maps API
    try:
        res = gmaps.directions(
            origin=(active_buses[0]['lat'], active_buses[0]['lon']),
            destination=(STATIONS[selected_station]['lat'], STATIONS[selected_station]['lon']),
            mode="driving", departure_time="now"
        )
        if res:
            eta = res[0]['legs'][0].get('duration_in_traffic', res[0]['legs'][0]['duration'])['text']
            st.success(f"Next Bus to {selected_station}: {eta}")
    except:
        st.write("Calculating ETA...")
else:
    st.info("No active buses currently detected on Line 1.")
