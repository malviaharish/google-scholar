import streamlit as st
import pandas as pd
import requests

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="Reference → Google Scholar Links",
    layout="wide"
)

st.title("🔍 Reference → Google Scholar Search Links")

st.markdown("""
Paste references **one per line**.  
Click **Search** to generate Google Scholar links.  
Use the checkbox to **mark references you have reviewed**.
""")

# ---------------- INPUT ---------------- #

refs_text = st.text_area(
    "Paste references here",
    height=250,
    placeholder="Author A, Author B. Title. Journal. Year.\nAuthor C et al. Title. Journal. Year."
)

# ---------------- PROCESS ---------------- #

if st.button("Generate Google Scholar Links"):

    refs = [r.strip() for r in refs_text.splitlines() if r.strip()]

    if not refs:
        st.warning("Please paste at least one reference.")
        st.stop()

    # Initialize session state
    if "checked" not in st.session_state:
        st.session_state.checked = {i: False for i in range(len(refs))}

    rows = []

    for i, ref in enumerate(refs, 1):
        scholar_url = f"https://scholar.google.com/scholar?q={requests.utils.quote(ref)}"

        rows.append({
            "No.": i,
            "Reference": ref,
            "Google Scholar": scholar_url,
            "Reviewed": st.session_state.checked.get(i-1, False)
        })

    df = pd.DataFrame(rows)

    st.markdown("## 📑 Google Scholar Search Results")

    # Render interactive table
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "No.": st.column_config.NumberColumn(width="small"),
            "Reference": st.column_config.TextColumn(width="large"),
            "Google Scholar": st.column_config.LinkColumn(
                "Google Scholar",
                display_text="🔍 Open in Scholar"
            ),
            "Reviewed": st.column_config.CheckboxColumn(
                "Reviewed",
                help="Tick after opening the Scholar link"
            ),
        },
        disabled=["No.", "Reference", "Google Scholar"],
        key="editor"
    )

    # Persist checkbox state
    for idx, row in edited_df.iterrows():
        st.session_state.checked[idx] = row["Reviewed"]

    # Summary
    reviewed_count = sum(st.session_state.checked.values())
    st.success(f"Reviewed {reviewed_count} / {len(refs)} references")
