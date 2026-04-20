#!/usr/bin/env python3
"""
TourMaG Toolbox — Scraper RSS + IA (v2)
Pousse directement dans la collection `modules` de Firestore.
Les champs d'affichage configurés dans l'admin ne sont jamais écrasés.
"""
import os, json, re, time, requests
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
import firebase_admin
from firebase_admin import credentials, firestore

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS", "")

EXPERT_FEEDS = [
    {"tag":"duthion","name":"Brice Duthion","role":"Expert Tourisme Urbain","rss":"https://www.tourmag.com/xml/syndication.rss?t=duthion","page":"https://www.tourmag.com/tags/duthion/"},
    {"tag":"camille-le-guilloux","name":"Camille Le Guilloux","role":"Chroniqueuse","rss":"https://www.tourmag.com/xml/syndication.rss?t=camille+le+guilloux","page":"https://www.tourmag.com/tags/camille+le+guilloux/"},
    {"tag":"eric-didier","name":"Eric Didier","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=eric+didier","page":"https://www.tourmag.com/tags/eric+didier/"},
    {"tag":"cousin","name":"Saskia Cousin","role":"Chercheuse","rss":"https://www.tourmag.com/xml/syndication.rss?t=cousin","page":"https://www.tourmag.com/tags/cousin/"},
    {"tag":"jean-pinard","name":"Jean Pinard","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=jean+pinard","page":"https://www.tourmag.com/tags/jean+pinard/"},
    {"tag":"messager","name":"Jean-Luc Messager","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=messager","page":"https://www.tourmag.com/tags/messager/"},
    {"tag":"habibou","name":"Habibou","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=habibou","page":"https://www.tourmag.com/tags/habibou/"},
    {"tag":"daniel-borja","name":"Daniel Borja","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=daniel+borja","page":"https://www.tourmag.com/tags/daniel+borja/"},
    {"tag":"delporte","name":"Yves Delporte","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=delporte","page":"https://www.tourmag.com/tags/delporte/"},
    {"tag":"gallo","name":"Adriana Gallo","role":"Experte","rss":"https://www.tourmag.com/xml/syndication.rss?t=gallo","page":"https://www.tourmag.com/tags/gallo/"},
    {"tag":"jansen","name":"Alix Jansen","role":"Journaliste","rss":"https://www.tourmag.com/xml/syndication.rss?t=jansen","page":"https://www.tourmag.com/tags/jansen/"},
    {"tag":"mazzola","name":"Jean-Pierre Mazzola","role":"Éditorialiste","rss":"https://www.tourmag.com/xml/syndication.rss?t=mazzola","page":"https://www.tourmag.com/tags/mazzola/"},
    {"tag":"pointet","name":"Pierre Pointet","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=pointet","page":"https://www.tourmag.com/tags/pointet/"},
    {"tag":"ramond","name":"Ramond","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=ramond","page":"https://www.tourmag.com/tags/ramond/"},
    {"tag":"remi-duchange","name":"Rémi Duchange","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=remi+duchange","page":"https://www.tourmag.com/tags/remi+duchange/"},
    {"tag":"rodolphe-lenoir","name":"Rodolphe Lenoir","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=rodolphe+lenoir","page":"https://www.tourmag.com/tags/rodolphe+lenoir/"},
    {"tag":"guillaume-vigneron","name":"Guillaume Vigneron","role":"Expert","rss":"https://www.tourmag.com/xml/syndication.rss?t=guillaume+vigneron","page":"https://www.tourmag.com/tags/guillaume+vigneron/"},
]
DEST_SING_RSS = "https://www.tourmag.com/xml/syndication.rss?t=destinations+singulieres"
HEADERS = {"User-Agent": "TourMaG-Toolbox-Bot/1.0"}

def init_firebase():
    cred = credentials.Certificate(json.loads(FIREBASE_CREDS)) if FIREBASE_CREDS else credentials.Certificate("firebase-creds.json")
    firebase_admin.initialize_app(cred)
    return firestore.client()

