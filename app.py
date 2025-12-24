import streamlit as st
import requests
import pandas as pd
from pathlib import Path
import zipfile
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import time

# ===================== CONFIG ===================== #

UNPAYWALL_EMAIL = "your_email@institute.edu"   # REQUIRED
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/pdf,text/html"
}

# ===================== STREAMLIT UI ===================== #

st.set_page_config(
    page_title="Reference / DOI → OA PDF Downloader",
    layout="wide"
)

st.title("📚 Reference / DOI → Open Access PDF Downloader")
st.caption("Downloads **legal Open Access PDFs only** using Unpaywall, PMC & publisher OA pages")

input_text = st.text_area(
    "Paste References OR DOIs (one per line)",
    height=220,
    placeholder="Author A et al. Title. Journal. Year.\n10.1000/j.jmb.2020.01.001"
)

# ===================== FUNCTIONS ===================== #

def is_doi(text):
    return bool(re.search(r"10\.\d{4,9}/", text))

def clean_doi(doi: str) -> str:
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())

def query_unpaywall(doi: str):
    try:
        r = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": UNPAYWALL_EMAIL},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def extract_pdf_from_html(page_url: str):
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")

        meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
        if meta and meta.get("content"):
            return meta["content"]

        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                return urljoin(page_url, a["href"])
    except:
        pass
    return None

def get_pdf_or_landing(unpaywall_data):
    locations = []
    if unpaywall_data.get("best_oa_location"):
        locations.append(unpaywall_data["best_oa_location"])
    locations.extend(unpaywall_data.get("oa_locations", []))

    for loc in locations:
        if loc.get("url_for_pdf"):
            return loc["url_for_pdf"], "pdf"
        if loc.get("url"):
            if "ncbi.nlm.nih.gov/pmc/articles" in loc["url"]:
                return loc["url"].rstrip("/") + "/pdf", "pdf"
            return loc["url"], "html"
    return None, None

def download_pdf(pdf_url: str, filepath: Path) -> str:
    try:
        r = requests.get(pdf_url, headers=HEADERS, timeout=30)
        if r.status_code == 200 and "pdf" in r.headers.get("Content-Type", ""):
            filepath.write_bytes(r.content)
            return "Downloaded"
    except Exception as e:
        return f"Error: {e}"
    return "Blocked or HTML"

def ncbi_get(url, params):
    r = requests.get(url, params=params, timeout=30)
    time.sleep(0.34)
    r.raise_for_status()
    return r

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
        "Title": doc.get("title", ""),
        "Journal_Details": f"{doc.get('fulljournalname','')} | {doc.get('pubdate','')[:4]}",
        "DOI": doc.get("elocationid", "").replace("doi:", ""),
        "PMCID": f"PMC{pmcid}"
    }

def make_button(url, label):
    if not url:
        return ""
    return f"""
    <a href="{url}" target="_blank"
       style="background:#2563eb;color:white;padding:5px 10px;
       border-radius:6px;text-decoration:none;font-weight:600;">
       {label}
    </a>
    """

# ===================== MAIN LOGIC ===================== #

if st.button("🔍 Process"):

    results = []
    lines = [l.strip() for l in input_text.splitlines() if l.strip()]
    progress = st.progress(0)

    for i, item in enumerate(lines):

        record = {
            "Input": item,
            "Type": "DOI" if is_doi(item) else "Reference",
            "Title": "",
            "Journal_Details": "",
            "DOI": "",
            "PMCID": "",
            "OA": "No",
            "PDF": "",
            "PubMed": make_button(
                f"https://pubmed.ncbi.nlm.nih.gov/?term={quote(item)}", "PubMed"
            ),
            "Scholar": make_button(
                f"https://scholar.google.com/scholar?q={quote(item)}", "Scholar"
            ),
            "Status": ""
        }

        # DOI flow
        if is_doi(item):
            doi = clean_doi(item)
            record["DOI"] = doi
            data = query_unpaywall(doi)

            if data and data.get("is_oa"):
                url, t = get_pdf_or_landing(data)
                if url:
                    record["OA"] = "Yes"
                    pdf_path = DOWNLOAD_DIR / f"{doi.replace('/', '_')}.pdf"
                    record["Status"] = download_pdf(url, pdf_path)
                    record["PDF"] = make_button(url, "PDF")

        # Reference flow
        else:
            pmcid = pmc_search(item)
            if pmcid:
                meta = pmc_metadata(pmcid)
                record.update(meta)
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{meta['PMCID']}/pdf/"
                record["OA"] = "Yes"
                record["PDF"] = make_button(pdf_url, "PDF")
                record["Status"] = "Available"

        results.append(record)
        progress.progress((i + 1) / len(lines))

    df = pd.DataFrame(results)

    st.success("✅ Processing complete")

    st.markdown(
        df.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )

# ===================== FOOTER ===================== #

st.markdown(
    """
    ---
    **Sources:** Unpaywall • PubMed Central • Google Scholar  
    **Compliance:** 100% Legal Open Access
    """
)
