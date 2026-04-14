import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="Bus Driver Console", layout="centered")

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
db = firestore.client()

st.title("🆔 Driver Dashboard")
bus_id = st.text_input("Enter Bus ID", value="Line_1")

# Grab GPS coordinates from browser
loc = get_geolocation()

if loc:
    lat = loc['coords']['latitude']
    lon = loc['coords']['longitude']
    
    st.success(f"GPS Active: {lat}, {lon}")
    
    if st.button("🛰️ Update Live Location", use_container_width=True):
        db.collection("buses").document(bus_id).set({
            "lat": lat,
            "lon": lon,
            "last_updated": datetime.now()
        })
        st.toast(f"Broadcasting as {bus_id}!")
else:
    st.warning("Waiting for GPS signal... Please enable location.")
