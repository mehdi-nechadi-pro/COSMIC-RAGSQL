from pyongc.ongc import Dso
import numpy as np
import json
import wikipedia
import time
import sqlite3
import math
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

# Mapping officiel IAU (3 lettres -> Nom complet)
iau_constellations = {
    "AND": "Andromeda", "ANT": "Antlia", "APS": "Apus", "AQR": "Aquarius",
    "AQL": "Aquila", "ARA": "Ara", "ARI": "Aries", "AUR": "Auriga",
    "BOO": "Bootes", "CAE": "Caelum", "CAM": "Camelopardalis", "CNC": "Cancer",
    "CVN": "Canes Venatici", "CMA": "Canis Major", "CMI": "Canis Minor", "CAP": "Capricornus",
    "CAR": "Carina", "CAS": "Cassiopeia", "CEN": "Centaurus", "CEP": "Cepheus",
    "CET": "Cetus", "CHA": "Chamaeleon", "CIR": "Circinus", "COL": "Columba",
    "COM": "Coma Berenices", "CRA": "Corona Australis", "CRB": "Corona Borealis", "CRV": "Corvus",
    "CRT": "Crater", "CRU": "Crux", "CYG": "Cygnus", "DEL": "Delphinus",
    "DOR": "Dorado", "DRA": "Draco", "EQU": "Equuleus", "ERI": "Eridanus",
    "FOR": "Fornax", "GEM": "Gemini", "GRU": "Grus", "HER": "Hercules",
    "HOR": "Horologium", "HYA": "Hydra", "HYI": "Hydrus", "IND": "Indus",
    "LAC": "Lacerta", "LEO": "Leo", "LMI": "Leo Minor", "LEP": "Lepus",
    "LIB": "Libra", "LUP": "Lupus", "LYN": "Lynx", "LYR": "Lyra",
    "MEN": "Mensa", "MIC": "Microscopium", "MON": "Monoceros", "MUS": "Musca",
    "NOR": "Norma", "OCT": "Octans", "OPH": "Ophiuchus", "ORI": "Orion",
    "PAV": "Pavo", "PEG": "Pegasus", "PER": "Perseus", "PHE": "Phoenix",
    "PIC": "Pictor", "PSC": "Pisces", "PSA": "Piscis Austrinus", "PUP": "Puppis",
    "PYX": "Pyxis", "RET": "Reticulum", "SGE": "Sagitta", "SGR": "Sagittarius",
    "SCO": "Scorpius", "SCL": "Sculptor", "SCT": "Scutum", "SER": "Serpens",
    "SEX": "Sextans", "TAU": "Taurus", "TEL": "Telescopium", "TRI": "Triangulum",
    "TRA": "Triangulum Australe", "TUC": "Tucana", "UMA": "Ursa Major", "UMI": "Ursa Minor",
    "VEL": "Vela", "VIR": "Virgo", "VOL": "Volans", "VUL": "Vulpecula"
}

def get_constellation_name(abbr):
    return iau_constellations.get(abbr.upper(), "Inconnue")

#Load JSON
def load_database(db_path):
    try:
        with open(db_path, 'r') as f:
            db = json.load(f)
        print(f"✅ Base de données chargée : {len(db)} objets trouvées.")
        return db
    except FileNotFoundError:
        print(f"❌ ERREUR : Le fichier {db_path} est introuvable.")
        exit()

#Get best Magnitude (Bmag, Vmag, Jmag, Hmag, Kmag) -> On récupère en prio V (visuel) et a la limite B sinon le reste est infra
def get_best_mag(mag_tuple):
    
    if len(mag_tuple) > 1 and mag_tuple[1] is not None:
        return mag_tuple[1]

    if len(mag_tuple) > 0 and mag_tuple[0] is not None:
        return mag_tuple[0]

    return None


def clean_from_radians(rad_tuple):
    """
    Convertit les radians (donnés par PyONGC) en degrés (pour SQL).
    C'est la méthode la plus précise qui existe.
    """
    ra_rad = rad_tuple[0]
    dec_rad = rad_tuple[1]
    
    ra_deg = math.degrees(ra_rad)
    dec_deg = math.degrees(dec_rad)
    
    return ra_deg, dec_deg

################## MAIN ##################

con = sqlite3.connect("Celestial.db")
cur = con.cursor()

cur.execute("CREATE TABLE Celestial(name, type, constellation, ra, dec, magnitude, url, catalogue)")

caldwell_ngc = load_database("Archive/caldwell.json")


for i in range(1, 111):
    messier_name = f"M{i}"
    
    try:
        obj = Dso(messier_name) # Récupération des infos OPENGC
     
        obj_type = obj.type.replace(" ", "_")

        constellation_IAU = obj.constellation
        constellation = get_constellation_name(constellation_IAU)

        ra_final, dec_final = clean_from_radians(obj.rad_coords)
    
        magnitude = obj.magnitudes
        magnitude = get_best_mag(magnitude)
        magnitude_sql = magnitude if magnitude is not None else "NULL"

        url = get_image_wikipedia(messier_name)

        catalogue = "Messier"

        print(f"✅ {messier_name}, {obj_type}, {constellation}, {ra_final}, {dec_final}, {magnitude_sql},{url}")

        cur.execute(f"""INSERT INTO Celestial VALUES 
                ('{messier_name}', '{obj_type}', '{constellation}', {ra_final}, {dec_final}, {magnitude_sql}, '{url}', '{catalogue}')
        """)
        
    except Exception as e:
        print(f"❌ Erreur sur {messier_name}: {e}")

print("Catalogue IC/NGC (Caldwell)")

for caldwell_id, NGC_IC_Correspondance in caldwell_ngc.items():
    try:
        ngc_ic_id = NGC_IC_Correspondance

        obj = Dso(ngc_ic_id) # Récupération des infos OPENGC

        obj_type = obj.type.replace(" ", "_")
        
        constellation_IAU = obj.constellation
        constellation = get_constellation_name(constellation_IAU)

        ra_final, dec_final = clean_from_radians(obj.rad_coords)

        magnitude = obj.magnitudes
        magnitude = get_best_mag(magnitude)
        magnitude_sql = magnitude if magnitude is not None else "NULL"

        name_wikipedia = propre = re.sub(r"(\D)(\d)", r"\1 \2", ngc_ic_id)
    
        url = get_image_wikipedia(name_wikipedia)

        catalogue = "Caldwell"

        print(f"✅ {ngc_ic_id}, {obj_type}, {constellation}, {ra_final}, {dec_final}, {magnitude_sql},{url}")

        cur.execute(f""" INSERT INTO Celestial VALUES 
                ('{ngc_ic_id}', '{obj_type}', '{constellation}', {ra_final}, {dec_final}, {magnitude_sql}, '{url}', '{catalogue}')
        """)
    
    except Exception as e:
        print(f"❌ Erreur sur {ngc_ic_id}: {e}")


con.commit()