import streamlit as st
import pandas as pd  # FIXED: Added to prevent the NameError in your screenshot
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
    "EN": {"title": "Herceg Novi Live Bus", "wait": "Where are you waiting?", "next": "Next Bus to", "mins": "mins", "none": "No buses active."},
    "ME": {"title": "Herceg Novi - Autobus Uživo", "wait": "Gdje čekate autobus?", "next": "Sledeći autobus za", "mins": "min", "none": "Nema aktivnih autobusa."},
    "RU": {"title": "Автобус Герцег-Нови Живьем", "wait": "Где вы ждете?", "next": "Следующий автобус до", "mins": "мин", "none": "На Линии 1 нет активных автобусов."}
}

# --- 2. INITIALIZATION ---
if not firebase_admin._apps:
    # Using the credentials you've set up for the Boka region tracker
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

st.selectbox(txt['wait'], options=ROUTE_ORDER, 
             index=ROUTE_ORDER.index(st.session_state.selected_station), 
             key="manual_choice", on_change=handle_dropdown)

# --- 5. THE "NON-STACKING" LANGUAGE BAR ---
st.write("---")

st.markdown("""
    <style>
    /* FORCE THE ROW: This stops Streamlit from stacking on mobile */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: flex-start !important;
        gap: 10px !important;
    }
    
    /* FORCE COLUMN WIDTH: Prevents them from stretching to full width */
    div[data-testid="column"] {
        width: fit-content !important;
        flex: unset !important;
        min-width: unset !important;
    }

    /* CIRCLE BUTTONS: Consistent with your previous design */
    .stButton > button {
        border-radius: 50% !important;
        width: 60px !important;
        height: 60px !important;
        padding: 0px !important;
        font-weight: bold !important;
        border: 2px solid #4CAF50 !important;
    }

    .stButton > button[kind="primary"] {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# Using columns, but the CSS above will "freeze" them in a row
c1, c2, c3, _ = st.columns([1, 1, 1, 5])

with c1:
    if st.button("MNE", key="me", type="primary" if st.session_state.lang == "ME" else "secondary"):
        st.session_state.lang = "ME"
        st.rerun()
with c2:
    if st.button("EN", key="en", type="primary" if st.session_state.lang == "EN" else "secondary"):
        st.session_state.lang = "EN"
        st.rerun()
with c3:
    if st.button("РУ", key="ru", type="primary" if st.session_state.lang == "RU" else "secondary"):
        st.session_state.lang = "RU"
        st.rerun()

# --- 6. BUS DATA & ETA ---
st.write("---")
buses_ref = db.collection("active_buses").where("line", "==", "Line_1").stream()
all_bus_etas = []

for doc in buses_ref:
    bus = doc.to_dict()
    target = st.session_state.selected_station
    target_idx = ROUTE_ORDER.index(target)
    # Custom waypoints for the Herceg Novi route
    route_waypoints = [f"{STATIONS[ROUTE_ORDER[i]]['lat']},{STATIONS[ROUTE_ORDER[i]]['lon']}" for i in range(target_idx)]

    try:
        res = gmaps.directions(origin=(bus['lat'], bus['lon']), 
                               destination=(STATIONS[target]['lat'], STATIONS[target]['lon']), 
                               waypoints=route_waypoints, mode="driving", departure_time="now")
        if res:
            seconds = sum(l.get('duration_in_traffic', l['duration'])['value'] for l in res[0]['legs'])
            all_bus_etas.append({"seconds": seconds, "lat": bus['lat'], "lon": bus['lon']})
    except:
        continue

if all_bus_etas:
    all_bus_etas.sort(key=lambda x: x['seconds'])
    st.metric(f"{txt['next']} {st.session_state.selected_station}", f"{all_bus_etas[0]['seconds'] // 60} {txt['mins']}")
    
    # Map logic using the data we just fetched
    bus_df = pd.DataFrame(all_bus_etas) # FIXED: NameError pd is gone
    # ... (Rest of your Pydeck map code here)
else:
    st.warning(txt['none'])
