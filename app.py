import streamlit as st
import requests
import pandas as pd
from pathlib import Path
import zipfile
import re
import time
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

# ================= CONFIG ================= #

UNPAYWALL_EMAIL = "your_email@institute.edu"   # REQUIRED
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/pdf,text/html"
}

# ================= UI ================= #

st.set_page_config("Literature OA Downloader", layout="wide")
st.title("📚 Reference / DOI → Open Access PDF Downloader")
st.caption("Europe PMC • PMC • Crossref • Unpaywall | 100% Legal Open Access")

input_text = st.text_area(
    "Paste DOI / PMID / PMCID / Reference (one per line)",
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
       font-size:13px;
       ">
       {label}
    </a>
    """

# ================= EUROPE PMC ================= #

def europe_pmc(query):
    r = requests.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": query, "format": "json", "pageSize": 1},
        timeout=20
    )
    hits = r.json().get("resultList", {}).get("result", [])
    if not hits:
        return {}
    h = hits[0]
    return {
        "Title": h.get("title",""),
        "Journal": h.get("journalTitle",""),
        "Year": h.get("pubYear",""),
        "Authors": h.get("authorString",""),
        "DOI": h.get("doi",""),
        "PMID": h.get("pmid",""),
        "PMCID": h.get("pmcid","")
    }

# ================= ID CROSSWALK ================= #

def id_crosswalk(val):
    r = requests.get(
        "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
        params={"ids": val, "format": "json"},
        timeout=15
    )
    recs = r.json().get("records", [])
    if not recs:
        return {}
    r0 = recs[0]
    return {
        "PMID": r0.get("pmid",""),
        "PMCID": r0.get("pmcid",""),
        "DOI": r0.get("doi","")
    }

# ================= CROSSREF ================= #

def crossref(doi):
    r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=15)
    if r.status_code != 200:
        return {}
    m = r.json()["message"]
    return {
        "Title": m.get("title",[""])[0],
        "Journal": m.get("container-title",[""])[0],
        "Year": str(m.get("issued",{}).get("date-parts",[[None]])[0][0]),
        "Authors": ", ".join(
            f"{a.get('family','')} {a.get('given','')}"
            for a in m.get("author",[])
        )
    }

# ================= UNPAYWALL ================= #

def unpaywall(doi):
    r = requests.get(
        f"https://api.unpaywall.org/v2/{doi}",
        params={"email": UNPAYWALL_EMAIL},
        timeout=15
    )
    return r.json() if r.status_code == 200 else {}

def extract_pdf(page):
    if not page:
        return None
    r = requests.get(page, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "lxml")
    m = soup.find("meta", attrs={"name": "citation_pdf_url"})
    if m:
        return m["content"]
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            return urljoin(page, a["href"])
    return None

def download_pdf(url, fname):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200 and "pdf" in r.headers.get("Content-Type",""):
        (DOWNLOAD_DIR / fname).write_bytes(r.content)
        return "Downloaded"
    return "Failed"

# ================= RIS ================= #

def make_ris(df):
    out = []
    for _, r in df.iterrows():
        out += [
            "TY  - JOUR",
            f"TI  - {r['Title']}",
            f"JO  - {r['Journal']}",
            f"PY  - {r['Year']}",
        ]
        for a in r["Authors"].split(","):
            if a.strip():
                out.append(f"AU  - {a.strip()}")
        if r["DOI"]: out.append(f"DO  - {r['DOI']}")
        if r["PMID"]: out.append(f"PM  - {r['PMID']}")
        out += ["ER  -", ""]
    return "\n".join(out)

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
            "Scholar": make_btn(
                f"https://scholar.google.com/scholar?q={quote(x)}",
                "🎓 Scholar",
                "#1a73e8"
            ),
            "PubMed": make_btn(
                f"https://pubmed.ncbi.nlm.nih.gov/?term={quote(x)}",
                "🧬 PubMed",
                "#059669"
            ),
            "PMC": make_btn(
                f"https://www.ncbi.nlm.nih.gov/pmc/?term={quote(x)}",
                "📖 PMC",
                "#7c3aed"
            ),
        }

        rec.update({k:v for k,v in europe_pmc(x).items() if v})

        for k in ["DOI","PMID","PMCID"]:
            if rec.get(k):
                rec.update({a:b for a,b in id_crosswalk(rec[k]).items() if b})

        if rec.get("DOI") and not rec["Title"]:
            rec.update(crossref(rec["DOI"]))

        if rec.get("DOI"):
            up = unpaywall(rec["DOI"])
            if up.get("is_oa"):
                loc = up.get("best_oa_location") or {}
                pdf = loc.get("url_for_pdf") or extract_pdf(loc.get("url",""))
                if pdf:
                    rec["OA"] = "Yes"
                    rec["PDF"] = make_btn(pdf, "📄 PDF", "#dc2626")
                    rec["Status"] = download_pdf(
                        pdf,
                        rec["DOI"].replace("/","_") + ".pdf"
                    )

        rows.append(rec)
        prog.progress((i+1)/len(lines))
        time.sleep(0.2)

    df = pd.DataFrame(rows)

    st.success("✅ Completed")

    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

    # ================= EXPORT ================= #

    csv_path = Path("results.csv")
    ris_path = Path("references.ris")

    df.to_csv(csv_path, index=False)
    ris_path.write_text(make_ris(df), encoding="utf-8")

    final_zip = Path("literature_results.zip")

    with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(csv_path, "results.csv")
        z.write(ris_path, "references.ris")
        for pdf in DOWNLOAD_DIR.glob("*.pdf"):
            z.write(pdf, f"oa_pdfs/{pdf.name}")

    with open(final_zip, "rb") as f:
        st.download_button(
            "📦 Download ALL (CSV + RIS + PDFs)",
            f,
            file_name="literature_results.zip",
            mime="application/zip"
        )
