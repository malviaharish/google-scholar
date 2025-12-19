import streamlit as st
import urllib.parse

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="Reference Reviewer",
    layout="wide"
)

# ---------------- CUSTOM CSS ---------------- #

st.markdown("""
<style>
.ref-card {
    padding: 14px;
    border-radius: 10px;
    border: 1px solid #e6e6e6;
    margin-bottom: 10px;
}
.ref-reviewed {
    background-color: #f0fff4;
    border-color: #22c55e;
}
.ref-text {
    font-size: 15px;
}
.ref-links a {
    margin-right: 14px;
    font-weight: 500;
    text-decoration: none;
}
.ref-links a:hover {
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ---------------- #

st.title("📚 Reference Reviewer")
st.caption(
    "Paste references → Open Google Scholar / PubMed Central → Mark as reviewed"
)

# ---------------- INPUT ---------------- #

refs_text = st.text_area(
    "Paste references (one per line)",
    height=220,
    placeholder="Author A et al. Title. Journal. Year.\nAuthor B et al. Title. Journal. Year."
)

# ---------------- SESSION STATE ---------------- #

if "refs" not in st.session_state:
    st.session_state.refs = []

if "reviewed" not in st.session_state:
    st.session_state.reviewed = {}

# ---------------- ACTION ---------------- #

if st.button("🔗 Generate Search Links", use_container_width=True):
    st.session_state.refs = [
        r.strip() for r in refs_text.splitlines() if r.strip()
    ]
    st.session_state.reviewed = {
        i: False for i in range(len(st.session_state.refs))
    }

# ---------------- STATS ---------------- #

if st.session_state.refs:
    reviewed_count = sum(st.session_state.reviewed.values())
    total = len(st.session_state.refs)

    st.markdown(
        f"### ✅ Reviewed **{reviewed_count} / {total}** references"
    )

# ---------------- DISPLAY ---------------- #

for i, ref in enumerate(st.session_state.refs):

    scholar_url = (
        "https://scholar.google.com/scholar?q="
        + urllib.parse.quote(ref)
    )

    pmc_url = (
        "https://www.ncbi.nlm.nih.gov/pmc/?term="
        + urllib.parse.quote(ref)
    )

    reviewed = st.session_state.reviewed.get(i, False)
    card_class = "ref-card ref-reviewed" if reviewed else "ref-card"

    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

    col_ref, col_links, col_check = st.columns([0.6, 0.25, 0.15])

    with col_ref:
        st.markdown(
            f'<div class="ref-text"><b>{i+1}.</b> {ref}</div>',
            unsafe_allow_html=True
        )

    with col_links:
        st.markdown(
            f'''
            <div class="ref-links">
                <a href="{scholar_url}" target="_blank">🔍 Google Scholar</a>
                <a href="{pmc_url}" target="_blank">🧬 PubMed Central</a>
            </div>
            ''',
            unsafe_allow_html=True
        )

    with col_check:
        st.session_state.reviewed[i] = st.checkbox(
            "Reviewed",
            value=reviewed,
            key=f"rev_{i}",
            label_visibility="collapsed"
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- EMPTY STATE ---------------- #

if not st.session_state.refs:
    st.info("Paste references above and click **Generate Search Links** to begin.")
import streamlit as st
import urllib.parse

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="Reference Reviewer",
    layout="wide"
)

# ---------------- CUSTOM CSS ---------------- #

st.markdown("""
<style>
.ref-card {
    padding: 14px;
    border-radius: 10px;
    border: 1px solid #e6e6e6;
    margin-bottom: 10px;
}
.ref-reviewed {
    background-color: #f0fff4;
    border-color: #22c55e;
}
.ref-text {
    font-size: 15px;
}
.ref-links a {
    margin-right: 14px;
    font-weight: 500;
    text-decoration: none;
}
.ref-links a:hover {
    text-decoration: underline;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ---------------- #

st.title("📚 Reference Reviewer")
st.caption(
    "Paste references → Open Google Scholar / PubMed Central → Mark as reviewed"
)

# ---------------- INPUT ---------------- #

refs_text = st.text_area(
    "Paste references (one per line)",
    height=220,
    placeholder="Author A et al. Title. Journal. Year.\nAuthor B et al. Title. Journal. Year."
)

# ---------------- SESSION STATE ---------------- #

if "refs" not in st.session_state:
    st.session_state.refs = []

if "reviewed" not in st.session_state:
    st.session_state.reviewed = {}

# ---------------- ACTION ---------------- #

if st.button("🔗 Generate Search Links", use_container_width=True):
    st.session_state.refs = [
        r.strip() for r in refs_text.splitlines() if r.strip()
    ]
    st.session_state.reviewed = {
        i: False for i in range(len(st.session_state.refs))
    }

# ---------------- STATS ---------------- #

if st.session_state.refs:
    reviewed_count = sum(st.session_state.reviewed.values())
    total = len(st.session_state.refs)

    st.markdown(
        f"### ✅ Reviewed **{reviewed_count} / {total}** references"
    )

# ---------------- DISPLAY ---------------- #

for i, ref in enumerate(st.session_state.refs):

    scholar_url = (
        "https://scholar.google.com/scholar?q="
        + urllib.parse.quote(ref)
    )

    pmc_url = (
        "https://www.ncbi.nlm.nih.gov/pmc/?term="
        + urllib.parse.quote(ref)
    )

    reviewed = st.session_state.reviewed.get(i, False)
    card_class = "ref-card ref-reviewed" if reviewed else "ref-card"

    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

    col_ref, col_links, col_check = st.columns([0.6, 0.25, 0.15])

    with col_ref:
        st.markdown(
            f'<div class="ref-text"><b>{i+1}.</b> {ref}</div>',
            unsafe_allow_html=True
        )

    with col_links:
        st.markdown(
            f'''
            <div class="ref-links">
                <a href="{scholar_url}" target="_blank">🔍 Google Scholar</a>
                <a href="{pmc_url}" target="_blank">🧬 PubMed Central</a>
            </div>
            ''',
            unsafe_allow_html=True
        )

    with col_check:
        st.session_state.reviewed[i] = st.checkbox(
            "Reviewed",
            value=reviewed,
            key=f"rev_{i}",
            label_visibility="collapsed"
        )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- EMPTY STATE ---------------- #

if not st.session_state.refs:
    st.info("Paste references above and click **Generate Search Links** to begin.")
