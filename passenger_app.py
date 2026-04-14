import streamlit as st
import pandas as pd
import pydeck as pdk
import firebase_admin
from firebase_admin import credentials, firestore
import googlemaps

# --- 1. CONFIG ---
st.set_page_config(page_title="HN Bus Tracker", layout="wide")

# --- 2. TRANSLATIONS ---
LANGS = {
    "EN": {
        "flag": "🇬🇧",
        "title": "Herceg Novi Live Bus",
        "wait_label": "Where are you waiting?",
        "next_arr": "Next Bus to",
        "mins": "mins",
        "no_bus": "No buses currently active on Line 1.",
        "refresh": "Refresh Map"
    },
    "ME": {
        "flag": "🇲🇪",
        "title": "Herceg Novi - Autobus Uživo",
        "wait_label": "Gdje čekate autobus?",
        "next_arr": "Sledeći autobus za",
        "mins": "min",
        "no_bus": "Trenutno nema aktivnih autobusa na Liniji 1.",
        "refresh": "Osvježi mapu"
    },
    "RU": {
        "flag": "🇷🇺",
        "title": "Автобус Герцег-Нови Живьем",
        "wait_label": "Где вы ждете?",
        "next_arr": "Следующий автобус до",
        "mins": "мин",
        "no_bus": "На Линии 1 сейчас нет активных автобусов.",
        "refresh": "Обновить карту"
    }
}

# --- 3. DATA & INIT ---
STATIONS = {
    "Igalo (Center)": {"lat": 42.4594, "lon": 18.5085},
    "Topla": {"lat": 42.4550, "lon": 18.5200},
    "Main Bus Station (Glavna)": {"lat": 42.4572, "lon": 18.5283},
    "Meljine": {"lat": 42.4575, "lon": 18.5580},
    "Zelenika": {"lat": 42.4500, "lon": 18.5750}
}
ROUTE_ORDER = list(STATIONS.keys())

if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()
gmaps = googlemaps.Client(key=st.secrets["api_key"])

# --- 4. STATE MANAGEMENT ---
if "lang" not in st.session_state:
    st.session_state.lang = "EN"

if "selected_station" not in st.session_state:
    qp = st.query_params
    st.session_state.selected_station = qp.get("station") if qp.get("station") in ROUTE_ORDER else ROUTE_ORDER[0]

txt = LANGS[st.session_state.lang]

# --- 5. UI: TITLE & STATION SELECTION ---
st.title(f"🚌 {txt['title']}")

# Station Selection Dropdown
selected_stop = st.selectbox(
    txt['wait_label'],
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="manual_choice"
)

if selected_stop != st.session_state.selected_station:
    st.session_state.selected_station = selected_stop
    st.rerun()

# --- 6. HORIZONTAL FLAG BUTTONS (Mobile Optimized) ---
st.write("---")

# CSS to force columns to stay horizontal even on small screens
st.markdown("""
    <style>
    [data-testid="column"] {
        width: calc(25% - 1rem) !important;
        flex: 1 1 calc(25% - 1rem) !important;
        min-width: 60px !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        display: flex !important;
        flex-wrap: nowrap !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Create 4 columns (3 for flags, 1 for spacing)
f1, f2, f3, _ = st.columns([1, 1, 1, 4])

with f1:
    if st.button(LANGS["EN"]["flag"] + " EN", key="btn_en", use_container_width=True):
        st.session_state.lang = "EN"
        st.rerun()
with f2:
    if st.button(LANGS["ME"]["flag"] + " ME", key="btn_me", use_container_width=True):
        st.session_state.lang = "ME"
        st.rerun()
with f3:
    if st.button(LANGS["RU"]["flag"] + " RU", key="btn_ru", use_container_width=True):
        st.session_state.lang = "RU"
        st.rerun()

st.write("") # Small spacer

# --- 7. BUS DATA & ETA ---
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

# Display Results
if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"{txt['next_arr']} {st.session_state.selected_station}", f"{all_bus_etas[0]['seconds'] // 60} {txt['mins']}")
else:
    st.warning(txt['no_bus'])

# --- 8. MAP ---
station_df = pd.DataFrame([
    {
        'name': n, 'lat': c['lat'], 'lon': c['lon'], 
        'color': [255, 0, 0, 255] if n == st.session_state.selected_station else [0, 100, 255, 160]
    } for n, c in STATIONS.items()
])

bus_df = pd.DataFrame(all_bus_etas)
if not bus_df.empty:
    bus_df['icon_data'] = [{"url": "https://img.icons8.com/color/48/bus.png", "width": 100, "height": 100, "anchorY": 100} for _ in range(len(bus_df))]

view = pdk.ViewState(latitude=42.4572, longitude=18.5383, zoom=12.5)

s_layer = pdk.Layer("ScatterplotLayer", data=station_df, id="stops", get_position="[lon, lat]", get_color="color", get_radius=180, pickable=True)
b_layer = pdk.Layer("IconLayer", data=bus_df, id="buses", get_position="[lon, lat]", get_icon="icon_data", get_size=5, size_scale=15)

map_data = st.pydeck_chart(
    pdk.Deck(layers=[s_layer, b_layer], initial_view_state=view, tooltip={"text": "{name}"}),
    on_select="rerun",
    selection_mode="single-object",
    key="bus_map"
)

# Handle Map Selection
if map_data.selection:
    objs = map_data.selection.get("objects", {}).get("stops")
    if objs:
        new_pick = objs[0]["name"]
        if new_pick != st.session_state.selected_station:
            st.session_state.selected_station = new_pick
            st.rerun()
