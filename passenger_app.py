import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG & DATA ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

# --- 2. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 3. UI: STATION SELECTOR ---
st.title("🚌 Herceg Novi Live Bus")

selected_station = st.selectbox(
    "Where are you waiting?", 
    options=ROUTE_ORDER,
    index=0
)

# --- 4. BUS DATA FETCHING ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    try:
        res = gmaps.directions(
            origin=(bus['lat'], bus['lon']),
            destination=(STATIONS[selected_station]['lat'], STATIONS[selected_station]['lon']),
            mode="driving", departure_time="now"
        )
        if res:
            seconds = res[0]['legs'][0].get('duration_in_traffic', res[0]['legs'][0]['duration'])['value']
            all_bus_etas.append({"seconds": seconds, "lat": bus['lat'], "lon": bus['lon']})
    except:
        continue

# --- 5. THE MAP FIX (CRITICAL) ---
# We define the dataframes outside of any 'if' blocks to ensure 
# they always exist for the Pydeck layers.
if all_bus_etas:
    bus_df = pd.DataFrame(all_bus_etas)
else:
    # We provide a 'dummy' row so Pydeck doesn't crash on an empty list
    bus_df = pd.DataFrame([{"lat": 0, "lon": 0}])

# Define the layers
stops_data = pd.DataFrame([{"name": k, "lat": v["lat"], "lon": v["lon"]} for k, v in STATIONS.items()])
stops_layer = pdk.Layer(
    "ScatterplotLayer",
    stops_data,
    get_position="[lon, lat]",
    get_color="[0, 150, 255, 180]",
    get_radius=100,
)

bus_layer = pdk.Layer(
    "IconLayer",
    bus_df,
    get_position="[lon, lat]",
    get_icon='''{
        "url": "https://img.icons8.com/color/96/bus.png",
        "width": 128, "height": 128, "anchorY": 128
    }''',
    get_size=40,
    # If no buses exist, we set opacity to 0 to hide the dummy row
    opacity=1 if all_bus_etas else 0 
)

# Final Map Render
st.pydeck_chart(pdk.Deck(
    layers=[stops_layer, bus_layer],
    initial_view_state=pdk.ViewState(
        latitude=STATIONS[selected_station]["lat"],
        longitude=STATIONS[selected_station]["lon"],
        zoom=13
    )
))

# --- 6. ETA DISPLAY ---
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"Next Bus to {selected_station}", f"{all_bus_etas[0]['seconds'] // 60} mins")
else:
    st.info("No buses active on Line 1 currently.")
