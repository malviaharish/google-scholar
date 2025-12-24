import streamlit as st
import requests
import pandas as pd
import os
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

# ================= PAGE CONFIG ================= #
st.set_page_config(page_title="Literature Mining Suite", layout="wide")

# ================= API CONFIG ================= #
NCBI_API_KEY = st.secrets.get("NCBI_API_KEY", os.getenv("NCBI_API_KEY"))
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", os.getenv("UNPAYWALL_EMAIL"))
NCBI_EMAIL = UNPAYWALL_EMAIL or "your_email@institute.edu"

REQUEST_DELAY = 0.34  # NCBI safe

# ================= SESSION STATE ================= #
if "refs" not in st.session_state:
    st.session_state.refs = []

if "reviewed" not in st.session_state:
    st.session_state.reviewed = {}

if "metadata" not in st.session_state:
    st.session_state.metadata = {}

# ================= HELPERS ================= #
def ncbi_get(url, params):
    params.update({"api_key": NCBI_API_KEY, "email": NCBI_EMAIL})
    r = requests.get(url, params=params, timeout=30)
    time.sleep(REQUEST_DELAY)
    r.raise_for_status()
    return r

def pmc_search(query):
    r = ncbi_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "pmc", "term": query, "retmode": "json", "retmax": 1}
    )
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    return ids[0] if ids else None

def cross_map_ids(pmcid):
    r = ncbi_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        {"db": "pmc", "id": pmcid, "retmode": "json"}
    )
    doc = r.json()["result"][pmcid]
    return {
        "PMCID": f"PMC{pmcid}",
        "PMID": doc.get("articleids", {}).get("pmid"),
        "DOI": doc.get("elocationid", "").replace("doi:", ""),
        "Title": doc.get("title"),
        "Journal": doc.get("fulljournalname"),
        "Year": doc.get("pubdate", "")[:4],
    }

def unpaywall_lookup(doi):
    if not doi or not UNPAYWALL_EMAIL:
        return {}
    url = f"https://api.unpaywall.org/v2/{doi}"
    r = requests.get(url, params={"email": UNPAYWALL_EMAIL}, timeout=20)
    if r.status_code == 200:
        d = r.json()
        return {
            "OA": d.get("is_oa"),
            "OA_Type": d.get("oa_status"),
            "OA_URL": d.get("best_oa_location", {}).get("url"),
        }
    return {}

# ================= UI ================= #
st.title("📚 Literature Mining & Systematic Review Tool")
st.caption(
    "PMC OA detection • PMID↔PMCID↔DOI mapping • Unpaywall • Excel export • Search builder"
)

# ================= SEARCH STRING BUILDER ================= #
st.markdown("## 🔍 Search-String Builder (PubMed / Europe PMC)")

with st.expander("Build Search String", expanded=True):
    c1, c2 = st.columns(2)

    with c1:
        keywords = st.text_input("Keywords (All fields)")
        title = st.text_input("Title")
        abstract = st.text_input("Abstract")
        mesh = st.text_input("MeSH terms")
        author = st.text_input("Author")
        journal = st.text_input("Journal")
        year_from = st.number_input("From year", 1900, 2100, 2000)
        year_to = st.number_input("To year", 1900, 2100, 2025)

    with c2:
        article_type = st.selectbox(
            "Article type",
            ["", "Clinical Trial", "Review", "Meta-Analysis", "Randomized Controlled Trial"]
        )
        species = st.selectbox("Species", ["", "Humans", "Animals"])
        boolean = st.selectbox("Boolean operator", ["AND", "OR", "NOT"])

    pubmed_terms = []
    if keywords:
        pubmed_terms.append(f"{keywords}[All Fields]")
    if title:
        pubmed_terms.append(f"{title}[Title]")
    if abstract:
        pubmed_terms.append(f"{abstract}[Abstract]")
    if mesh:
        pubmed_terms.append(f"{mesh}[MeSH Terms]")
    if author:
        pubmed_terms.append(f"{author}[Author]")
    if journal:
        pubmed_terms.append(f"{journal}[Journal]")
    if article_type:
        pubmed_terms.append(f"{article_type}[Publication Type]")
    if species:
        pubmed_terms.append(f"{species}[MeSH Terms]")

    pubmed_terms.append(f"{year_from}:{year_to}[dp]")

    pubmed_query = f" {boolean} ".join(pubmed_terms)

    europmc_query = (
        pubmed_query
        .replace("[Title]", "TITLE:")
        .replace("[Abstract]", "ABSTRACT:")
        .replace("[Author]", "AUTHOR:")
        .replace("[Journal]", "JOURNAL:")
    )

    st.markdown("### PubMed")
    st.code(pubmed_query)

    st.markdown("### Europe PMC")
    st.code(europmc_query)

# ================= REFERENCES ================= #
st.markdown("---")
refs_text = st.text_area("Paste references (one per line)", height=200)

if st.button("🔍 Process References"):
    st.session_state.refs = [r.strip() for r in refs_text.splitlines() if r.strip()]
    st.session_state.reviewed = {i: False for i in range(len(st.session_state.refs))}
    st.session_state.metadata = {}

# ================= PROCESS ================= #
if st.session_state.refs:
    st.markdown("## 📄 Results")

    for i, ref in enumerate(st.session_state.refs):

        if i not in st.session_state.metadata:
            pmcid = pmc_search(ref)
            if pmcid:
                meta = cross_map_ids(pmcid)
                meta.update(unpaywall_lookup(meta.get("DOI")))
                st.session_state.metadata[i] = meta
            else:
                st.session_state.metadata[i] = None

        meta = st.session_state.metadata[i]

        st.markdown(f"### {i+1}. {ref}")

        if meta:
            st.json(meta)
        else:
            st.warning("No Open-Access PMC record found")

        st.checkbox(
            "Reviewed",
            key=f"rev_{i}",
            value=st.session_state.reviewed[i],
            on_change=lambda idx=i: st.session_state.reviewed.update(
                {idx: not st.session_state.reviewed[idx]}
            )
        )

# ================= EXPORT ================= #
if st.session_state.refs:
    st.markdown("---")
    st.markdown("## 📤 Export")

    rows = []
    for i, ref in enumerate(st.session_state.refs):
        meta = st.session_state.metadata.get(i) or {}
        rows.append({
            "Reference": ref,
            "Reviewed": st.session_state.reviewed[i],
            **meta
        })

    df = pd.DataFrame(rows)

    # ---------- CSV ---------- #
    st.download_button(
        "⬇️ Download CSV",
        data=df.to_csv(index=False),
        file_name="literature_review.csv",
        mime="text/csv"
    )

    # ---------- EXCEL (SAFE) ---------- #
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Literature Review")
    excel_buffer.seek(0)

    st.download_button(
        "⬇️ Download Excel",
        data=excel_buffer,
        file_name="literature_review.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
