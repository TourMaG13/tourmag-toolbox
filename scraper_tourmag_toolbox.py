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
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

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

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

def search_pexels_photos(queries, count=5, country=""):
    """Search for destination photos using Claude web search (best) → Pexels → Wikimedia."""
    photos = []
    seen = set()
    
    # ═══ METHOD 1: Claude web search for real photo URLs (most reliable) ═══
    if ANTHROPIC_API_KEY and country:
        terms_str = ", ".join(queries[:count])
        prompt = f"""Trouve {count} URLs d'images haute qualité en format paysage (landscape) pour ces lieux de {country} : {terms_str}

Cherche des photos sur Wikimedia Commons, Wikipedia, ou des sites de tourisme officiel.
Pour chaque lieu, donne UNE URL directe vers une image JPG/PNG en haute résolution (pas de pages HTML, pas de vignettes).
Privilégie les images de Wikimedia Commons (format : https://upload.wikimedia.org/...)

Réponds UNIQUEMENT en JSON (pas de backticks) :
{{"photos": ["https://url1.jpg", "https://url2.jpg", "https://url3.jpg", "https://url4.jpg", "https://url5.jpg"]}}"""
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "content-type": "application/json", "anthropic-version": "2023-06-01"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1000,
                      "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=120)
            if r.status_code == 200:
                texts = [b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text"]
                raw = "".join(texts)
                m = re.search(r'\{[\s\S]*"photos"[\s\S]*\}', raw)
                if m:
                    try:
                        found = json.loads(m.group()).get("photos", [])
                        for url in found:
                            if (url and url.startswith("http") and url not in seen
                                    and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', 'upload.wikimedia'])
                                    and not any(bad in url.lower() for bad in ['logo', 'icon', 'flag', 'thumb/2', '120px', '150px', '200px'])):
                                seen.add(url)
                                photos.append(url)
                        if photos:
                            print(f"Claude:{len(photos)}", end=" ")
                    except: pass
        except Exception as e:
            print(f"Claude photos err: {e}", end=" ")
    
    # ═══ METHOD 2: Pexels API (needs key) ═══
    if len(photos) < count and PEXELS_API_KEY:
        for q in queries[:count * 2]:
            if len(photos) >= count: break
            search_q = q if (country and country.lower() in q.lower()) else f"{country} {q}" if country else q
            try:
                r = requests.get("https://api.pexels.com/v1/search",
                    headers={"Authorization": PEXELS_API_KEY},
                    params={"query": search_q, "per_page": 3, "orientation": "landscape", "size": "large"},
                    timeout=10)
                if r.status_code == 200:
                    for p in r.json().get("photos", []):
                        url = p["src"].get("large2x") or p["src"]["large"]
                        if url not in seen:
                            seen.add(url); photos.append(url); break
            except Exception as e:
                print(f"Pexels err: {e}", end=" ")
            time.sleep(0.3)
        if len(photos) > len(seen) - len(photos):  # If Pexels added some
            print(f"Pexels:{len(photos)}", end=" ")
    
    # ═══ METHOD 3: Wikimedia Commons direct search (free, no key) ═══
    if len(photos) < count:
        for q in queries[:count * 2]:
            if len(photos) >= count: break
            search_q = q if (country and country.lower() in q.lower()) else f"{country} {q}" if country else q
            try:
                r = requests.get("https://commons.wikimedia.org/w/api.php",
                    params={"action":"query","format":"json","generator":"search",
                            "gsrsearch":f"{search_q} landscape panorama","gsrlimit":8,"gsrnamespace":6,
                            "prop":"imageinfo","iiprop":"url|size|mime","iiurlwidth":1200},
                    headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    pages = r.json().get("query", {}).get("pages", {})
                    for pid, page in sorted(pages.items(), key=lambda x: x[1].get("index", 999)):
                        info = page.get("imageinfo", [{}])[0]
                        thumb = info.get("thumburl", "")
                        mime = info.get("mime", "")
                        w, h = info.get("width", 0), info.get("height", 0)
                        if (thumb and "image/" in mime and w > 600 and w > h * 0.8
                                and thumb not in seen
                                and not any(x in thumb.lower() for x in ['.svg','logo','icon','flag','coat','emblem'])):
                            seen.add(thumb); photos.append(thumb); break
            except Exception as e:
                print(f"Wiki err: {e}", end=" ")
            time.sleep(0.3)
    
    return photos[:count]


def generate_dest_fiche(db, country, photo=""):
    """Generate a destination fiche with a single simple prompt + photos + news."""
    print(f"═══ FICHE: {country} ═══")
    
    prompt = f"""Rédige une fiche destination professionnelle complète sur "{country}" destinée aux agents de voyages français.

Réponds UNIQUEMENT en JSON valide (pas de backticks, pas de markdown) :
{{
  "summary": "Texte d'accroche de 4-5 phrases rédigées avec soin, décrivant l'attrait touristique, le positionnement et la singularité de la destination.",
  "essentials": {{
    "visa": "Une phrase complète sur les formalités d'entrée pour les Français (passeport, visa, durée de séjour).",
    "sante": "Une phrase complète sur les recommandations sanitaires : vaccins, précautions.",
    "devise": "Une phrase complète sur la monnaie locale, le taux de change et le budget quotidien moyen."
  }},
  "photoSearchTerms": [
    "{country} [monument le plus célèbre et photographié]",
    "{country} [paysage naturel grandiose et iconique]",
    "{country} [deuxième site touristique majeur]",
    "{country} [panorama ou point de vue célèbre]",
    "{country} [lieu historique ou architectural emblématique]"
  ],
  "sections": [
    {{"title": "Conseils MAE", "group": "pratique", "content": "- Niveau de vigilance : [phrase complète sur la situation sécuritaire]\\n- Zones sûres : [phrase complète sur les régions touristiques sûres]\\n- Zones à éviter : [phrase complète]\\n- Recommandations : [phrase complète]"}},
    {{"title": "Formalités", "group": "pratique", "content": "- Passeport : [2-3 phrases détaillées]\\n- Visa : [2-3 phrases]\\n- Vaccins : [2-3 phrases]\\n- Devise et paiements : [2-3 phrases]"}},
    {{"title": "Dynamisme touristique", "group": "pratique", "content": "- Fréquentation : {country} accueille environ X millions de visiteurs par an. [contexte]\\n- Croissance : Le tourisme connaît une croissance de X%. [détails]\\n- Visiteurs français : Environ X Français visitent chaque année. [profil]\\n- Haute saison : De [mois] à [mois], [détails prix et affluence].\\n- Basse saison : De [mois] à [mois], [avantages].\\n- Tendances : [3-4 phrases sur les tendances actuelles]"}},
    {{"title": "Points d'intérêt", "group": "pratique", "content": "- [Lieu 1] : [3-4 phrases descriptives comme un guide touristique passionné]\\n- [Lieu 2] : [3-4 phrases]\\n- [Lieu 3] : [3-4 phrases]\\n- [Lieu 4] : [3-4 phrases]\\n- [Lieu 5] : [3-4 phrases]"}},
    {{"title": "Tour-opérateurs", "group": "vente", "content": "- [TO 1] : [2-3 phrases sur ce TO et ses circuits]\\n- [TO 2] : [2-3 phrases]\\n- [TO 3] : [2-3 phrases]"}},
    {{"title": "Conseils de vente", "group": "vente", "content": "- Cibles clients : [2-3 phrases sur les profils de clientèle]\\n- Budget moyen : [phrase avec fourchette de prix]\\n- Durée idéale : [phrase argumentée]\\n- Meilleure période de réservation : [phrase]\\n- Arguments clés : [3-4 phrases percutantes]\\n- Extensions possibles : [2-3 phrases sur les combinés]"}}
  ]
}}

REGLES :
1. photoSearchTerms = NOMS DE LIEUX CELEBRES ET PHOTOGENIQUES de {country}. Le nom du pays DOIT figurer dans CHAQUE terme.
   Exemples pour l'Allemagne : ["Allemagne Porte de Brandebourg", "Allemagne Château Neuschwanstein", "Allemagne Cathédrale Cologne", "Allemagne vallée du Rhin", "Allemagne île Rügen"]
   INTERDIT : termes génériques (food, culture, people, tradition, cuisine, gastronomie, avion, plage générique)
2. Texte fluide et professionnel, PAS de style télégraphique.
   INTERDIT : "Passeport valide 6 mois. Visa non requis. CNI suffisante."
   ATTENDU : "Les ressortissants français peuvent se rendre en Allemagne munis d'une simple carte d'identité en cours de validité. Aucun visa n'est nécessaire dans le cadre de l'espace Schengen."
3. Chiffres réels dans Dynamisme touristique."""

    print("  Generating...", end=" ", flush=True)
    text = call_haiku(prompt, max_tokens=4000)
    if not text:
        print("FAIL")
        return None
    try:
        fiche_data = json.loads(re.sub(r'```json|```', '', text).strip())
    except Exception as e:
        print(f"JSON err: {e}")
        # Try to salvage partial JSON
        try:
            partial = text.strip()
            if not partial.endswith('}'):
                partial = partial[:partial.rfind('}')+1]
            fiche_data = json.loads(re.sub(r'```json|```', '', partial).strip())
        except:
            return None
    print(f"OK ({len(fiche_data.get('sections', []))} sections)")
    
    slug = re.sub(r'[^a-z0-9]', '-', country.lower())
    mod_id = f"dest-{slug}-{int(time.time())}"
    
    # ═══ PHOTOS — Pexels or Wikimedia Commons ═══
    search_terms = fiche_data.get("photoSearchTerms", [
        f"{country} famous landmark",
        f"{country} panoramic landscape",
        f"{country} iconic monument",
        f"{country} scenic view",
        f"{country} historic site"
    ])
    # Ensure country name is in every search term
    search_terms = [t if country.lower() in t.lower() else f"{country} {t}" for t in search_terms]
    print(f"  Photos: {search_terms[:2]}...", end=" ", flush=True)
    photos = search_pexels_photos(search_terms, count=5, country=country)
    hero_photo = photos[0] if photos else ""
    if photo:
        hero_photo = photo
    print(f"{len(photos)} photos")
    
    essentials = fiche_data.get("essentials", {})
    
    # ═══ SAVE TO FIRESTORE ═══
    doc_data = {
        "title": country,
        "subtitle": "Fiche pratique destination",
        "description": fiche_data.get("summary", ""),
        "url": "", "photo": hero_photo,
        "category": "destinations",
        "categories": ["destinations"],
        "size": "large", "accent": "#D97706",
        "type": "focus", "active": True, "order": 0, "badge": "",
        "ficheData": fiche_data,
        "essentials": essentials,
        "photoSearchTerms": search_terms,
        "photos": photos,
        "destNews": [],
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "ia-haiku"
    }
    db.collection("modules").document(mod_id).set(doc_data)
    print(f"  → {mod_id}")
    
    # ═══ FETCH NEWS ═══
    print(f"  News...", end=" ", flush=True)
    try:
        _fetch_news_for_dest(db, db.collection("modules").document(mod_id), country)
    except Exception as e:
        print(f"news err: {e}")
    
    return mod_id

def _fetch_news_for_dest(db, doc_ref, country):
    """Fetch news for a destination — TourMaG RSS first, then HTML scraping, then web search."""
    articles = []
    
    # 1. TourMaG RSS by tag
    safe_tag = country.lower().replace(" ", "+").replace("'", "+")
    rss_url = f"https://www.tourmag.com/xml/syndication.rss?t={safe_tag}"
    xml = fetch_url(rss_url)
    if xml and len(xml) > 200:
        articles = parse_rss(xml, max_items=5)
        if articles:
            print(f"{len(articles)} (TourMaG RSS)", end="")
    
    # 2. TourMaG HTML scraping via tag page
    if not articles:
        tag_url = f"https://www.tourmag.com/tags/{safe_tag}/"
        articles = scrape_html_articles(tag_url, max_items=5)
        if articles:
            print(f"{len(articles)} (TourMaG HTML)", end="")
    
    # 3. Web search fallback (needs API key)
    if not articles and ANTHROPIC_API_KEY:
        print("web...", end="")
        prompt = f"""Recherche les 5 dernières actualités tourisme concernant "{country}" sur tourmag.com ou des sites francophones de tourisme pro.
Réponds UNIQUEMENT en JSON valide (pas de backticks) :
{{"articles": [{{"title": "Titre", "description": "Résumé", "url": "https://...", "date": "2025-06-01"}}]}}"""
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "content-type": "application/json", "anthropic-version": "2023-06-01"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1500,
                      "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=180)
            if r.status_code == 200:
                texts = [b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text"]
                raw = "".join(texts)
                m = re.search(r'\{[\s\S]*"articles"[\s\S]*\}', raw)
                if m:
                    try:
                        news = json.loads(m.group()).get("articles", [])[:5]
                        articles = [a for a in news if a.get("title") and a.get("url", "").startswith("http")]
                        if articles: print(f"{len(articles)} (web)", end="")
                    except: pass
        except Exception as e:
            print(f"err:{e}", end="")
    
    if not articles:
        print("aucun article trouvé", end=""); return
    
    # Enrich missing images
    for art in articles:
        if not art.get("image") and art.get("url"):
            art["image"] = get_og_image(art["url"])
            time.sleep(0.3)
    
    doc_ref.update({"destNews": articles, "destNewsUpdatedAt": datetime.now(timezone.utc).isoformat()})

def refresh_dest_news(db):
    """Refresh news for all destination fiches."""
    print("═══ REFRESH DESTINATION NEWS ═══")
    if not ANTHROPIC_API_KEY:
        print("  No API key"); return
    count = 0
    for doc in db.collection("modules").where("type", "==", "focus").stream():
        country = doc.to_dict().get("title", "")
        if not country: continue
        print(f"  [{country}]...", end=" ", flush=True)
        try:
            _fetch_news_for_dest(db, doc.reference, country)
            count += 1
        except Exception as e:
            print(f"ERR: {e}")
        time.sleep(2)
    print(f"  → {count} fiches.")

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

def enrich_dest_fiches(db):
    """Auto-detect destination fiches missing photos or news, and enrich them."""
    print("═══ ENRICHISSEMENT FICHES DESTINATIONS ═══")
    docs = list(db.collection("modules").where("type", "==", "focus").stream())
    enriched = 0
    
    for doc in docs:
        data = doc.to_dict()
        country = data.get("title", "")
        if not country:
            continue
        
        needs_photos = False
        needs_news = False
        
        # Check if photos need enrichment
        photos = data.get("photos", [])
        if not photos:
            needs_photos = True
        else:
            # Check if photos are bad (unsplash source URLs or wikimedia junk)
            bad_urls = [p for p in photos if "source.unsplash.com" in p or "upload.wikimedia" in p or not p.startswith("http")]
            if len(bad_urls) >= 3:
                needs_photos = True
        
        # Check hero photo too
        hero = data.get("photo", "")
        if not hero or "source.unsplash.com" in hero or "upload.wikimedia" in hero:
            needs_photos = True
        
        # Check if news need enrichment
        news = data.get("destNews", [])
        news_date = data.get("destNewsUpdatedAt", "")
        if not news:
            needs_news = True
        elif news_date:
            # Refresh if older than 3 days
            try:
                last = datetime.fromisoformat(news_date.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - last).days >= 3:
                    needs_news = True
            except:
                needs_news = True
        
        if not needs_photos and not needs_news:
            continue
        
        print(f"  [{country}]", end="", flush=True)
        
        # ═══ ENRICH PHOTOS ═══
        if needs_photos and PEXELS_API_KEY:
            print(" photos...", end="", flush=True)
            # Get search terms from existing data or generate from country name
            search_terms = data.get("photoSearchTerms", [])
            fd = data.get("ficheData", {})
            if not search_terms:
                search_terms = fd.get("photoSearchTerms", [])
            if not search_terms:
                search_terms = [
                    f"{country} famous landmark",
                    f"{country} panoramic landscape",
                    f"{country} iconic monument",
                    f"{country} scenic view",
                    f"{country} historic architecture"
                ]
            # Ensure country in every term
            search_terms = [t if country.lower() in t.lower() else f"{country} {t}" for t in search_terms]
            
            new_photos = search_pexels_photos(search_terms, count=5, country=country)
            if new_photos and len(new_photos) >= 3:
                update = {"photos": new_photos, "photoSearchTerms": search_terms}
                # Also update hero if needed
                if not hero or "source.unsplash.com" in hero or "upload.wikimedia" in hero:
                    update["photo"] = new_photos[0]
                doc.reference.update(update)
                print(f" {len(new_photos)} OK", end="", flush=True)
            else:
                print(" skip (not enough results)", end="", flush=True)
        elif needs_photos:
            print(" photos skip (no Pexels key)", end="", flush=True)
        
        # ═══ ENRICH NEWS ═══
        if needs_news and ANTHROPIC_API_KEY:
            print(" news...", end="", flush=True)
            try:
                _fetch_news_for_dest(db, doc.reference, country)
            except Exception as e:
                print(f" err:{e}", end="", flush=True)
        elif needs_news:
            print(" news skip (no API key)", end="", flush=True)
        
        enriched += 1
        print()
        time.sleep(1)
    
    if enriched:
        print(f"  → {enriched} fiches enrichies.")
    else:
        print(f"  → Toutes les fiches sont à jour ({len(docs)} vérifiées).")

def main():
    print(f"╔══ TourMaG Scraper v7 — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ══╗")
    db = init_firebase()
    scrape_experts(db)
    scrape_rss_rubriques(db)
    scrape_dynamic_rss(db)
    scrape_thematiques(db)
    # Enrich destination fiches (photos + news) — runs every time
    enrich_dest_fiches(db)
    # Manual fiche generation via env var
    dest = os.environ.get("GENERATE_DEST_FICHE", "")
    if dest:
        generate_dest_fiche(db, dest, os.environ.get("DEST_FICHE_PHOTO", ""))
    print("╚══ Done ══╝")

if __name__ == "__main__": main()
