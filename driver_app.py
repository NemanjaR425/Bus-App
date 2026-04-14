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
    # --- APP INITIALIZATION ---
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
