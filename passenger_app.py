# --- 5. ROUND LANGUAGE BAR (Forced Single Row) ---
st.write("---")

st.markdown("""
    <style>
    /* 1. Force the horizontal container to NEVER wrap */
    div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important; /* This prevents the stacking */
        justify-content: flex-start !important;
        gap: 8px !important; /* Minimal gap to save space */
        width: 100% !important;
    }

    /* 2. Prevent columns from expanding to full width on mobile */
    div[data-testid="column"] {
        width: auto !important;
        flex: 0 0 auto !important; /* Don't grow, don't shrink */
        min-width: 0px !important;
    }

    /* 3. Slightly smaller circular buttons for guaranteed fit */
    .stButton > button {
        border-radius: 50% !important;
        width: 58px !important;
        height: 58px !important;
        padding: 0px !important;
        font-weight: bold !important;
        font-size: 13px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border: 2px solid #4CAF50 !important;
    }

    /* 4. Highlight for active state */
    .stButton > button[kind="primary"] {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Define columns with a very large empty spacer at the end
c1, c2, c3, _ = st.columns([1, 1, 1, 15])

with c1:
    mne_style = "primary" if st.session_state.lang == "ME" else "secondary"
    if st.button("MNE", key="btn_mne", type=mne_style):
        st.session_state.lang = "ME"
        st.rerun()
with c2:
    en_style = "primary" if st.session_state.lang == "EN" else "secondary"
    if st.button("EN", key="btn_en", type=en_style):
        st.session_state.lang = "EN"
        st.rerun()
with c3:
    ru_style = "primary" if st.session_state.lang == "RU" else "secondary"
    if st.button("Ру", key="btn_ru", type=ru_style):
        st.session_state.lang = "RU"
        st.rerun()
