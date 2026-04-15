import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG & DATA ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# Translation Dictionary
LANGS = {
    "🇬🇧 English": {
        "title": "Herceg Novi Live Bus",
        "wait_label": "Where are you waiting?",
        "lang_label": "Select Language",
        "next_arr": "Next Bus to",
        "mins": "mins",
        "no_bus": "No buses currently active on Line 1.",
    },
    "🇲🇪 Crnogorski": {
        "title": "Herceg Novi - Autobus Uživo",
        "wait_label": "Gdje čekate autobus?",
        "lang_label": "Izaberite jezik",
        "next_arr": "Sledeći autobus za",
        "mins": "min",
        "no_bus": "Trenutno nema aktivnih autobusa na Liniji 1.",
    },
    "🇷🇺 Русский": {
        "title": "Автобус Герцег-Нови Живьем",
        "wait_label": "Где вы ждете?",
        "lang_label": "Выберите язык",
        "next_arr": "Следующий автобус до",
        "mins": "мин",
        "no_bus": "На Линии 1 сейчас нет активных автобусов.",
    }
}

STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

# --- 2. INIT ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 3. UI: TITLE & SELECTORS (IN-LINE) ---
st.title("🚌 Live Bus") # Static prefix to ensure title always renders

if "selected_station" not in st.session_state:
    qp = st.query_params
    st.session_state.selected_station = qp.get("station") if qp.get("station") in ROUTE_ORDER else ROUTE_ORDER[0]

# Station Dropdown
def handle_station():
    st.session_state.selected_station = st.session_state.manual_choice

selected_stop = st.selectbox(
    "Location", # Temporary placeholder until lang is set
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="manual_choice",
    on_change=handle_station,
    label_visibility="collapsed" # Tidy layout
)

# Language Dropdown directly below
selected_lang_name = st.selectbox(
    "Language",
    options=list(LANGS.keys()),
    key="lang_choice",
    label_visibility="collapsed"
)
txt = LANGS[selected_lang_name]

# --- 4. BUS DATA & ETA ---
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    target = st.session_state.selected_station
    target_idx = ROUTE_ORDER.index(target)
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        res = gmaps.directions(
            origin=(bus['lat'], bus['lon']),
            destination=(STATIONS[target]['lat'], STATIONS[target]['lon']),
            waypoints=route_waypoints,
            optimize_waypoints=False,
            mode="driving",
            departure_time="now"
        )
        if res:
            seconds = sum(l.get('duration_in_traffic', l['duration'])['value'] for l in res[0]['legs'])
            all_bus_etas.append({"id": bus.get('bus_id'), "seconds": seconds, "lat": bus['lat'], "lon": bus['lon']})
    except:
        continue

# Display Metric
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"{txt['next_arr']} {st.session_state.selected_station}", f"{all_bus_etas[0]['seconds'] // 60} {txt['mins']}")
else:
    st.warning(txt['no_bus'])

# --- 5. MAP PREP ---
station_df = pd.DataFrame([
    {
        'name': n, 'lat': c['lat'], 'lon': c['lon'], 
        'color': [255, 0, 0, 255] if n == st.session_state.selected_station else [0, 100, 255, 160]
    } for n, c in STATIONS.items()
])

layers = [
    pdk.Layer(
        "ScatterplotLayer", 
        data=station_df, 
        id="station_layer", 
        get_position="[lon, lat]", 
        get_color="color", 
        get_radius=180, 
        pickable=True
    )
]

if all_bus_etas:
    bus_df = pd.DataFrame(all_bus_etas)
    bus_df['icon_data'] = [{"url": "https://img.icons8.com/color/48/bus.png", "width": 100, "height": 100, "anchorY": 100} for _ in range(len(bus_df))]
    layers.append(pdk.Layer("IconLayer", data=bus_df, get_position="[lon, lat]", get_icon="icon_data", get_size=5, size_scale=15))

# --- 6. RENDER BRIGHT MAP ---
view = pdk.ViewState(
    latitude=STATIONS[st.session_state.selected_station]["lat"], 
    longitude=STATIONS[st.session_state.selected_station]["lon"], 
    zoom=13
)

map_data = None 
try:
    map_data = st.pydeck_chart(
        pdk.Deck(
            layers=layers, 
            initial_view_state=view, 
            tooltip={"text": "{name}"},
            map_style="light" # Stable bright style
        ),
        on_select="rerun",
        selection_mode="single-object",
        key="bus_map"
    )
except Exception as e:
    st.error("Map loading error.")

# --- 7. HANDLE MAP CLICK ---
if map_data is not None and map_data.selection:
    objs = map_data.selection.get("objects", {}).get("station_layer")
    if objs:
        new_station = objs[0]["name"]
        if new_station != st.session_state.selected_station:
            st.session_state.selected_station = new_station
            st.rerun()
