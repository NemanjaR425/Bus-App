import streamlit as st
import pandas as pd  # Fixed the NameError from your last screenshot
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

# --- 5. THE "NON-STRETCH" LANGUAGE BAR ---
st.write("---")

st.markdown("""
    <style>
    /* 1. Target the specific block containing our buttons */
    [data-testid="stVerticalBlock"] > div:has(.lang-anchor) {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: flex-start !important;
        gap: 8px !important;
        width: 100% !important;
    }

    /* 2. FORCE the button wrappers to NOT take up full width */
    [data-testid="stVerticalBlock"] > div:has(.lang-anchor) > div {
        width: auto !important;
        flex: none !important;
    }

    /* 3. Style the buttons into tight circles */
    .stButton > button {
        border-radius: 50% !important;
        width: 55px !important;
        height: 55px !important;
        min-width: 55px !important;
        padding: 0px !important;
        font-weight: bold !important;
        font-size: 12px !important;
        border: 2px solid #4CAF50 !important;
    }

    .stButton > button[kind="primary"] {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

with st.container():
    # This anchor helps our CSS find the right block to turn into a row
    st.markdown('<div class="lang-anchor"></div>', unsafe_allow_html=True)
    
    if st.button("MNE", key="me", type="primary" if st.session_state.lang == "ME" else "secondary"):
        st.session_state.lang = "ME"
        st.rerun()
    if st.button("EN", key="en", type="primary" if st.session_state.lang == "EN" else "secondary"):
        st.session_state.lang = "EN"
        st.rerun()
    if st.button("РУ", key="ru", type="primary" if st.session_state.lang == "RU" else "secondary"):
        st.session_state.lang = "RU"
        st.rerun()

# --- 6. BUS DATA & ETA ---
st.write("---")
# Data fetching and ETA logic here...
st.metric(f"{txt['next']} {st.session_state.selected_station}", f"9 {txt['mins']}")

# --- 7. MAP ---
# Pydeck map implementation here...
