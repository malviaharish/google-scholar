import streamlit as st
import requests
import pandas as pd
from pathlib import Path
import zipfile
import time
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from requests.exceptions import RequestException, ConnectTimeout, ReadTimeout
import re

# ================= CONFIG ================= #

UNPAYWALL_EMAIL = "your_real_email@institute.edu"   # REQUIRED
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ================= UI ================= #

st.set_page_config("Literature OA Downloader", layout="wide")
st.title("📚 Reference / DOI → Open Access PDF Downloader")
st.caption("Primary source: PubMed | OA: PubMed Central → Unpaywall")

input_text = st.text_area(
    "Paste DOI / PMID / Reference (one per line)",
    height=220
)

# ================= CSS ================= #

st.markdown("""
<style>
table { width:100%; border-collapse:collapse; }
th, td {
    text-align:center !important;
    padding:8px;
    vertical-align:middle;
}
th { background:#f1f5f9; font-weight:700; }
</style>
""", unsafe_allow_html=True)

# ================= HELPERS ================= #

def make_btn(url, label, color="#2563eb"):
    if not url:
        return ""
    return f"""
    <a href="{url}" target="_blank"
       style="
       display:inline-flex;
       align-items:center;
       justify-content:center;
       gap:6px;
       padding:6px 14px;
       margin:2px;
       border-radius:999px;
       background:{color};
       color:white;
       font-weight:600;
       text-decoration:none;
       font-size:13px;">
       {label}
    </a>
    """

def is_doi(text):
    return bool(re.match(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", text, re.I))

def is_pmid(text):
    return text.isdigit()

# ================= PUBMED SEARCH ================= #

def pubmed_search(query):
    try:
        if is_doi(query):
            term = f"{query}[DOI]"
        else:
            term = f"{query}[Title]"

        r = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": 1
            },
            timeout=10
        )

        ids = r.json().get("esearchresult", {}).get("idlist", [])
        return ids[0] if ids else None

    except Exception:
        return None

# ================= PUBMED FETCH ================= #

def pubmed_fetch(pmid):
    try:
        r = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pubmed", "id": pmid, "retmode": "xml"},
            timeout=10
        )

        soup = BeautifulSoup(r.text, "lxml")
        article = soup.find("pubmedarticle")
        if not article:
            return {}

        title = article.find("articletitle")
        title = title.text.strip() if title else ""

        journal = ""
        journal_tag = article.find("journal")
        if journal_tag and journal_tag.find("title"):
            journal = journal_tag.find("title").text.strip()

        year = ""
        pubdate = article.find("pubdate")
        if pubdate and pubdate.find("year"):
            year = pubdate.find("year").text.strip()

        authors = []
        for a in article.find_all("author"):
            if a.find("lastname") and a.find("forename"):
                authors.append(f"{a.find('lastname').text} {a.find('forename').text}")

        doi, pmcid = "", ""
        for aid in article.find_all("articleid"):
            if aid.get("idtype") == "doi":
                doi = aid.text.strip()
            elif aid.get("idtype") == "pmc":
                pmcid = aid.text.strip()

        return {
            "Title": title,
            "Journal": journal,
            "Year": year,
            "Authors": ", ".join(authors),
            "PMID": pmid,
            "DOI": doi,
            "PMCID": pmcid
        }

    except Exception:
        return {}

# ================= UNPAYWALL ================= #

def unpaywall(doi):
    try:
        r = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": UNPAYWALL_EMAIL},
            timeout=10
        )
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

# ================= PDF EXTRACTION ================= #

def extract_pdf(page):
    try:
        r = requests.get(page, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "lxml")
        meta = soup.find("meta", {"name": "citation_pdf_url"})
        if meta:
            return meta["content"]
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                return urljoin(page, a["href"])
    except Exception:
        return None
    return None

# ================= MAIN ================= #

if st.button("🔍 Process"):

    rows = []
    lines = [l.strip() for l in input_text.splitlines() if l.strip()]
    prog = st.progress(0.0)

    for i, x in enumerate(lines):

        rec = {
            "Input": x,
            "Title": "",
            "Journal": "",
            "Year": "",
            "Authors": "",
            "DOI": "",
            "PMID": "",
            "PMCID": "",
            "OA": "No",
            "PDF": "",
            "Status": "",
            "Scholar": make_btn(f"https://scholar.google.com/scholar?q={quote(x)}", "Scholar"),
            "PubMed": make_btn(f"https://pubmed.ncbi.nlm.nih.gov/?term={quote(x)}", "PubMed"),
        }

        if is_pmid(x):
            pmid = x
        else:
            pmid = pubmed_search(x)

        if pmid:
            rec.update(pubmed_fetch(pmid))

        # ===== PMC OA =====
        if rec.get("PMCID"):
            rec["OA"] = "Yes"
            rec["PDF"] = make_btn(
                f"https://www.ncbi.nlm.nih.gov/pmc/articles/{rec['PMCID']}/pdf/",
                "📄 PMC PDF",
                "#7c3aed"
            )
            rec["Status"] = "PMC Open Access"

        # ===== UNPAYWALL =====
        if rec.get("DOI") and rec["OA"] == "No":
            up = unpaywall(rec["DOI"])
            if up.get("is_oa"):
                loc = up.get("best_oa_location") or {}
                pdf = loc.get("url_for_pdf") or extract_pdf(loc.get("url", ""))
                if pdf:
                    rec["OA"] = "Yes"
                    rec["PDF"] = make_btn(pdf, "📄 PDF", "#dc2626")
                    rec["Status"] = "Unpaywall OA"

        rows.append(rec)
        prog.progress((i + 1) / len(lines))
        time.sleep(0.05)

    df = pd.DataFrame(rows)
    st.success("✅ Completed")
    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
