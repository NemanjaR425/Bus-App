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

LANGS = {
    "EN": {"title": "Herceg Novi Live Bus", "wait": "Where are you waiting?", "next": "Next Bus to", "mins": "mins", "none": "No buses active.", "label": "EN"},
    "ME": {"title": "Herceg Novi - Autobus Uživo", "wait": "Gdje čekate autobus?", "next": "Sledeći autobus za", "mins": "min", "none": "Nema aktivnih autobusa.", "label": "MNE"},
    "RU": {"title": "Автобус Герцег-Нови Живьем", "wait": "Где вы ждете?", "next": "Следующий автобус до", "mins": "мин", "none": "На Линии 1 нет активных автобусов.", "label": "Ру"}
}

# --- 2. INITIALIZATION ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 3. STATE ---
if "lang" not in st.session_state:
    st.session_state.lang = "EN"
if "selected_station" not in st.session_state:
    st.session_state.selected_station = ROUTE_ORDER[0]

txt = LANGS[st.session_state.lang]

# --- 4. UI: TITLE & SELECTOR ---
st.title(f"🚌 {txt['title']}")

def handle_dropdown():
    st.session_state.selected_station = st.session_state.manual_choice

st.selectbox(txt['wait'], options=ROUTE_ORDER, index=ROUTE_ORDER.index(st.session_state.selected_station), key="manual_choice", on_change=handle_dropdown)

# --- 5. THE "FIXED" LANGUAGE BAR ---
st.write("---")

st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: flex-start !important;
        gap: 12px !important;
        width: 100% !important;
    }
    div[data-testid="column"] {
        width: 65px !important;
        flex: 0 0 65px !important;
        padding: 0px !important;
    }
    .stButton > button {
        border-radius: 50% !important;
        width: 62px !important;
        height: 62px !important;
        padding: 0px !important;
        font-weight: bold !important;
        font-size: 14px !important;
        border: 2px solid #4CAF50 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

c1, c2, c3, spacer = st.columns([1, 1, 1, 10])

with c1:
    mne_type = "primary" if st.session_state.lang == "ME" else "secondary"
    if st.button("MNE", key="mne", type=mne_type):
        st.session_state.lang = "ME"
        st.rerun()
with c2:
    en_type = "primary" if st.session_state.lang == "EN" else "secondary"
    if st.button("EN", key="en", type=en_type):
        st.session_state.lang = "EN"
        st.rerun()
with c3:
    ru_type = "primary" if st.session_state.lang == "RU" else "secondary"
    if st.button("Ру", key="ru", type=ru_type):
        st.session_state.lang = "RU"
        st.rerun()

# --- 6. BUS DATA & ETA ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    target = st.session_state.selected_station
    target_idx = ROUTE_ORDER.index(target)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        res = gmaps.directions(origin=(bus['lat'], bus['lon']), destination=(STATIONS[target]['lat'], STATIONS[target]['lon']), waypoints=route_waypoints, mode="driving", departure_time="now")
        if res:
            seconds = sum(l.get('duration_in_traffic', l['duration'])['value'] for l in res[0]['legs'])
            all_bus_etas.append({"seconds": seconds, "lat": bus['lat'], "lon": bus['lon']})
    except:
        continue

if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"{txt['next']} {st.session_state.selected_station}", f"{all_bus_etas[0]['seconds'] // 60} {txt['mins']}")
else:
    st.warning(txt['none'])

# --- 7. MAP ---
station_df = pd.DataFrame([{'name': n, 'lat': c['lat'], 'lon': c['lon'], 'color': [255, 0, 0, 255] if n == st.session_state.selected_station else [0, 100, 255, 160]} for n, c in STATIONS.items()])
bus_df = pd.DataFrame(all_bus_etas)
if not bus_df.empty:
    bus_df['icon_data'] = [{"url": "https://img.icons8.com/color/48/bus.png", "width": 100, "height": 100, "anchorY": 100} for _ in range(len(bus_df))]

view = pdk.ViewState(latitude=42.4572, longitude=18.5383, zoom=12.5)
s_layer = pdk.Layer("ScatterplotLayer", data=station_df, id="stops", get_position="[lon, lat]", get_color="color", get_radius=180, pickable=True)
b_layer = pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=5, size_scale=15)

map_data = st.pydeck_chart(pdk.Deck(layers=[s_layer, b_layer], initial_view_state=view, tooltip={"text": "{name}"}), on_select="rerun", selection_mode="single-object", key="bus_map")

if map_data and map_data.selection:
    objs = map_data.selection.get("objects", {}).get("stops")
    if objs:
        st.session_state.selected_station = objs[0]["name"]
        st.rerun()
