import streamlit as st
import requests
import urllib.parse

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="Reference → Scholar & PMC Links",
    layout="wide"
)

st.title("🔍 Reference → Google Scholar & PubMed Central")

st.markdown("""
Paste references **one per line**.  
Open **Google Scholar** or **PubMed Central** in a new tab.  
Tick **Reviewed** once checked.
""")

# ---------------- INPUT ---------------- #

refs_text = st.text_area(
    "Paste references here",
    height=250
)

# ---------------- SESSION STATE ---------------- #

if "refs" not in st.session_state:
    st.session_state.refs = []

if "reviewed" not in st.session_state:
    st.session_state.reviewed = {}

# ---------------- GENERATE ---------------- #

if st.button("Generate Links"):
    st.session_state.refs = [
        r.strip() for r in refs_text.splitlines() if r.strip()
    ]
    st.session_state.reviewed = {
        i: False for i in range(len(st.session_state.refs))
    }

# ---------------- DISPLAY ---------------- #

if st.session_state.refs:

    st.markdown("## 📑 References")

    for i, ref in enumerate(st.session_state.refs):

        scholar_url = (
            "https://scholar.google.com/scholar?q="
            + urllib.parse.quote(ref)
        )

        pmc_url = (
            "https://www.ncbi.nlm.nih.gov/pmc/?term="
            + urllib.parse.quote(ref)
        )

        col_ref, col_scholar, col_pmc, col_check = st.columns(
            [0.55, 0.18, 0.18, 0.09]
        )

        with col_ref:
            st.write(f"**{i+1}.** {ref}")

        with col_scholar:
            st.markdown(
                f'<a href="{scholar_url}" target="_blank">🔍 Google Scholar</a>',
                unsafe_allow_html=True
            )

        with col_pmc:
            st.markdown(
                f'<a href="{pmc_url}" target="_blank">🧬 PubMed Central</a>',
                unsafe_allow_html=True
            )

        with col_check:
            st.session_state.reviewed[i] = st.checkbox(
                "Reviewed",
                value=st.session_state.reviewed.get(i, False),
                key=f"rev_{i}",
                label_visibility="collapsed"
            )

    reviewed_count = sum(st.session_state.reviewed.values())
    st.success(f"Reviewed {reviewed_count} / {len(st.session_state.refs)} references")
