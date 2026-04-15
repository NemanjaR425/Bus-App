import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# CSS to make the radio buttons look more like actual buttons
st.markdown("""
    <style>
    /* Force the radio group to stay tight */
    div[data-testid="stWidgetLabel"] {
        display: none;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 0px !important;
    }
    /* Simple styling to make the radio options look cleaner */
    div.stStandard {
        padding-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATA & STATIONS ---
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

LANGS = {
    "English": {"title": "Herceg Novi Live Bus", "wait": "Where are you waiting?", "next": "Next Bus to", "mins": "mins", "none": "No buses active.", "code": "EN"},
    "Crnogorski": {"title": "Herceg Novi - Autobus Uživo", "wait": "Gdje čekate autobus?", "next": "Sledeći autobus za", "mins": "min", "none": "Nema aktivnih autobusa.", "code": "ME"},
    "Русский": {"title": "Автобус Герцег-Нови Живьем", "wait": "Где вы ждете?", "next": "Следующий автобус до", "mins": "мин", "none": "На Линии 1 нет активных автобусов.", "code": "RU"}
}

# --- 3. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. LANGUAGE SELECTOR (The "Safe" Way) ---
# This uses standard Streamlit radio buttons set to horizontal.
# It is guaranteed to stay in one row on mobile.
selected_lang_name = st.radio(
    "Language",
    options=list(LANGS.keys()),
    horizontal=True,
    label_visibility="collapsed"
)

txt = LANGS[selected_lang_name]

# --- 5. UI: MAIN CONTENT ---
st.title(f"🚌 {txt['title']}")

# Station selection
selected_station = st.selectbox(
    txt['wait'], 
    options=ROUTE_ORDER,
    index=0
)

st.write("---")

# --- 6. BUS DATA & MAP (Guaranteed to Render) ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    target_coords = STATIONS[selected_station]
    
    try:
        # Direct point-to-point for stability
        res = gmaps.directions(
            origin=(bus['lat'], bus['lon']),
            destination=(target_coords['lat'], target_coords['lon']),
            mode="driving",
            departure_time="now"
        )
        if res:
            seconds = res[0]['legs'][0].get('duration_in_traffic', res[0]['legs'][0]['duration'])['value']
            all_bus_etas.append({
                "seconds": seconds, 
                "lat": bus['lat'], 
                "lon": bus['lon'], 
                "name": f"Bus {doc.id[-4:]}"
            })
    except Exception as e:
        continue

# Display Metric
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"{txt['next']} {selected_station}", f"{all_bus_etas[0]['seconds'] // 60} {txt['mins']}")
else:
    st.info(txt['none'])

# --- 7. THE MAP (Independent of Logic) ---
# We build the dataframes here to ensure the map always has something to show
stops_data = pd.DataFrame([
    {"name": k, "lat": v["lat"], "lon": v["lon"]} for k, v in STATIONS.items()
])

bus_data = pd.DataFrame(all_bus_etas) if all_bus_etas else pd.DataFrame(columns=["lat", "lon", "name"])

view_state = pdk.ViewState(
    latitude=42.4572,
    longitude=18.5383,
    zoom=12,
    pitch=0
)

# Layer for bus stops
stops_layer = pdk.Layer(
    "ScatterplotLayer",
    stops_data,
    get_position="[lon, lat]",
    get_color="[0, 100, 255, 160]",
    get_radius=150,
)

# Layer for buses
bus_layer = pdk.Layer(
    "IconLayer",
    bus_data,
    get_position="[lon, lat]",
    get_icon='''{
        "url": "https://img.icons8.com/color/96/bus.png",
        "width": 128, "height": 128, "anchorY": 128
    }''',
    get_size=40,
)

st.pydeck_chart(pdk.Deck(
    layers=[stops_layer, bus_layer],
    initial_view_state=view_state,
    tooltip={"text": "{name}"}
))
