#!/usr/bin/env python3
"""
TourMaG Toolbox — Scraper RSS + IA
Tourne via GitHub Actions (cron toutes les 6h par défaut).
Scrape les flux RSS experts + destinations singulières,
récupère les images (og:image), et pousse dans Firestore.
"""

import os, json, re, time, hashlib, requests
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import firebase_admin
from firebase_admin import credentials, firestore

# ══════════ CONFIG ══════════
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FIREBASE_CREDS = os.environ.get("FIREBASE_CREDENTIALS", "")  # JSON string

# ══════════ EXPERT FEEDS ══════════
EXPERT_FEEDS = [
    {"tag": "duthion", "name": "Brice Duthion", "role": "Expert Tourisme Urbain", "rss": "https://www.tourmag.com/xml/syndication.rss?t=duthion", "page": "https://www.tourmag.com/tags/duthion/"},
    {"tag": "camille-le-guilloux", "name": "Camille Le Guilloux", "role": "Chroniqueuse", "rss": "https://www.tourmag.com/xml/syndication.rss?t=camille+le+guilloux", "page": "https://www.tourmag.com/tags/camille+le+guilloux/"},
    {"tag": "eric-didier", "name": "Eric Didier", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=eric+didier", "page": "https://www.tourmag.com/tags/eric+didier/"},
    {"tag": "cousin", "name": "Saskia Cousin", "role": "Chercheuse", "rss": "https://www.tourmag.com/xml/syndication.rss?t=cousin", "page": "https://www.tourmag.com/tags/cousin/"},
    {"tag": "jean-pinard", "name": "Jean Pinard", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=jean+pinard", "page": "https://www.tourmag.com/tags/jean+pinard/"},
    {"tag": "messager", "name": "Jean-Luc Messager", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=messager", "page": "https://www.tourmag.com/tags/messager/"},
    {"tag": "habibou", "name": "Habibou", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=habibou", "page": "https://www.tourmag.com/tags/habibou/"},
    {"tag": "daniel-borja", "name": "Daniel Borja", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=daniel+borja", "page": "https://www.tourmag.com/tags/daniel+borja/"},
    {"tag": "delporte", "name": "Yves Delporte", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=delporte", "page": "https://www.tourmag.com/tags/delporte/"},
    {"tag": "gallo", "name": "Adriana Gallo", "role": "Experte", "rss": "https://www.tourmag.com/xml/syndication.rss?t=gallo", "page": "https://www.tourmag.com/tags/gallo/"},
    {"tag": "jansen", "name": "Alix Jansen", "role": "Journaliste", "rss": "https://www.tourmag.com/xml/syndication.rss?t=jansen", "page": "https://www.tourmag.com/tags/jansen/"},
    {"tag": "mazzola", "name": "Jean-Pierre Mazzola", "role": "Éditorialiste", "rss": "https://www.tourmag.com/xml/syndication.rss?t=mazzola", "page": "https://www.tourmag.com/tags/mazzola/"},
    {"tag": "pointet", "name": "Pierre Pointet", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=pointet", "page": "https://www.tourmag.com/tags/pointet/"},
    {"tag": "ramond", "name": "Ramond", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=ramond", "page": "https://www.tourmag.com/tags/ramond/"},
    {"tag": "remi-duchange", "name": "Rémi Duchange", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=remi+duchange", "page": "https://www.tourmag.com/tags/remi+duchange/"},
    {"tag": "rodolphe-lenoir", "name": "Rodolphe Lenoir", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=rodolphe+lenoir", "page": "https://www.tourmag.com/tags/rodolphe+lenoir/"},
    {"tag": "guillaume-vigneron", "name": "Guillaume Vigneron", "role": "Expert", "rss": "https://www.tourmag.com/xml/syndication.rss?t=guillaume+vigneron", "page": "https://www.tourmag.com/tags/guillaume+vigneron/"},
]

DEST_SING_RSS = "https://www.tourmag.com/xml/syndication.rss?t=destinations+singulieres"

HEADERS = {
    "User-Agent": "TourMaG-Toolbox-Bot/1.0 (RSS scraper for tourism dashboard)"
}


# ══════════ FIREBASE INIT ══════════
def init_firebase():
    if FIREBASE_CREDS:
        cred_dict = json.loads(FIREBASE_CREDS)
        cred = credentials.Certificate(cred_dict)
    else:
        # fallback: fichier local pour dev
        cred = credentials.Certificate("firebase-creds.json")
    firebase_admin.initialize_app(cred)
    return firestore.client()


# ══════════ HTTP UTILS ══════════
def fetch_url(url, timeout=20):
    """Fetch une URL avec gestion d'erreurs."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  WARN fetch {url[:80]}: {e}")
        return None


def get_og_image(url):
    """Récupère l'image og:image d'une page web."""
    html = fetch_url(url)
    if not html:
        return ""
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def get_expert_photo(page_url):
    """Essaie de trouver la photo d'un expert sur sa page TourMaG."""
    html = fetch_url(page_url)
    if not html:
        return ""
    # Chercher une image auteur
    patterns = [
        r'<img[^>]+class=["\'][^"\']*(?:author|avatar|expert|photo)[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*(?:author|avatar|expert|photo)[^"\']*["\']',
        # Fallback: og:image de la page de l'expert
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            img = m.group(1)
            # Filtrer les logos/icônes trop génériques
            if "logo" not in img.lower() and "icon" not in img.lower() and "favicon" not in img.lower():
                return img
    return ""


# ══════════ RSS PARSING ══════════
def parse_rss(xml_text, max_items=5):
    """Parse un flux RSS et retourne une liste d'articles."""
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
        items = root.findall(".//item")
        results = []
        for item in items[:max_items]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc_raw = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()

            # Extraire image de enclosure ou description
            image = ""
            enc = item.find("enclosure")
            if enc is not None:
                image = enc.get("url", "")
            if not image:
                m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc_raw, re.IGNORECASE)
                if m:
                    image = m.group(1)

            # Nettoyer la description
            desc_clean = re.sub(r'<[^>]+>', '', desc_raw).strip()[:300]

            results.append({
                "title": title,
                "url": link,
                "description": desc_clean,
                "image": image,
                "date": pub_date,
            })
        return results
    except ET.ParseError as e:
        print(f"  WARN parse RSS: {e}")
        return []


# ══════════ SCRAPE EXPERTS ══════════
def scrape_experts(db):
    """Scrape les flux RSS de tous les experts et met à jour Firestore."""
    print("═══ EXPERTS ═══")
    batch = db.batch()
    count = 0

    for expert in EXPERT_FEEDS:
        tag = expert["tag"]
        print(f"  [{tag}] {expert['name']}...", end=" ", flush=True)

        # Récupérer les articles RSS
        xml = fetch_url(expert["rss"])
        articles = parse_rss(xml, max_items=3)

        # Récupérer les og:image des articles qui n'ont pas d'image
        for art in articles:
            if not art["image"] and art["url"]:
                art["image"] = get_og_image(art["url"])
                time.sleep(0.3)

        # Récupérer la photo de l'expert
        photo = get_expert_photo(expert["page"])
        time.sleep(0.3)

        doc_data = {
            "tag": tag,
            "name": expert["name"],
            "role": expert["role"],
            "page": expert["page"],
            "photo": photo,
            "articles": articles,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "rss-auto",
        }

        ref = db.collection("rssExperts").document(tag)
        batch.set(ref, doc_data, merge=True)
        count += 1
        print(f"{len(articles)} articles, photo={'✓' if photo else '✗'}")

    batch.commit()
    print(f"  → {count} experts mis à jour dans Firestore.")


# ══════════ SCRAPE DESTINATIONS SINGULIÈRES ══════════
def scrape_dest_singulieres(db):
    """Scrape le flux RSS Destinations Singulières et met à jour Firestore."""
    print("═══ DESTINATIONS SINGULIÈRES ═══")

    xml = fetch_url(DEST_SING_RSS)
    articles = parse_rss(xml, max_items=12)

    # Récupérer les og:image pour chaque article
    for art in articles:
        if not art["image"] and art["url"]:
            art["image"] = get_og_image(art["url"])
            time.sleep(0.3)

    print(f"  {len(articles)} articles trouvés")

    batch = db.batch()
    for i, art in enumerate(articles):
        doc_id = f"destsing-{i}"
        doc_data = {
            "index": i,
            "title": art["title"],
            "url": art["url"],
            "description": art["description"],
            "image": art["image"],
            "date": art["date"],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "source": "rss-auto",
        }
        ref = db.collection("rssDestSing").document(doc_id)
        batch.set(ref, doc_data, merge=True)
        img_status = "✓" if art["image"] else "✗"
        print(f"  [{doc_id}] {art['title'][:60]}... img={img_status}")

    # Supprimer les anciens si le flux a rétréci
    existing = db.collection("rssDestSing").stream()
    for doc in existing:
        idx = doc.to_dict().get("index", 999)
        if idx >= len(articles):
            batch.delete(doc.reference)
            print(f"  [supprimé] index {idx}")

    batch.commit()
    print(f"  → {len(articles)} destinations mises à jour dans Firestore.")


# ══════════ CLAUDE HAIKU ══════════
def call_haiku(prompt, system="", max_tokens=1500, retries=3):
    """Appelle Claude Haiku via l'API Anthropic."""
    if not ANTHROPIC_API_KEY:
        print("  WARN: pas de clé API Anthropic, skip IA")
        return None
    for attempt in range(retries):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": max_tokens,
                    "system": system or "Tu es un expert tourisme. Réponds uniquement en JSON valide, sans backticks ni markdown. Français.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=90,
            )
            if r.status_code == 429:
                wait = int(r.headers.get("retry-after", "30"))
                print(f"  Claude 429 — attente {wait}s", flush=True)
                time.sleep(wait)
                continue
            if r.status_code == 529:
                print("  Claude 529 (surchargé) — attente 30s", flush=True)
                time.sleep(30)
                continue
            r.raise_for_status()
            data = r.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            return text
        except Exception as e:
            print(f"  Claude ERR ({attempt+1}/{retries}): {e}", flush=True)
            if attempt < retries - 1:
                time.sleep(10)
    return None


def generate_dest_fiche(db, country, photo=""):
    """Génère une fiche destination via Claude Haiku et la stocke dans Firestore."""
    print(f"═══ FICHE DESTINATION: {country} ═══")

    prompt = f"""Génère une fiche destination professionnelle complète pour "{country}" à destination des agents de voyages français.

Réponds UNIQUEMENT avec un objet JSON valide avec cette structure :
{{
  "summary": "Résumé en 2 phrases",
  "sections": [
    {{"title": "Conseils MAE", "content": "Niveau de vigilance, zones à risque, recommandations"}},
    {{"title": "Formalités", "content": "Visa, passeport, vaccins obligatoires/recommandés"}},
    {{"title": "Dynamisme touristique", "content": "Fréquentation, tendances, saisonnalité, croissance"}},
    {{"title": "Points d'intérêt", "content": "Les incontournables à recommander"}},
    {{"title": "Tour-opérateurs", "content": "Principaux TO français qui programment cette destination"}},
    {{"title": "Conseils de vente", "content": "Arguments commerciaux, cibles, panier moyen, astuces"}}
  ]
}}"""

    text = call_haiku(prompt)
    if not text:
        print("  Échec de génération.")
        return None

    # Parse JSON
    clean = re.sub(r'```json|```', '', text).strip()
    try:
        fiche_data = json.loads(clean)
    except json.JSONDecodeError:
        print(f"  Erreur parsing JSON: {clean[:200]}")
        return None

    # Stocker dans Firestore comme module
    slug = re.sub(r'[^a-z0-9]', '-', country.lower())
    mod_id = f"dest-{slug}-{int(time.time())}"

    if not photo:
        photo = f"https://source.unsplash.com/800x400/?{requests.utils.quote(country)},travel,landmark"

    doc_data = {
        "title": country,
        "subtitle": "Focus destination de la semaine",
        "description": fiche_data.get("summary", ""),
        "url": "",
        "photo": photo,
        "category": "destinations",
        "categories": ["destinations", "dashboard"],
        "size": "large",
        "accent": "#D97706",
        "type": "focus",
        "active": True,
        "order": 0,
        "badge": "",
        "ficheData": fiche_data,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "ia-haiku",
    }

    db.collection("modules").document(mod_id).set(doc_data)
    print(f"  → Fiche publiée: {mod_id}")
    return mod_id


# ══════════ MAIN ══════════
def main():
    print(f"╔══ TourMaG Toolbox Scraper — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ══╗")

    db = init_firebase()

    # 1. Scrape experts
    scrape_experts(db)

    # 2. Scrape destinations singulières
    scrape_dest_singulieres(db)

    # 3. Génération IA destination (optionnel, via variable d'env)
    dest_country = os.environ.get("GENERATE_DEST_FICHE", "")
    if dest_country:
        dest_photo = os.environ.get("DEST_FICHE_PHOTO", "")
        generate_dest_fiche(db, dest_country, dest_photo)

    print("╚══ Terminé ══╝")


if __name__ == "__main__":
    main()
