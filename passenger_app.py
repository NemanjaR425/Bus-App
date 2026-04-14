# --- ADD THIS TO YOUR IMPORTS ---
import streamlit as st
import pandas as pd
import pydeck as pdk

# ... (Firebase & Google Maps setup remains the same) ...

# 1. SETUP SESSION STATE
# We need this to keep track of the selection across reruns
if "selected_station" not in st.session_state:
    # Use the QR code station if present, otherwise default to Igalo
    st.session_state.selected_station = url_station if url_station in ROUTE_ORDER else ROUTE_ORDER[0]

# 2. THE SELECTION BOX
# We link the selectbox to the session state
selected_stop = st.selectbox(
    "Where are you waiting?",
    options=ROUTE_ORDER,
    index=ROUTE_ORDER.index(st.session_state.selected_station),
    key="station_dropdown"
)

# ... (ETA Logic remains the same) ...

# 3. THE INTERACTIVE MAP
# We add an 'id' to the layer and 'on_select' to the chart
station_data = pd.DataFrame([
    {'name': n, 'lat': c['lat'], 'lon': c['lon'], 'index': i} 
    for i, (n, c) in enumerate(STATIONS.items())
])

view = pdk.ViewState(latitude=42.4572, longitude=18.5283, zoom=12)

# Define the Station Layer
station_layer = pdk.Layer(
    "ScatterplotLayer",
    data=station_data,
    id="stations-layer",  # Required for selection to work
    get_position="[lon, lat]",
    get_color="[0, 100, 255, 160]",
    get_radius=150,
    pickable=True,        # Must be True to click it
)

# Render with on_select
map_event = st.pydeck_chart(
    pdk.Deck(layers=[station_layer, bus_layer], initial_view_state=view),
    on_select="rerun",    # This tells Streamlit to refresh when a dot is clicked
    selection_mode="single-object"
)

# 4. HANDLE THE CLICK
if map_event and map_event.selection:
    # Check if something was clicked in our station layer
    selected_indices = map_event.selection.get("objects", {}).get("stations-layer")
    if selected_indices:
        clicked_station_name = selected_indices[0]["name"]
        
        # Update session state and rerun to update the dropdown/ETA
        if clicked_station_name != st.session_state.selected_station:
            st.session_state.selected_station = clicked_station_name
            st.rerun()
