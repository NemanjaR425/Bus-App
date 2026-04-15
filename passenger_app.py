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

# --- 3. UI: TITLE & LANGUAGE (PRIORITY) ---
# Putting the title at the top ensures it renders first
st.title("🚌 Herceg Novi Live Bus")

cols = st.columns(3)
if "lang" not in st.session_state: st.session_state.lang = "EN"

with cols[0]:
    if st.button("🇲🇪 MNE", use_container_width=True): st.session_state.lang = "ME"
with cols[1]:
    if st.button("🇬🇧 EN", use_container_width=True): st.session_state.lang = "EN"
with cols[2]:
    if st.button("🇷🇺 РУ", use_container_width=True): st.session_state.lang = "RU"

selected_station = st.selectbox("Where are you waiting?", options=ROUTE_ORDER)

# --- 4. DATA FETCHING ---
active_bus_list = []
try:
    buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
    for doc in buses_ref:
        bus = doc.to_dict()
        active_bus_list.append({"lat": bus['lat'], "lon": bus['lon']})
except Exception as e:
    st.warning("Connecting to bus data...")

# --- 5. THE MAP (ERROR-PROOFED) ---
# We force the stops to exist first so the map always has valid data
stops_df = pd.DataFrame([{"name": k, "lat": v["lat"], "lon": v["lon"]} for k, v in STATIONS.items()])

main_layers = [
    pdk.Layer(
        "ScatterplotLayer",
        stops_df,
        get_position="[lon, lat]",
        get_color="[0, 150, 255, 200]",
        get_radius=150,
    )
]

# Only add the problematic bus layer if data actually exists
if active_bus_list:
    bus_df = pd.DataFrame(active_bus_list)
    main_layers.append(
        pdk.Layer(
            "IconLayer",
            bus_df,
            get_position="[lon, lat]",
            get_icon='''{
                "url": "https://img.icons8.com/color/96/bus.png",
                "width": 128, "height": 128, "anchorY": 128
            }''',
            get_size=40,
        )
    )

# Use a static view state if the selected station isn't found
view_state = pdk.ViewState(
    latitude=STATIONS[selected_station]["lat"],
    longitude=STATIONS[selected_station]["lon"],
    zoom=13
)

st.pydeck_chart(pdk.Deck(
    layers=main_layers,
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/dark-v10"
))

# --- 6. ETA DISPLAY ---
if active_bus_list:
    st.success(f"Bus is on the way to {selected_station}!")
else:
    st.info("No active buses on Line 1 at the moment.")
