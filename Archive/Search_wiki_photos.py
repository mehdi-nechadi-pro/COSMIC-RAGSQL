from ddgs import DDGS
import time
import sqlite3

import requests

import requests
from typing import Optional
import re

def get_image_wikipedia(object_name: str, thumbnail_width: int = 1000) -> Optional[str]:
    """
    Récupère l'URL de l'image principale d'un objet via l'API Wikipédia (EN).
    
    Args:
        object_name (str): Le nom de l'objet (ex: 'M42', 'NGC 224').
        thumbnail_width (int): La largeur souhaitée en pixels (défaut: 1000px).
        
    Returns:
        str: L'URL directe de l'image (JPG/PNG) ou None si introuvable.
    """
    
    search_query = object_name.strip()
    if search_query.upper().startswith("M") and search_query[1:].isdigit():
        search_query = f"Messier {search_query[1:]}"
    
    url = "https://en.wikipedia.org/w/api.php"
    
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages",   
        "pithumbsize": thumbnail_width,
        "titles": search_query,
        "redirects": 1,         
        "formatversion": 2        
    }
    
    headers = {
        "User-Agent": "AstroSQLBot/1.0 (educational project; contact@univ.fr)"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if "query" in data and "pages" in data["query"]:
            page = data["query"]["pages"][0]
            
            if "missing" not in page and "thumbnail" in page:
                image_url = page["thumbnail"]["source"]
                
                if image_url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                    return image_url
                    
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Erreur réseau pour {object_name}: {e}")
    except Exception as e:
        print(f"⚠️ Erreur inattendue pour {object_name}: {e}")

    return None

con = sqlite3.connect("base.db")
cur = con.cursor()

def get_beautiful_image(query):
    """Cherche une image 'Wallpaper' sur DuckDuckGo"""
    with DDGS() as ddgs:
        keywords = f"{query} space astronomy hubble"
        try:
            results = list(ddgs.images(
                keywords,
                max_results=1,
                type_image='photo',
                safesearch='off'
            ))
            if results:
                return results[0]['image'] 
        except Exception as e:
            print(f"Erreur DDG sur {query}: {e}")
            time.sleep(2) 
    return None

def get_nasa_image(query):
    # API NASA Image Library (Pas besoin de clé pour la recherche simple)
    url = "https://images-api.nasa.gov/search"
    params = {
        "q": query,
        "media_type": "image",
    }
    try:
        r = requests.get(url, params=params)
        data = r.json()
        items = data['collection']['items']
        if items:
            return items[0]['links'][0]['href']
    except:
        return None

print(get_beautiful_image("NGC2516"))

cur.execute("SELECT name FROM Celestial")
rows = cur.fetchall()

count = 0

for i in range(len(rows)):
    name_raw = rows[i][0]

    if not name_raw.startswith("M"):
        name = propre = re.sub(r"(\D)(\d)", r"\1 \2", name_raw)
    else :
        name = name_raw
        
    new_url = get_image_wikipedia(name)

    if new_url:
        print(f"   ✅ Trouvé : {new_url}")
        #cur.execute("UPDATE Celestial SET url = ? WHERE name = ?", (new_url, name_raw))
        count += 1
    else:
        print("   ❌ Rien trouvé.")

print(f"Terminé ! {count} images mises à jour.")
con.commit()
con.close()
    
