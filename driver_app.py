import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="HN Bus Driver Console", layout="centered")

# --- AUTHENTICATION ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.title("🔒 Driver Access")
        pwd = st.text_input("Enter Driver Password", type="password")
        if st.button("Unlock Dashboard"):
            if pwd == st.secrets["driver_password"]:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        return False
    return True

if check_password():
    st.title("🆔 Driver Dashboard")
    
    # Each driver enters a unique ID for their specific vehicle
    bus_id = st.text_input("Enter Vehicle ID (e.g., HN-BS-001)", value="Bus_1")
    
    loc = get_geolocation()
    if loc:
        lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
        st.success(f"GPS Active for {bus_id}")
        
        if st.button("🛰️ Broadcast My Location", use_container_width=True):
            # We save each bus as its own document in the "buses" collection
            db.collection("active_buses").document(bus_id).set({
                "bus_id": bus_id,
                "line": "Line_1",
                "lat": lat,
                "lon": lon,
                "last_updated": datetime.now()
            })
            st.toast(f"Broadcasting {bus_id} on Line 1")
    # Grab GPS coordinates from browser
    loc = get_geolocation()

    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        
        st.success(f"GPS Signal Ready: {lat}, {lon}")
        
        if st.button("🛰️ Broadcast Live Location", use_container_width=True):
            db.collection("buses").document(bus_id).set({
                "lat": lat,
                "lon": lon,
                "last_updated": datetime.now()
            })
            st.toast(f"Location Updated for {bus_id}!")
    else:
        st.warning("Waiting for GPS... Please ensure Location Access is enabled.")
    
    if st.button("Log Out"):
        st.session_state.password_correct = False
        st.rerun()
