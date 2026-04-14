import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from streamlit_js_eval import get_geolocation

# --- 1. CONFIG & FIREBASE INIT ---
st.set_page_config(page_title="HN Driver Console", layout="centered")

# Initialize Firebase immediately to avoid NameError
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase Init Error: {e}")

db = firestore.client()

# --- 2. AUTHENTICATION ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    if not st.session_state.password_correct:
        st.title("🔒 Driver Access")
        pwd = st.text_input("Enter Driver Password", type="password")
        if st.button("Unlock Dashboard"):
            # Ensure 'driver_password' is at the TOP of your secrets
            if pwd == st.secrets["driver_password"]:
                st.session_state.password_correct = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        return False
    return True

# --- 3. MAIN DASHBOARD ---
if check_password():
    st.title("🆔 Driver Dashboard")
    
    # Manual input for different buses
    bus_id = st.text_input("Enter Vehicle ID (e.g., Bus_1, Bus_2)", value="Bus_1")
    
    # Trigger GPS
    loc = get_geolocation()
    
    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        
        st.success(f"GPS Active for {bus_id}")
        
        if st.button("🛰️ Broadcast My Location", use_container_width=True):
            try:
                # This matches the new 'active_buses' collection for the multi-bus logic
                db.collection("active_buses").document(bus_id).set({
                    "bus_id": bus_id,
                    "line": "Line_1",
                    "lat": lat,
                    "lon": lon,
                    "last_updated": datetime.now()
                })
                st.toast(f"Successfully broadcasting as {bus_id}!")
            except Exception as e:
                st.error(f"Database Error: {e}")
    else:
        st.warning("Waiting for GPS signal... Please enable location on your device.")

    if st.sidebar.button("Log Out"):
        st.session_state.password_correct = False
        st.rerun()