def fetch_url(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout); r.raise_for_status(); return r.text
    except Exception as e:
        print(f"  WARN fetch {url[:80]}: {e}"); return None

def get_og_image(url):
    html = fetch_url(url)
    if not html: return ""
    for pat in [r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']']:
        m = re.search(pat, html, re.IGNORECASE)
        if m: return m.group(1)
    return ""

def get_expert_photo(page_url):
    html = fetch_url(page_url)
    if not html: return ""
    for pat in [r'<img[^>]+class=["\'][^"\']*(?:author|avatar|expert|photo)[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*(?:author|avatar|expert|photo)[^"\']*["\']',r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']']:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            img = m.group(1)
            if not any(x in img.lower() for x in ["logo","icon","favicon"]): return img
    return ""

def parse_rss(xml_text, max_items=5):
    if not xml_text: return []
    try:
        root = ET.fromstring(xml_text); items = root.findall(".//item"); results = []
        for item in items[:max_items]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc_raw = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            image = ""
            enc = item.find("enclosure")
            if enc is not None: image = enc.get("url", "")
            if not image:
                m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_raw, re.IGNORECASE)
                if m: image = m.group(1)
            desc_clean = re.sub(r'<[^>]+>', '', desc_raw).strip()[:300]
            results.append({"title":title,"url":link,"description":desc_clean,"image":image,"date":pub_date})
        return results
    except ET.ParseError as e:
        print(f"  WARN parse RSS: {e}"); return []

# ══════════ EXPERTS → modules/ ══════════
def scrape_experts(db):
    print("═══ EXPERTS → modules ═══")
    for i, expert in enumerate(EXPERT_FEEDS):
        tag = expert["tag"]; doc_id = f"rss-expert-{tag}"
        print(f"  [{tag}] {expert['name']}...", end=" ", flush=True)
        xml = fetch_url(expert["rss"])
        articles = parse_rss(xml, max_items=5)
        for art in articles:
            if not art["image"] and art["url"]: art["image"] = get_og_image(art["url"]); time.sleep(0.3)
        photo = get_expert_photo(expert["page"]); time.sleep(0.3)
        ref = db.collection("modules").document(doc_id)
        existing = ref.get()
        rss_data = {"articles":articles,"expertPhoto":photo,"rssUpdatedAt":datetime.now(timezone.utc).isoformat(),"source":"rss-auto"}
        if existing.exists:
            ref.update(rss_data)
        else:
            ref.set({"title":expert["name"],"subtitle":expert["role"],"description":"","url":expert["page"],"photo":"","expertName":expert["name"],"expertRole":expert["role"],"expertTag":tag,"expertPage":expert["page"],"type":"expert","category":"experts","categories":["experts"],"size":"medium","accent":"#0891B2","active":True,"order":100+i,"badge":"","noBorder":False,"maxArticles":3,"articleImgSize":72,"showArticleImg":True,"featuredArticleTitle":"","featuredArticleUrl":"","featuredArticleImg":"","featuredArticleDesc":"",**rss_data})
        print(f"{len(articles)} articles, photo={'Y' if photo else 'N'}")
    print(f"  → {len(EXPERT_FEEDS)} experts traités.")

