import streamlit as st
import requests
import pandas as pd
import os
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

# ================= CONFIG ================= #
st.set_page_config(page_title="Literature Mining Suite", layout="wide")

NCBI_API_KEY = st.secrets.get("NCBI_API_KEY", os.getenv("NCBI_API_KEY"))
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", os.getenv("UNPAYWALL_EMAIL"))
NCBI_EMAIL = UNPAYWALL_EMAIL

REQUEST_DELAY = 0.34

BASE_DIR = Path("output")
PDF_DIR = BASE_DIR / "pdfs"
BASE_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

# ================= SESSION ================= #
for key in ["refs", "reviewed", "metadata"]:
    if key not in st.session_state:
        st.session_state[key] = {} if key != "refs" else []

# ================= NCBI HELPERS ================= #
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
    ids = r.json()["esearchresult"]["idlist"]
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
        "Year": doc.get("pubdate", "")[:4]
    }

# ================= UNPAYWALL ================= #
def unpaywall_lookup(doi):
    if not doi:
        return None
    url = f"https://api.unpaywall.org/v2/{doi}"
    r = requests.get(url, params={"email": UNPAYWALL_EMAIL}, timeout=20)
    if r.status_code == 200:
        data = r.json()
        return {
            "OA": data["is_oa"],
            "OA_Type": data.get("oa_status"),
            "OA_URL": data.get("best_oa_location", {}).get("url")
        }
    return None

# ================= SEARCH STRING BUILDER ================= #
st.title("🔍 Search-String Builder (PubMed / Europe PMC)")

with st.expander("Build Search String", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        keywords = st.text_input("Keywords")
        title = st.text_input("Title contains")
        abstract = st.text_input("Abstract contains")
        mesh = st.text_input("MeSH terms")
        author = st.text_input("Author")
        journal = st.text_input("Journal")
        year_from = st.number_input("From Year", 1900, 2100, 2000)
        year_to = st.number_input("To Year", 1900, 2100, 2025)

    with col2:
        article_type = st.selectbox(
            "Article Type",
            ["", "Clinical Trial", "Review", "Meta-Analysis", "Randomized Controlled Trial"]
        )
        species = st.selectbox("", ["", "Humans", "Animals"])
        has_doi = st.checkbox("Has DOI")
        has_pmc = st.checkbox("Has PMCID")
        boolean = st.selectbox("Combine with", ["AND", "OR", "NOT"])

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
    europmc_query = pubmed_query.replace("[Title]", "TITLE:").replace("[Abstract]", "ABSTRACT:")

    st.markdown("### PubMed Search String")
    st.code(pubmed_query)

    st.markdown("### Europe PMC Search String")
    st.code(europmc_query)

# ================= REFERENCE INPUT ================= #
st.markdown("---")
refs_text = st.text_area("Paste references (one per line)", height=180)

if st.button("Process References"):
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
                meta["Unpaywall"] = unpaywall_lookup(meta["DOI"])
                st.session_state.metadata[i] = meta
            else:
                st.session_state.metadata[i] = None

        meta = st.session_state.metadata[i]
        st.subheader(ref)

        if meta:
            st.write(meta)
        else:
            st.warning("No OA match found")

        st.checkbox(
            "Reviewed",
            key=f"rev_{i}",
            value=st.session_state.reviewed[i],
            on_change=lambda idx=i: st.session_state.reviewed.update(
                {idx: not st.session_state.reviewed[idx]}
            )
        )

# ================= EXPORT ================= #
st.markdown("---")
rows = []
for i, ref in enumerate(st.session_state.refs):
    meta = st.session_state.metadata.get(i)
    rows.append({
        "Reference": ref,
        "Reviewed": st.session_state.reviewed[i],
        **(meta or {})
    })

df = pd.DataFrame(rows)

excel_path = BASE_DIR / "literature_review.xlsx"
df.to_excel(excel_path, index=False)

st.download_button(
    "⬇️ Download Excel",
    data=df.to_excel(index=False, engine="openpyxl"),
    file_name="literature_review.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
