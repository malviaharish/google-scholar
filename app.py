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
st.title("📚 Reference / DOI → OA PDF Downloader")
st.caption("Europe PMC + Unpaywall + PMC + Crossref | 100% Legal OA")

input_text = st.text_area(
    "Paste DOI / PMID / PMCID / Reference (one per line)",
    height=220
)

# ================= HELPERS ================= #

def is_doi(x): return bool(re.search(r"10\.\d{4,9}/", x))
def is_pmid(x): return x.isdigit() and len(x) <= 8
def is_pmcid(x): return x.upper().startswith("PMC")

def clean_doi(x):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", x.strip())

def ncbi_get(url, params):
    r = requests.get(url, params=params, timeout=20)
    time.sleep(0.34)
    r.raise_for_status()
    return r

def make_btn(url, label):
    return f"""<a href="{url}" target="_blank"
    style="background:#2563eb;color:white;padding:5px 10px;
    border-radius:6px;text-decoration:none;font-weight:600;">{label}</a>""" if url else ""

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
        "Journal_Details": f"{h.get('journalTitle','')} | {h.get('pubYear','')}",
        "Year": h.get("pubYear",""),
        "Authors": h.get("authorString",""),
        "Abstract": h.get("abstractText",""),
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
        "Journal_Details": f"{m.get('container-title',[''])[0]} | {m.get('issued',{}).get('date-parts',[[None]])[0][0]}",
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
    r = requests.get(page, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, "lxml")
    m = soup.find("meta", attrs={"name":"citation_pdf_url"})
    if m: return m["content"]
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            return urljoin(page, a["href"])
    return None

def download_pdf(url, fname):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 200 and "pdf" in r.headers.get("Content-Type",""):
        (DOWNLOAD_DIR/fname).write_bytes(r.content)
        return "Downloaded"
    return "Failed"

# ================= RIS ================= #

def make_ris(df):
    out=[]
    for _,r in df.iterrows():
        out += [
            "TY  - JOUR",
            f"TI  - {r['Title']}" if r["Title"] else "",
            f"JO  - {r['Journal_Details']}" if r["Journal_Details"] else "",
            f"PY  - {r['Year']}" if r["Year"] else "",
        ]
        for a in r["Authors"].split(","):
            out.append(f"AU  - {a.strip()}")
        if r["DOI"]: out.append(f"DO  - {r['DOI']}")
        if r["PMID"]: out.append(f"PM  - {r['PMID']}")
        out += ["ER  -",""]
    return "\n".join(out)

# ================= MAIN ================= #

if st.button("🔍 Process"):

    rows=[]
    lines=[l.strip() for l in input_text.splitlines() if l.strip()]
    prog=st.progress(0)

    for i,x in enumerate(lines):
        rec={
            "Input":x,"Title":"","Journal_Details":"","Year":"",
            "Authors":"","DOI":"","PMID":"","PMCID":"",
            "OA":"No","PDF":"","Status":"",
            "Scholar":make_btn(f"https://scholar.google.com/scholar?q={quote(x)}","Scholar"),
            "PubMed":make_btn(f"https://pubmed.ncbi.nlm.nih.gov/?term={quote(x)}","PubMed"),
            "PMC":make_btn(f"https://www.ncbi.nlm.nih.gov/pmc/?term={quote(x)}","PMC")
        }

        rec.update({k:v for k,v in europe_pmc(x).items() if v})
        for k in ["DOI","PMID","PMCID"]:
            if rec.get(k):
                rec.update({a:b for a,b in id_crosswalk(rec[k]).items() if b})

        if rec.get("DOI") and not rec["Title"]:
            rec.update(crossref(rec["DOI"]))

        if rec.get("DOI"):
            up=unpaywall(rec["DOI"])
            if up.get("is_oa"):
                loc=up.get("best_oa_location") or {}
                pdf=loc.get("url_for_pdf") or extract_pdf(loc.get("url",""))
                if pdf:
                    rec["OA"]="Yes"
                    rec["PDF"]=make_btn(pdf,"PDF")
                    rec["Status"]=download_pdf(pdf,rec["DOI"].replace("/","_")+".pdf")

        rows.append(rec)
        prog.progress((i+1)/len(lines))

    df=pd.DataFrame(rows)

    st.success("✅ Completed")

    st.markdown(df.to_html(escape=False,index=False),unsafe_allow_html=True)

    st.download_button("⬇️ CSV",df.to_csv(index=False),"results.csv","text/csv")
    st.download_button("⬇️ RIS",make_ris(df),"references.ris","application/x-research-info-systems")

    zip_path=Path("oa_pdfs.zip")
    with zipfile.ZipFile(zip_path,"w") as z:
        for f in DOWNLOAD_DIR.glob("*.pdf"):
            z.write(f,f.name)

    with open(zip_path,"rb") as f:
        st.download_button("📦 PDFs ZIP",f,"oa_pdfs.zip","application/zip")
