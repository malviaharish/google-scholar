import streamlit as st
import requests
import pandas as pd
import time
import re
import zipfile
from pathlib import Path
from urllib.parse import quote
from bs4 import BeautifulSoup

# ================= PAGE CONFIG ================= #
st.set_page_config(
    page_title="Reference / DOI → OA PDF Downloader",
    layout="wide"
)

# ================= CONFIG ================= #
NCBI_API_KEY = st.secrets.get("NCBI_API_KEY")
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL")

REQUEST_DELAY = 0.34  # NCBI safe with API key

BASE_DIR = Path("output")
PDF_DIR = BASE_DIR / "pdfs"
BASE_DIR.mkdir(exist_ok=True)
PDF_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/pdf,text/html"
}

# ================= SESSION ================= #
if "items" not in st.session_state:
    st.session_state.items = []

if "results" not in st.session_state:
    st.session_state.results = []

# ================= UI ================= #
st.title("📚 Reference / DOI → Open Access PDF Downloader")
st.caption(
    "Unpaywall • PubMed Central • Google Scholar | Legal Open Access only"
)

input_text = st.text_area(
    "Paste References OR DOIs (one per line)",
    height=220,
    placeholder="Author A et al. Title. Journal. Year.\n10.1000/j.jmb.2020.01.001"
)

# ================= HELPERS ================= #
def is_doi(text):
    return bool(re.search(r"10\.\d{4,9}/", text))

def clean_doi(doi):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())

def ncbi_get(url, params):
    params["api_key"] = NCBI_API_KEY
    params["email"] = UNPAYWALL_EMAIL
    r = requests.get(url, params=params, timeout=30)
    time.sleep(REQUEST_DELAY)
    r.raise_for_status()
    return r

# ================= UNPAYWALL ================= #
def query_unpaywall(doi):
    url = f"https://api.unpaywall.org/v2/{doi}"
    r = requests.get(url, params={"email": UNPAYWALL_EMAIL}, timeout=20)
    return r.json() if r.status_code == 200 else None

def extract_pdf_from_html(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "lxml")

    meta = soup.find("meta", {"name": "citation_pdf_url"})
    if meta:
        return meta.get("content")

    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            return a["href"]
    return None

# ================= PMC ================= #
def pmc_search(query):
    r = ncbi_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        {"db": "pmc", "term": query, "retmode": "json", "retmax": 1}
    )
    ids = r.json()["esearchresult"]["idlist"]
    return ids[0] if ids else None

def pmc_metadata(pmcid):
    r = ncbi_get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
        {"db": "pmc", "id": pmcid, "retmode": "json"}
    )
    doc = r.json()["result"][pmcid]
    return {
        "Title": doc.get("title"),
        "Journal": doc.get("fulljournalname"),
        "Year": doc.get("pubdate", "")[:4],
        "DOI": doc.get("elocationid", "").replace("doi:", ""),
        "PMCID": f"PMC{pmcid}"
    }

def download_pmc_pdf(pmcid):
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
    path = PDF_DIR / f"{pmcid}.pdf"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200 and "pdf" in r.headers.get("Content-Type", ""):
        path.write_bytes(r.content)
        return True
    return False

# ================= PROCESS ================= #
if st.button("🔍 Process"):

    lines = [l.strip() for l in input_text.splitlines() if l.strip()]
    results = []

    progress = st.progress(0)

    for i, item in enumerate(lines):

        record = {
            "Input": item,
            "Type": "DOI" if is_doi(item) else "Reference",
            "Title": "",
            "Journal": "",
            "Year": "",
            "DOI": "",
            "PMCID": "",
            "OA": "No",
            "PDF": ""
        }

        scholar_url = f"https://scholar.google.com/scholar?q={quote(item)}"
        pmc_search_url = f"https://www.ncbi.nlm.nih.gov/pmc/?term={quote(item)}"

        # ---------- DOI FLOW ----------
        if is_doi(item):
            doi = clean_doi(item)
            record["DOI"] = doi
            data = query_unpaywall(doi)

            if data and data.get("is_oa"):
                loc = data.get("best_oa_location")
                pdf_url = loc.get("url_for_pdf") or extract_pdf_from_html(loc.get("url"))

                if pdf_url:
                    pdf_path = PDF_DIR / f"{doi.replace('/', '_')}.pdf"
                    r = requests.get(pdf_url, headers=HEADERS, timeout=30)
                    if r.status_code == 200 and "pdf" in r.headers.get("Content-Type", ""):
                        pdf_path.write_bytes(r.content)
                        record["OA"] = "Yes"
                        record["PDF"] = str(pdf_path)

        # ---------- REFERENCE FLOW ----------
        else:
            pmcid = pmc_search(item)
            if pmcid:
                meta = pmc_metadata(pmcid)
                record.update(meta)
                if download_pmc_pdf(meta["PMCID"]):
                    record["OA"] = "Yes"
                    record["PDF"] = str(PDF_DIR / f"{meta['PMCID']}.pdf")

        record["Scholar"] = scholar_url
        record["PMC_Search"] = pmc_search_url
        results.append(record)
        progress.progress((i + 1) / len(lines))

    st.session_state.results = results

# ================= DISPLAY ================= #
if st.session_state.results:

    df = pd.DataFrame(st.session_state.results)

    st.success("✅ Processing complete")

    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Scholar": st.column_config.LinkColumn("Scholar"),
            "PMC_Search": st.column_config.LinkColumn("PMC")
        }
    )

    # ---------- EXPORTS ----------
    st.markdown("### 📤 Exports")

    st.download_button(
        "⬇️ Download CSV",
        df.to_csv(index=False),
        "oa_results.csv",
        "text/csv"
    )

    zip_path = BASE_DIR / "oa_pdfs.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        for pdf in PDF_DIR.glob("*.pdf"):
            z.write(pdf, pdf.name)

    with open(zip_path, "rb") as f:
        st.download_button(
            "📦 Download PDFs (ZIP)",
            f,
            "oa_pdfs.zip",
            "application/zip"
        )

# ================= FOOTER ================= #
st.markdown(
    """
    ---
    **Sources:** Unpaywall • PubMed Central • Google Scholar  
    **Compliance:** Legal Open Access only
    """
)
