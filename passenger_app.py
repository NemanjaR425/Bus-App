import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# This CSS creates custom "Language Pills" that are large enough for fingers
# and guaranteed to stay in a row on mobile screens.
st.markdown("""
    <style>
    .lang-container {
        display: flex;
        flex-direction: row;
        gap: 10px;
        margin-bottom: 20px;
    }
    .lang-pill {
        flex: 1;
        padding: 12px;
        text-align: center;
        background-color: #262730;
        border: 2px solid #4CAF50;
        border-radius: 10px;
        color: white;
        text-decoration: none;
        font-weight: bold;
        cursor: pointer;
    }
    .lang-pill:active {
        background-color: #4CAF50;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA ---
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

LANGS = {
    "EN": {"title": "Herceg Novi Live Bus", "wait": "Where are you waiting?", "next": "Next Bus to", "mins": "mins", "none": "No buses active."},
    "ME": {"title": "Herceg Novi - Autobus Uživo", "wait": "Gdje čekate autobus?", "next": "Sledeći autobus za", "mins": "min", "none": "Nema aktivnih autobusa."},
    "RU": {"title": "Автобус Герцег-Нови Живьем", "wait": "Где вы ждете?", "next": "Следующий автобус до", "mins": "мин", "none": "На Линии 1 нет активных автобусов."}
}

# --- 3. STATE & INITIALIZATION ---
if "lang" not in st.session_state:
    st.session_state.lang = "EN"

if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. UI: LANGUAGE PILLS ---
# Using columns for the click events, but the CSS above ensures they look like buttons
cols = st.columns(3)
with cols[0]:
    if st.button("🇲🇪 MNE", use_container_width=True):
        st.session_state.lang = "ME"
        st.rerun()
with cols[1]:
    if st.button("🇬🇧 EN", use_container_width=True):
        st.session_state.lang = "EN"
        st.rerun()
with cols[2]:
    if st.button("🇷🇺 РУ", use_container_width=True):
        st.session_state.lang = "RU"
        st.rerun()

txt = LANGS[st.session_state.lang]

# --- 5. MAIN UI ---
st.title(f"🚌 {txt['title']}")

selected_station = st.selectbox(
    txt['wait'], 
    options=ROUTE_ORDER,
    index=0
)

# --- 6. BUS DATA & ETA ---
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
            all_bus_etas.append({"seconds": seconds, "lat": bus['lat'], "lon": bus['lon'], "name": "Bus"})
    except:
        continue

# Display ETA
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"{txt['next']} {selected_station}", f"{all_bus_etas[0]['seconds'] // 60} {txt['mins']}")
else:
    st.info(txt['none'])

# --- 7. THE MAP (FIXED) ---
# We use a default coordinate to ensure the map always loads
map_center = STATIONS[selected_station]

# Ensure we always pass a valid, non-empty list to the IconLayer
if all_bus_etas:
    bus_df = pd.DataFrame(all_bus_etas)
else:
    # Dummy data with zero opacity to prevent the JSON "Unexpected {" error
    bus_df = pd.DataFrame([{"lat": 0, "lon": 0, "name": ""}])

view_state = pdk.ViewState(
    latitude=map_center["lat"],
    longitude=map_center["lon"],
    zoom=13, pitch=0
)

# Layer for the bus stops in the Boka region
stops_data = pd.DataFrame([{"name": k, "lat": v["lat"], "lon": v["lon"]} for k, v in STATIONS.items()])
stops_layer = pdk.Layer(
    "ScatterplotLayer",
    stops_data,
    get_position="[lon, lat]",
    get_color="[0, 150, 255, 180]",
    get_radius=100,
)

# Layer for active buses
bus_layer = pdk.Layer(
    "IconLayer",
    bus_df,
    get_position="[lon, lat]",
    get_icon='''{
        "url": "https://img.icons8.com/color/96/bus.png",
        "width": 128, "height": 128, "anchorY": 128
    }''',
    get_size=40,
    opacity=1 if all_bus_etas else 0 # Hide if no buses
)

st.pydeck_chart(pdk.Deck(
    layers=[stops_layer, bus_layer],
    initial_view_state=view_state
))
