import streamlit as st
import pandas as pd
import requests

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="Reference → Google Scholar Links",
    layout="wide"
)

st.title("🔍 Reference → Google Scholar Search")

st.markdown("""
Paste references **one per line**.  
Click **Open in Scholar** to search.  
Tick **Reviewed** after checking the result.
""")

# ---------------- INPUT ---------------- #

refs_text = st.text_area(
    "Paste references here",
    height=250
)

# ---------------- SESSION STATE INIT ---------------- #

if "refs" not in st.session_state:
    st.session_state.refs = []

if "reviewed" not in st.session_state:
    st.session_state.reviewed = {}

# ---------------- PROCESS ---------------- #

if st.button("Generate Scholar Links"):
    st.session_state.refs = [
        r.strip() for r in refs_text.splitlines() if r.strip()
    ]
    st.session_state.reviewed = {
        i: False for i in range(len(st.session_state.refs))
    }

# ---------------- DISPLAY ---------------- #

if st.session_state.refs:

    st.markdown("## 📑 References")

    for i, ref in enumerate(st.session_state.refs, 1):

        scholar_url = f"https://scholar.google.com/scholar?q={requests.utils.quote(ref)}"

        col1, col2, col3 = st.columns([0.05, 0.75, 0.2])

        with col1:
            st.write(f"**{i}.**")

        with col2:
            st.write(ref)
            st.markdown(
                f'<a href="{scholar_url}" target="_blank">🔍 Open in Google Scholar</a>',
                unsafe_allow_html=True
            )

        with col3:
            st.session_state.reviewed[i-1] = st.checkbox(
                "Reviewed",
                value=st.session_state.reviewed.get(i-1, False),
                key=f"rev_{i}"
            )

    reviewed_count = sum(st.session_state.reviewed.values())
    st.success(f"Reviewed {reviewed_count} / {len(st.session_state.refs)} references")
