#!/usr/bin/env python3
"""
TourMaG Toolbox — Scraper RSS + IA (v5)
- Experts: un module par expert dans `modules/` (type=expert)
- Destinations singulières: UN SEUL module rubrique dans `modules/` (type=rubrique, rssSource défini)
- Thématiques abonné: articles scrapés dans `thematiques/{id}` pour personnalisation dashboard
- Ne touche jamais aux champs d'affichage configurés dans l'admin
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

RSS_RUBRIQUES = [
    {
        "id": "rss-rubrique-dest-singulieres",
        "rss": "https://www.tourmag.com/xml/syndication.rss?t=destinations+singulieres",
        "title": "Destinations Singulières",
        "subtitle": "Destination singulière",
        "category": "destinations",
        "categories": ["destinations"],
        "accent": "#EC4899",
        "max_items": 10,
        "url": "https://www.tourmag.com/tags/destinations+singulieres/",
    },
]

# ══════════ THÉMATIQUES ABONNÉ ══════════
# RSS via proxy Vercel (prioritaire) + fallback HTML scraping
THEMATIC_FEEDS = [
    {
        "id": "thema-aerien",
        "title": "Aérien",
        "icon": "✈️",
        "accent": "#0EA5E9",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/airmag",
        "html_url": "https://www.tourmag.com/airmag/",
        "max_items": 5,
    },
    {
        "id": "thema-croisieres",
        "title": "Croisières",
        "icon": "🚢",
        "accent": "#0891B2",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/cruisemag",
        "html_url": "https://www.tourmag.com/cruisemag/",
        "max_items": 5,
    },
    {
        "id": "thema-destinations",
        "title": "Destinations",
        "icon": "🌍",
        "accent": "#059669",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/dmcmag",
        "html_url": "https://www.tourmag.com/dmcmag/",
        "max_items": 5,
    },
    {
        "id": "thema-tech",
        "title": "Tech",
        "icon": "💻",
        "accent": "#7C3AED",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/la-travel-tech",
        "html_url": "https://www.tourmag.com/latraveltech/",
        "max_items": 5,
    },
    {
        "id": "thema-luxe",
        "title": "Luxe",
        "icon": "💎",
        "accent": "#D97706",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/luxury-travelmag",
        "html_url": "https://www.tourmag.com/luxurytravelmag/",
        "max_items": 5,
    },
    {
        "id": "thema-france",
        "title": "Partez en France",
        "icon": "🇫🇷",
        "accent": "#1D4ED8",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/partez-en-france",
        "html_url": "https://www.tourmag.com/partez-en-france/",
        "max_items": 5,
    },
    {
        "id": "thema-responsable",
        "title": "Voyages responsables",
        "icon": "🌱",
        "accent": "#15803D",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/voyages-responsables",
        "html_url": "https://www.tourmag.com/voyages-responsables/",
        "max_items": 5,
    },
    {
        "id": "thema-voyageurs",
        "title": "Voyageurs Mag",
        "icon": "🧳",
        "accent": "#9333EA",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/voyageursmag",
        "html_url": "https://www.tourmag.com/voyageursmag/",
        "max_items": 5,
    },
    {
        "id": "thema-tmc",
        "title": "TMC",
        "icon": "💼",
        "accent": "#475569",
        "rss": "https://tourmag-rss-flux-psi.vercel.app/rss/travel-managermag",
        "html_url": "https://www.tourmag.com/travel-managermag/",
        "max_items": 5,
    },
]

HEADERS = {"User-Agent": "TourMaG-Toolbox-Bot/1.0"}

def init_firebase():
    cred = credentials.Certificate(json.loads(FIREBASE_CREDS)) if FIREBASE_CREDS else credentials.Certificate("firebase-creds.json")
    firebase_admin.initialize_app(cred)
    return firestore.client()

def fetch_url(url, timeout=20):
    try: r = requests.get(url, headers=HEADERS, timeout=timeout); r.raise_for_status(); return r.text
    except Exception as e: print(f"  WARN {url[:60]}: {e}"); return None

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
    for pat in [r'<img[^>]+class=["\'][^"\']*(?:author|avatar|expert|photo)[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*(?:author|avatar|expert|photo)[^"\']*["\']',r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']']:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            img = m.group(1)
            if not any(x in img.lower() for x in ["logo","icon","favicon"]): return img
    return ""

def parse_rss(xml_text, max_items=5):
    if not xml_text: return []
    try:
        root = ET.fromstring(xml_text); results = []
        for item in root.findall(".//item")[:max_items]:
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
    except ET.ParseError as e: print(f"  WARN RSS: {e}"); return []

# ══════════ EXPERTS → modules/ (one module per expert) ══════════
def scrape_experts(db):
    print("═══ EXPERTS ═══")
    for i, expert in enumerate(EXPERT_FEEDS):
        tag = expert["tag"]; doc_id = f"rss-expert-{tag}"
        print(f"  [{tag}] {expert['name']}...", end=" ", flush=True)
        xml = fetch_url(expert["rss"])
        articles = parse_rss(xml, max_items=5)
        for art in articles:
            if not art["image"] and art["url"]: art["image"] = get_og_image(art["url"]); time.sleep(0.3)
        photo = get_expert_photo(expert["page"]); time.sleep(0.3)
        ref = db.collection("modules").document(doc_id)
        rss_data = {"articles":articles,"expertPhoto":photo,"rssUpdatedAt":datetime.now(timezone.utc).isoformat(),"source":"rss-auto"}
        if ref.get().exists:
            ref.update(rss_data)
        else:
            ref.set({"title":expert["name"],"subtitle":expert["role"],"description":"","url":expert["page"],"photo":"","expertName":expert["name"],"expertRole":expert["role"],"expertTag":tag,"expertPage":expert["page"],"type":"expert","category":"experts","categories":["experts"],"size":"medium","accent":"#0891B2","active":True,"order":100+i,"badge":"","noBorder":False,"maxArticles":3,"articleImgSize":72,"showArticleImg":True,"featuredArticleTitle":"","featuredArticleUrl":"","featuredArticleImg":"","featuredArticleDesc":"","featuredImgHeight":"","expertStyle":"classic",**rss_data})
        print(f"{len(articles)} art, photo={'Y' if photo else 'N'}")
    print(f"  → {len(EXPERT_FEEDS)} experts.")

# ══════════ RSS RUBRIQUES → modules/ (ONE module per rubrique) ══════════
def scrape_rss_rubriques(db):
    print("═══ RSS RUBRIQUES (prédéfinies) ═══")
    for rub in RSS_RUBRIQUES:
        doc_id = rub["id"]
        print(f"  [{doc_id}] {rub['title']}...", end=" ", flush=True)
        xml = fetch_url(rub["rss"])
        articles = parse_rss(xml, max_items=rub.get("max_items", 10))
        for art in articles:
            if not art["image"] and art["url"]: art["image"] = get_og_image(art["url"]); time.sleep(0.3)
        ref = db.collection("modules").document(doc_id)
        rss_data = {"articles":articles,"rssUpdatedAt":datetime.now(timezone.utc).isoformat(),"source":"rss-auto"}
        if ref.get().exists:
            ref.update(rss_data)
        else:
            ref.set({
                "title": rub["title"],
                "subtitle": rub.get("subtitle", ""),
                "description": "",
                "url": rub.get("url", ""),
                "photo": "",
                "type": "rubrique",
                "category": rub["category"],
                "categories": rub["categories"],
                "size": "large",
                "accent": rub.get("accent", "#0891B2"),
                "active": True,
                "order": 50,
                "badge": "",
                "noBorder": False,
                "rssSource": rub["rss"],
                "rubriqueStyle": "grid",
                **rss_data,
            })
        print(f"{len(articles)} articles")
    print(f"  → {len(RSS_RUBRIQUES)} rubriques prédéfinies.")

def scrape_dynamic_rss(db):
    """Scanne tous les modules de type rubrique avec rssSource et met à jour leurs articles."""
    print("═══ RSS DYNAMIQUES (rssSource dans modules) ═══")
    count = 0
    # Trouver tous les modules rubrique qui ont un rssSource
    docs = db.collection("modules").where("type", "==", "rubrique").stream()
    for doc in docs:
        data = doc.to_dict()
        rss_url = data.get("rssSource", "")
        doc_id = doc.id
        # Skip les rubriques prédéfinies (déjà traitées) et celles sans rssSource
        if not rss_url or doc_id in [r["id"] for r in RSS_RUBRIQUES]:
            continue
        title = data.get("title", doc_id)
        print(f"  [{doc_id}] {title}...", end=" ", flush=True)
        xml = fetch_url(rss_url)
        articles = parse_rss(xml, max_items=10)
        for art in articles:
            if not art["image"] and art["url"]: art["image"] = get_og_image(art["url"]); time.sleep(0.3)
        doc.reference.update({
            "articles": articles,
            "rssUpdatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "rss-auto",
        })
        count += 1
        print(f"{len(articles)} articles")
    print(f"  → {count} rubriques dynamiques.")

# ══════════ CLAUDE HAIKU ══════════
def call_haiku(prompt, system="", max_tokens=1500, retries=3):
    if not ANTHROPIC_API_KEY: print("  WARN: no API key"); return None
    for attempt in range(retries):
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":ANTHROPIC_API_KEY,"content-type":"application/json","anthropic-version":"2023-06-01"},json={"model":"claude-haiku-4-5-20251001","max_tokens":max_tokens,"system":system or "Tu es un expert tourisme. JSON valide uniquement, sans backticks. Français.","messages":[{"role":"user","content":prompt}]},timeout=90)
            if r.status_code in (429,529): time.sleep(int(r.headers.get("retry-after","30"))); continue
            r.raise_for_status(); return "".join(b.get("text","") for b in r.json().get("content",[]) if b.get("type")=="text")
        except Exception as e: print(f"  ERR ({attempt+1}): {e}"); time.sleep(10) if attempt<retries-1 else None
    return None

def generate_dest_fiche(db, country, photo=""):
    print(f"═══ FICHE: {country} ═══")
    prompt = f"""Fiche destination pro "{country}" pour agents de voyages français. JSON valide uniquement :
{{
  "summary": "Résumé 2-3 phrases",
  "photoKeywords": ["5 mots-clés photo pour unsplash"],
  "essentials": {{
    "visa": "Résumé court visa/passeport",
    "sante": "Résumé court santé/vaccins",
    "devise": "Résumé court devise/budget"
  }},
  "sections": [
    {{"title": "Conseils MAE", "group": "pratique", "content": "- Point 1\\n- Point 2\\n- Point 3"}},
    {{"title": "Formalités", "group": "pratique", "content": "- Passeport : détail\\n- Visa : détail\\n- Vaccins : détail"}},
    {{"title": "Dynamisme touristique", "group": "pratique", "content": "- Fréquentation\\n- Tendances\\n- Saisonnalité"}},
    {{"title": "Points d'intérêt", "group": "pratique", "content": "- Lieu 1 : description\\n- Lieu 2 : description"}},
    {{"title": "Tour-opérateurs", "group": "vente", "content": "- TO 1 : spécialité\\n- TO 2 : spécialité"}},
    {{"title": "Conseils de vente", "group": "vente", "content": "- Argument 1\\n- Cible\\n- Panier moyen"}}
  ]
}}
IMPORTANT: Utilise des retours à la ligne (\\n) et tirets (-) pour séparer chaque point."""
    text = call_haiku(prompt)
    if not text: return None
    try: fiche_data = json.loads(re.sub(r'```json|```','',text).strip())
    except: print("  JSON err"); return None
    slug = re.sub(r'[^a-z0-9]','-',country.lower()); mod_id = f"dest-{slug}-{int(time.time())}"
    if not photo: photo = f"https://source.unsplash.com/800x400/?{requests.utils.quote(country)},travel"
    # Build photo URLs from keywords
    keywords = fiche_data.get("photoKeywords", [f"{country} travel", f"{country} landmark", f"{country} nature", f"{country} culture", f"{country} food"])
    photos = []
    for kw in keywords[:5]:
        img = get_og_image(f"https://source.unsplash.com/600x400/?{requests.utils.quote(kw)}")
        photos.append(img if img else f"https://source.unsplash.com/600x400/?{requests.utils.quote(kw)}")
        time.sleep(0.3)
    essentials = fiche_data.get("essentials", {})
    db.collection("modules").document(mod_id).set({
        "title": country,
        "subtitle": "Focus destination de la semaine",
        "description": fiche_data.get("summary", ""),
        "url": "", "photo": photo,
        "category": "destinations",
        "categories": ["destinations", "dashboard"],
        "size": "large", "accent": "#D97706",
        "type": "focus", "active": True, "order": 0, "badge": "",
        "ficheData": fiche_data,
        "essentials": essentials,
        "photoKeywords": keywords,
        "photos": photos,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "ia-haiku"
    })
    print(f"  → {mod_id} ({len(photos)} photos)"); return mod_id

# ══════════ HTML FALLBACK SCRAPER (BeautifulSoup) ══════════
def scrape_html_articles(url, max_items=5):
    """Scrape articles from a TourMaG rubrique page as fallback when RSS fails."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("  WARN: bs4 not installed, skipping HTML fallback")
        return []
    html = fetch_url(url)
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        # TourMaG uses various article containers — try several selectors
        articles = (
            soup.select('article') or
            soup.select('.post-item') or
            soup.select('.article-item') or
            soup.select('.card-article') or
            soup.select('[class*="article"]') or
            soup.select('a[href*="tourmag.com"]')
        )
        for art in articles[:max_items * 2]:  # Get more candidates to filter
            # Extract link
            link_el = art if art.name == 'a' else art.find('a', href=True)
            if not link_el or not link_el.get('href'):
                continue
            link = link_el['href']
            if not link.startswith('http'):
                link = 'https://www.tourmag.com' + link
            # Skip non-article links
            if '/tags/' in link or '#' == link or len(link) < 30:
                continue
            # Extract title
            title_el = art.find(['h1', 'h2', 'h3', 'h4'])
            title = title_el.get_text(strip=True) if title_el else (link_el.get_text(strip=True) if link_el else '')
            if not title or len(title) < 10:
                continue
            # Extract image
            img_el = art.find('img')
            image = ''
            if img_el:
                image = img_el.get('src') or img_el.get('data-src') or img_el.get('data-lazy-src') or ''
                if image and not image.startswith('http'):
                    image = 'https://www.tourmag.com' + image
            # Extract description
            desc_el = art.find('p') or art.find('[class*="desc"]') or art.find('[class*="excerpt"]')
            desc = desc_el.get_text(strip=True)[:300] if desc_el else ''
            # Extract date
            date_el = art.find('time') or art.find('[class*="date"]')
            date_str = ''
            if date_el:
                date_str = date_el.get('datetime') or date_el.get_text(strip=True)
            results.append({
                "title": title,
                "url": link,
                "description": desc,
                "image": image,
                "date": date_str,
            })
            if len(results) >= max_items:
                break
        # Deduplicate by URL
        seen = set()
        deduped = []
        for r in results:
            if r['url'] not in seen:
                seen.add(r['url'])
                deduped.append(r)
        return deduped[:max_items]
    except Exception as e:
        print(f"  WARN HTML scrape {url[:50]}: {e}")
        return []

