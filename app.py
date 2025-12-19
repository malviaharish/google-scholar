import streamlit as st
import requests
import pandas as pd
from urllib.parse import quote

# ---------------- PAGE CONFIG ---------------- #
st.set_page_config(
    page_title="Reference → Scholar / PMC",
    layout="wide"
)

# ---------------- SESSION STATE ---------------- #
if "refs" not in st.session_state:
    st.session_state.refs = []

if "reviewed" not in st.session_state:
    st.session_state.reviewed = {}

# ---------------- UI HEADER ---------------- #
st.markdown(
    """
    <style>
    .ref-card {
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        background-color: #ffffff;
        margin-bottom: 0.75rem;
    }
    .links a {
        margin-right: 1.2rem;
        font-weight: 600;
        text-decoration: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📚 Reference → Google Scholar & PubMed Central")
st.caption(
    "Paste references → open search results in new tabs → mark as reviewed"
)

# ---------------- INPUT ---------------- #
refs_text = st.text_area(
    "Paste references (one per line)",
    height=220,
    placeholder="Author A et al. Title. Journal. Year.\nAuthor B et al. Title. Journal. Year.",
    key="refs_input"
)

if st.button("🔍 Generate Search Links"):
    st.session_state.refs = [
        r.strip() for r in refs_text.splitlines() if r.strip()
    ]
    st.session_state.reviewed = {
        i: False for i in range(len(st.session_state.refs))
    }

# ---------------- RESULTS ---------------- #
if st.session_state.refs:

    st.markdown("## 🔗 Search Links")

    for i, ref in enumerate(st.session_state.refs):

        scholar_url = f"https://scholar.google.com/scholar?q={quote(ref)}"
        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/?term={quote(ref)}"

        col1, col2 = st.columns([6, 2])

        with col1:
            st.markdown(
                f"""
                <div class="ref-card">
                    <div><strong>{i+1}.</strong> {ref}</div>
                    <div class="links">
                        <a href="{scholar_url}" target="_blank">🔍 Google Scholar</a>
                        <a href="{pmc_url}" target="_blank">📖 PubMed Central</a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col2:
            st.checkbox(
                "Reviewed",
                key=f"rev_{i}",
                value=st.session_state.reviewed.get(i, False),
                on_change=lambda idx=i: st.session_state.reviewed.update(
                    {idx: not st.session_state.reviewed.get(idx, False)}
                )
            )

    # ---------------- SUMMARY ---------------- #
    total = len(st.session_state.refs)
    done = sum(st.session_state.reviewed.values())

    st.markdown("---")
    st.success(f"✅ Reviewed {done} / {total} references")

    # ---------------- TABLE VIEW ---------------- #
    st.markdown("## 📊 Overview Table")

    table_rows = []
    for i, ref in enumerate(st.session_state.refs):
        table_rows.append({
            "Reference #": i + 1,
            "Reference": ref,
            "Google Scholar": f"https://scholar.google.com/scholar?q={quote(ref)}",
            "PubMed Central": f"https://www.ncbi.nlm.nih.gov/pmc/?term={quote(ref)}",
            "Reviewed": "✅" if st.session_state.reviewed.get(i) else "❌"
        })

    df = pd.DataFrame(table_rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Google Scholar": st.column_config.LinkColumn(
                "Google Scholar", display_text="Open"
            ),
            "PubMed Central": st.column_config.LinkColumn(
                "PubMed Central", display_text="Open"
            ),
        }
    )
