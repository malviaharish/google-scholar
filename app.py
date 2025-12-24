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
UNPAYWALL_EMAIL = st.secrets.get("UNPAYWALL_EMAIL", "your_email@institute.edu") 
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/pdf,text/html"
}

# ===================== UI ===================== #
st.set_page_config(
    page_title="Reference / DOI → OA PDF Downloader",
    layout="wide"
)

st.title("📚 Reference / DOI → Open Access PDF Downloader")
st.caption("Search & download Open Access PDFs from Unpaywall, PMC & publisher OA pages")

input_text = st.text_area(
    "Paste References OR DOIs (one per line)",
    height=220,
    placeholder="Author A et al. Title. Journal. Year\n10.1000/j.jmb.2020.01.001"
)

# ===================== FUNCTIONS ===================== #
def is_doi(text):
    return bool(re.search(r"10\.\d{4,9}/", text))

def clean_doi(doi: str) -> str:
    doi = doi.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi

def query_unpaywall(doi: str):
    url = f"https://api.unpaywall.org/v2/{doi}"
    params = {"email": UNPAYWALL_EMAIL}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
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
    except Exception:
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
        content_type = r.headers.get("Content-Type", "").lower()
        if r.status_code == 200 and "pdf" in content_type:
            with open(filepath, "wb") as f:
                f.write(r.content)
            return "Downloaded"
        else:
            return "Blocked or HTML"
    except Exception as e:
        return f"Error: {str(e)}"

def zip_downloads(zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for pdf in DOWNLOAD_DIR.glob("*.pdf"):
            z.write(pdf, pdf.name)

def make_clickable(url):
    if not url:
        return ""
    return f'<a href="{url}" target="_blank" style="background:#2563eb;color:white;padding:4px 8px;border-radius:5px;text-decoration:none;font-weight:500;">Open</a>'

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
        "Journal": doc.get("fulljournalname", ""),
        "Year": doc.get("pubdate", "")[:4],
        "DOI": doc.get("elocationid", "").replace("doi:", ""),
        "PMCID": f"PMC{pmcid}"
    }

def download_pmc_pdf(pmcid):
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
    path = DOWNLOAD_DIR / f"{pmcid}.pdf"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200 and "pdf" in r.headers.get("Content-Type", ""):
        path.write_bytes(r.content)
        return True
    return False

def generate_ris(df):
    ris_str = ""
    for _, row in df.iterrows():
        ris_str += "TY  - JOUR\n"
        ris_str += f"TI  - {row.get('Title','')}\n"
        ris_str += f"JO  - {row.get('Journal','')}\n"
        ris_str += f"PY  - {row.get('Year','')}\n"
        if row.get("DOI"):
            ris_str += f"DO  - {row.get('DOI')}\n"
        if row.get("PMCID"):
            ris_str += f"UR  - https://www.ncbi.nlm.nih.gov/pmc/articles/{row.get('PMCID')}/\n"
        ris_str += "ER  - \n\n"
    return ris_str

# ===================== PROCESS ===================== #

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
            "PDF_Link": "",
            "Download_Status": "",
            "Scholar_Link": f"https://scholar.google.com/scholar?q={quote(item)}",
            "PMC_Search_Link": f"https://www.ncbi.nlm.nih.gov/pmc/?term={quote(item)}"
        }

        if is_doi(item):
            doi = clean_doi(item)
            record["DOI"] = doi
            data = query_unpaywall(doi)
            if data and data.get("is_oa"):
                url, url_type = get_pdf_or_landing(data)
                if url:
                    record["OA"] = "Yes"
                    pdf_file = DOWNLOAD_DIR / f"{doi.replace('/', '_')}.pdf"
                    if url_type == "pdf":
                        record["PDF_Link"] = url
                        record["Download_Status"] = download_pdf(url, pdf_file)
                    else:
                        extracted_pdf = extract_pdf_from_html(url)
                        if extracted_pdf:
                            record["PDF_Link"] = extracted_pdf
                            record["Download_Status"] = download_pdf(extracted_pdf, pdf_file)
                        else:
                            record["Download_Status"] = "OA page but PDF not found"
                else:
                    record["Download_Status"] = "OA but no usable link"
            else:
                record["Download_Status"] = "Not Open Access"
        else:
            pmcid = pmc_search(item)
            if pmcid:
                meta = pmc_metadata(pmcid)
                record.update(meta)
                if download_pmc_pdf(meta["PMCID"]):
                    record["OA"] = "Yes"
                    record["PDF_Link"] = str(DOWNLOAD_DIR / f"{meta['PMCID']}.pdf")
                    record["Download_Status"] = "Downloaded"
                else:
                    record["Download_Status"] = "PDF not available"

        results.append(record)
        progress.progress((i + 1) / len(lines))

    df = pd.DataFrame(results)
    # Add clickable links
    df["PDF_Link"] = df["PDF_Link"].apply(make_clickable)
    df["Scholar_Link"] = df["Scholar_Link"].apply(make_clickable)
    df["PMC_Search_Link"] = df["PMC_Search_Link"].apply(make_clickable)

    # ===================== EDITABLE TABLE ===================== #
    st.markdown("### ✏️ Edit table if needed")
    df_edit = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    # ===================== EXPORT ===================== #
    csv_data = df_edit.drop(columns=["PDF_Link", "Scholar_Link", "PMC_Search_Link"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV Report", csv_data, "oa_results.csv", "text/csv")

    ris_data = generate_ris(df_edit)
    st.download_button("⬇️ Download RIS File", ris_data, "oa_results.ris", "text/plain")

    # Export ZIP of PDFs
    zip_path = Path("oa_pdfs.zip")
    zip_downloads(zip_path)
    if zip_path.exists():
        with open(zip_path, "rb") as f:
            st.download_button("📦 Download All PDFs (ZIP)", f, file_name="oa_pdfs.zip", mime="application/zip")

# ===================== FOOTER ===================== #
st.markdown("""
---
**Sources:** Unpaywall • PubMed Central • Google Scholar • Publisher OA  
**Compliance:** 100% Legal Open Access (No Sci-Hub / Anna’s Archive)
""")