# ══════════ DESTINATIONS SINGULIÈRES → modules/ ══════════
def scrape_dest_singulieres(db):
    print("═══ DESTINATIONS SINGULIÈRES → modules ═══")
    xml = fetch_url(DEST_SING_RSS); articles = parse_rss(xml, max_items=12)
    for art in articles:
        if not art["image"] and art["url"]: art["image"] = get_og_image(art["url"]); time.sleep(0.3)
    print(f"  {len(articles)} articles")
    for i, art in enumerate(articles):
        doc_id = f"rss-destsing-{i}"; ref = db.collection("modules").document(doc_id); existing = ref.get()
        rss_data = {"rssTitle":art["title"],"rssDescription":art["description"],"rssImage":art["image"],"rssUrl":art["url"],"rssDate":art["date"],"rssUpdatedAt":datetime.now(timezone.utc).isoformat(),"source":"rss-auto"}
        if existing.exists:
            ref.update(rss_data)
        else:
            ref.set({"title":art["title"],"subtitle":"Destination singulière","description":art["description"],"url":art["url"],"photo":art["image"],"type":"rss-destsing","category":"destinations","categories":["destinations"],"size":"medium","accent":"#EC4899","active":True,"order":200+i,"badge":"","noBorder":False,"rssIndex":i,**rss_data})
        print(f"  [{doc_id}] {art['title'][:50]}... img={'Y' if art['image'] else 'N'}")
    for j in range(len(articles), 50):
        ref = db.collection("modules").document(f"rss-destsing-{j}")
        if ref.get().exists: ref.delete(); print(f"  [del] rss-destsing-{j}")
        else: break
    print(f"  → {len(articles)} destinations traitées.")

# ══════════ CLAUDE HAIKU ══════════
def call_haiku(prompt, system="", max_tokens=1500, retries=3):
    if not ANTHROPIC_API_KEY: print("  WARN: pas de clé API"); return None
    for attempt in range(retries):
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":ANTHROPIC_API_KEY,"content-type":"application/json","anthropic-version":"2023-06-01"},json={"model":"claude-haiku-4-5-20251001","max_tokens":max_tokens,"system":system or "Tu es un expert tourisme. Réponds uniquement en JSON valide, sans backticks ni markdown. Français.","messages":[{"role":"user","content":prompt}]},timeout=90)
            if r.status_code==429: time.sleep(int(r.headers.get("retry-after","30"))); continue
            if r.status_code==529: time.sleep(30); continue
            r.raise_for_status(); data=r.json(); return "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
        except Exception as e: print(f"  ERR ({attempt+1}): {e}"); time.sleep(10) if attempt<retries-1 else None
    return None

def generate_dest_fiche(db, country, photo=""):
    print(f"═══ FICHE: {country} ═══")
    prompt = f'Génère une fiche destination pro pour "{country}" pour agents de voyages français.\nJSON: {{"summary":"...","sections":[{{"title":"Conseils MAE","content":"..."}},{{"title":"Formalités","content":"..."}},{{"title":"Dynamisme touristique","content":"..."}},{{"title":"Points d\'intérêt","content":"..."}},{{"title":"Tour-opérateurs","content":"..."}},{{"title":"Conseils de vente","content":"..."}}]}}'
    text = call_haiku(prompt)
    if not text: return None
    try: fiche_data = json.loads(re.sub(r'```json|```','',text).strip())
    except: print(f"  JSON err"); return None
    slug = re.sub(r'[^a-z0-9]','-',country.lower()); mod_id = f"dest-{slug}-{int(time.time())}"
    if not photo: photo = f"https://source.unsplash.com/800x400/?{requests.utils.quote(country)},travel"
    db.collection("modules").document(mod_id).set({"title":country,"subtitle":"Focus destination de la semaine","description":fiche_data.get("summary",""),"url":"","photo":photo,"category":"destinations","categories":["destinations","dashboard"],"size":"large","accent":"#D97706","type":"focus","active":True,"order":0,"badge":"","ficheData":fiche_data,"generatedAt":datetime.now(timezone.utc).isoformat(),"source":"ia-haiku"})
    print(f"  → {mod_id}"); return mod_id

def main():
    print(f"╔══ TourMaG Toolbox Scraper v2 — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ══╗")
    db = init_firebase()
    scrape_experts(db)
    scrape_dest_singulieres(db)
    dest = os.environ.get("GENERATE_DEST_FICHE","")
    if dest: generate_dest_fiche(db, dest, os.environ.get("DEST_FICHE_PHOTO",""))
    print("╚══ Terminé ══╝")

if __name__ == "__main__": main()
