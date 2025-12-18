import streamlit as st
import requests

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="Reference → Google Scholar Links",
    layout="wide"
)

st.title("🔍 Reference → Google Scholar Search")

st.markdown("""
Paste references **one per line**.  
Click **Google Scholar** to open in a new tab.  
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

        scholar_url = f"https://scholar.google.com/scholar?q={requests.utils.quote(ref)}"

        # Inline layout
        col_ref, col_link, col_check = st.columns([0.65, 0.2, 0.15])

        with col_ref:
            st.write(f"**{i+1}.** {ref}")

        with col_link:
            st.markdown(
                f'<a href="{scholar_url}" target="_blank">🔍 Google Scholar</a>',
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