# ══════════ THEMATIQUES ABONNÉ → thematiques/{id} ══════════
def scrape_thematiques(db):
    """Scrape les 5 thématiques pour les abonnés. RSS prioritaire, fallback HTML."""
    print("═══ THÉMATIQUES ABONNÉ ═══")
    # Also write the catalog to config/thematiques for the dashboard to read
    catalog = []
    for thema in THEMATIC_FEEDS:
        doc_id = thema["id"]
        print(f"  [{doc_id}] {thema['title']}...", end=" ", flush=True)
        # 1. Try RSS first
        articles = []
        xml = fetch_url(thema["rss"])
        if xml and len(xml) > 100:
            articles = parse_rss(xml, max_items=thema["max_items"])
            print(f"RSS={len(articles)}", end=" ", flush=True)
        # 2. Fallback to HTML scraping if RSS failed or returned nothing
        if not articles:
            print("RSS fail, trying HTML...", end=" ", flush=True)
            articles = scrape_html_articles(thema["html_url"], max_items=thema["max_items"])
            print(f"HTML={len(articles)}", end=" ", flush=True)
        # 3. Enrich missing images via og:image
        for art in articles:
            if not art["image"] and art["url"]:
                art["image"] = get_og_image(art["url"])
                time.sleep(0.3)
        # 4. Write to Firestore thematiques collection
        db.collection("thematiques").document(doc_id).set({
            "id": doc_id,
            "title": thema["title"],
            "icon": thema["icon"],
            "accent": thema["accent"],
            "articles": articles,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "rss" if xml and len(xml) > 100 else "html-scrape",
        })
        catalog.append({
            "id": doc_id,
            "title": thema["title"],
            "icon": thema["icon"],
            "accent": thema["accent"],
            "articleCount": len(articles),
        })
        print(f"→ {len(articles)} articles")
    # Write catalog for dashboard to enumerate available thematiques
    db.collection("config").document("thematiques").set({
        "catalog": catalog,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })
    print(f"  → {len(THEMATIC_FEEDS)} thématiques, catalogue mis à jour.")

def main():
    print(f"╔══ TourMaG Scraper v5 — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ══╗")
    db = init_firebase()
    scrape_experts(db)
    scrape_rss_rubriques(db)
    scrape_dynamic_rss(db)
    scrape_thematiques(db)
    dest = os.environ.get("GENERATE_DEST_FICHE","")
    if dest: generate_dest_fiche(db, dest, os.environ.get("DEST_FICHE_PHOTO",""))
    print("╚══ Done ══╝")

if __name__ == "__main__": main()
