import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# Check if already initialized so it doesn't error on refresh
if not firebase_admin._apps:
    # This pulls directly from the [gcp_service_account] section in your secrets
    cred = credentials.Certificate(dict(st.secrets["gcp_service_account"]))
    firebase_admin.initialize_app(cred)
# 1. Pull the latest coordinates from your database
db = firestore.client()
bus_ref = db.collection("buses").document("bus_01")
data = bus_ref.get().to_dict() # Contains {'lat': 42.45, 'lon': 18.53}

# 2. Display on a map
view_state = pdk.ViewState(latitude=data['lat'], longitude=data['lon'], zoom=14)
layer = pdk.Layer(
    "IconLayer",
    data=[data],
    get_position='[lon, lat]',
    get_icon='{"url": "https://img.icons8.com/color/48/bus.png", "width": 128, "height": 128, "anchorY": 128}',
    get_size=4,
    size_scale=15,
)

st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))
