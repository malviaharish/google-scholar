import streamlit as st
import requests
import pandas as pd
import os
import time
import zipfile
from pathlib import Path
from urllib.parse import quote

# ================= PAGE CONFIG ================= #
st.set_page_config(
    page_title="Reference → PMC OA Downloader",
    layout="wide"
)

# ================= NCBI CONFIG ================= #
NCBI_API_KEY = st.secrets.get("NCBI_API_KEY", os.getenv("NCBI_API_KEY"))
NCBI_EMAIL = "your_email@institute.edu"

REQUEST_DELAY = 0.34  # NCBI safe (~3 requests/sec with API key)

BASE_DIR = Path("pmc_output")
PDF_DIR = BASE_DIR / "pdfs"
BASE_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

# ================= SESSION STATE ================= #
if "refs" not in st.session_state:
    st.session_state.refs = []

if "reviewed" not in st.session_state:
    st.session_state.reviewed = {}

if "metadata" not in st.session_state:
    st.session_state.metadata = {}

# ================= STYLES ================= #
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

# ================= HEADER ================= #
st.title("📚 Reference → PMC Open-Access Downloader")
st.caption(
    "Bulk OA detection • PDF download • Metadata fetch • DOI mapping • ZIP export"
)

# ================= INPUT ================= #
refs_text = st.text_area(
    "Paste references (one per line)",
    height=220,
    placeholder="Author A et al. Title. Journal. Year."
)

if st.button("🔍 Process References"):
    st.session_state.refs = [r.strip() for r in refs_text.splitlines() if r.strip()]
    st.session_state.reviewed = {i: False for i in range(len(st.session_state.refs))}
    st.session_state.metadata = {}

# ================= PMC FUNCTIONS ================= #
def ncbi_get(url, params):
    params["api_key"] = NCBI_API_KEY
    params["email"] = NCBI_EMAIL
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

def pmc_fetch_metadata(pmcid):
    r = ncbi_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        {"db": "pmc", "id": pmcid, "retmode": "json"}
    )
    doc = r.json()["result"][pmcid]
    return {
        "Title": doc.get("title"),
        "Journal": doc.get("fulljournalname"),
        "Year": doc.get("pubdate", "")[:4],
        "DOI": doc.get("elocationid", "").replace("doi:", "")
    }

def download_pmc_pdf(pmcid):
    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/pdf/"
    pdf_path = PDF_DIR / f"PMC{pmcid}.pdf"
    r = requests.get(pdf_url, stream=True, timeout=30)
    if r.status_code == 200 and "application/pdf" in r.headers.get("Content-Type", ""):
        with open(pdf_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return pdf_path
    return None

# ================= RESULTS ================= #
if st.session_state.refs:

    st.markdown("## 🔗 Results")

    for i, ref in enumerate(st.session_state.refs):

        scholar_url = f"https://scholar.google.com/scholar?q={quote(ref)}"
        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/?term={quote(ref)}"

        col1, col2 = st.columns([7, 2])

        with col1:
            st.markdown(
                f"""
                <div class="ref-card">
                    <strong>{i+1}.</strong> {ref}
                    <div class="links">
                        <a href="{scholar_url}" target="_blank">🔍 Scholar</a>
                        <a href="{pmc_url}" target="_blank">📖 PMC</a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if i not in st.session_state.metadata:
                pmcid = pmc_search(ref)
                if pmcid:
                    meta = pmc_fetch_metadata(pmcid)
                    meta["PMCID"] = f"PMC{pmcid}"
                    st.session_state.metadata[i] = meta
                else:
                    st.session_state.metadata[i] = None

            meta = st.session_state.metadata[i]

            if meta:
                st.write(
                    f"**{meta['Title']}**  \n"
                    f"{meta['Journal']} ({meta['Year']})  \n"
                    f"PMCID: {meta['PMCID']} | DOI: {meta['DOI'] or 'N/A'}"
                )

                if st.button("⬇️ Download PDF", key=f"dl_{i}"):
                    pdf = download_pmc_pdf(meta["PMCID"].replace("PMC", ""))
                    if pdf:
                        st.success("Downloaded")
                        st.markdown(f"[📄 Open PDF](sandbox:/{pdf})")
                    else:
                        st.warning("PDF not available")

            else:
                st.info("No OA article found")

        with col2:
            st.checkbox(
                "Reviewed",
                key=f"rev_{i}",
                value=st.session_state.reviewed.get(i),
                on_change=lambda idx=i: st.session_state.reviewed.update(
                    {idx: not st.session_state.reviewed[idx]}
                )
            )

    # ================= BULK DOWNLOAD ================= #
    st.markdown("---")
    if st.button("⬇️ Bulk Download All OA PDFs"):
        for meta in st.session_state.metadata.values():
            if meta:
                download_pmc_pdf(meta["PMCID"].replace("PMC", ""))
        st.success("Bulk download complete")

    # ================= ZIP EXPORT ================= #
    zip_path = BASE_DIR / "pmc_pdfs.zip"
    if st.button("📦 Create ZIP"):
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for pdf in PDF_DIR.glob("*.pdf"):
                zipf.write(pdf, pdf.name)
        st.success("ZIP ready")
        st.markdown(f"[⬇️ Download ZIP](sandbox:/{zip_path})")

    # ================= CSV EXPORT ================= #
    st.markdown("## 📤 Export CSV")

    rows = []
    for i, ref in enumerate(st.session_state.refs):
        meta = st.session_state.metadata.get(i)
        rows.append({
            "Reference": ref,
            "Reviewed": st.session_state.reviewed[i],
            "PMCID": meta["PMCID"] if meta else "",
            "DOI": meta["DOI"] if meta else "",
            "Title": meta["Title"] if meta else "",
            "Journal": meta["Journal"] if meta else "",
            "Year": meta["Year"] if meta else ""
        })

    df = pd.DataFrame(rows)
    csv_path = BASE_DIR / "review_status.csv"
    df.to_csv(csv_path, index=False)

    st.download_button(
        "⬇️ Download CSV",
        data=df.to_csv(index=False),
        file_name="review_status.csv",
        mime="text/csv"
    )
