from pyongc.ongc import Dso
import numpy as np
import json
import wikipedia
import time
import sqlite3
import math
from astroquery.simbad import Simbad
from astroquery.vizier import Vizier

con = sqlite3.connect("base.db")
cur = con.cursor()

cur.execute("CREATE TABLE Celestial(name, type, constellation, ra, dec, magnitude, url)")

# Mapping officiel IAU (3 lettres -> Nom complet)
iau_constellations = {
    "AND": "Andromeda", "ANT": "Antlia", "APS": "Apus", "AQR": "Aquarius",
    "AQL": "Aquila", "ARA": "Ara", "ARI": "Aries", "AUR": "Auriga",
    "BOO": "Boötes", "CAE": "Caelum", "CAM": "Camelopardalis", "CNC": "Cancer",
    "CVN": "Canes Venatici", "CMAR": "Canis Major", "CMIN": "Canis Minor", "CAP": "Capricornus",
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

# Fonction utilitaire
def get_constellation_name(abbr):
    return iau_constellations.get(abbr.upper(), "Inconnue")

def get_seds_messier_image(messier_id):
    number = messier_id[1:] 
    
    url = f"http://messier.seds.org/Jpg/m{number}.jpg"
    
    return url

def load_database(db_path):
    try:
        with open(db_path, 'r') as f:
            db = json.load(f)
        print(f"✅ Base de données chargée : {len(db)} objets trouvées.")
        return db
    except FileNotFoundError:
        print(f"❌ ERREUR : Le fichier {db_path} est introuvable.")
        exit()

caldwell_ngc = load_database("caldwell.json")
caldwell_ngc_url = load_database("caldwell_data_complete.json")


def get_best_mag(mag_tuple):
    
    if len(mag_tuple) > 1 and mag_tuple[1] is not None:
        return mag_tuple[1]

    if len(mag_tuple) > 0 and mag_tuple[0] is not None:
        return mag_tuple[0]

    for mag in mag_tuple:
        if mag is not None:
            return mag

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


for i in range(1, 111):
    messier_name = f"M{i}"
    
    try:
        obj = Dso(messier_name)
        
        ra_final, dec_final = clean_from_radians(obj.rad_coords)
    
        magnitude = obj.magnitudes
        obj_type = obj.type
        constellation = obj.constellation

        magnitude = obj.magnitudes
        obj_type = obj.type.replace(" ", "_")
        url = get_seds_messier_image(messier_name)
        mag = get_best_mag(magnitude)
        valeur_sql = mag if mag is not None else "NULL"

        print(f"✅ {messier_name}, {obj_type}, {get_constellation_name(constellation)}, {ra_final}, {dec_final}, {valeur_sql},{url}")

        cur.execute(f"""INSERT INTO Celestial VALUES ('{messier_name}', '{obj_type}', '{get_constellation_name(constellation)}', {ra_final}, {dec_final}, {valeur_sql}, '{url}')
        """)
        
    except Exception as e:
        print(f"❌ Erreur sur {messier_name}: {e}")

print("Catalogue IC/NGC")

for caldwell_id, details in caldwell_ngc_url.items():
    try:
        ngc_ic_id = details['scientific_name']
        url = details['image_url']
        obj = Dso(ngc_ic_id)
        ra_final, dec_final = clean_from_radians(obj.rad_coords)
        constellation = obj.constellation
        
        magnitude = obj.magnitudes
        obj_type = obj.type.replace(" ", "_")

        mag = get_best_mag(magnitude)
        valeur_sql = mag if mag is not None else "NULL"

        print(f"✅ {ngc_ic_id}, {obj_type}, {get_constellation_name(constellation)}, {ra_final}, {dec_final}, {valeur_sql},{url}")

        cur.execute(f""" INSERT INTO Celestial VALUES ('{ngc_ic_id}', '{obj_type}', '{valeur_sql}', {ra_final}, {dec_final}, {valeur_sql}, '{url}')
        """)
    
    except Exception as e:
        print(f"❌ Erreur sur {ngc_ic_id}: {e}")


con.commit()

#NAME, TYPE, CONSTELLATIONS, RA, DEC, MAGNITUDE, URL

# def get_wiki_image_safe(search_term):
#     try:
#         # On cherche la page précise "NGC 188"
#         page = wikipedia.page(search_term, auto_suggest=False)
        
#         # On prend la première image qui est un JPG et pas un Logo
#         for img in page.images:
#             if img.lower().endswith('.jpg') and "logo" not in img.lower():
#                 return img
#         return None
#     except:
#         return None


# print("📸 Début de la récupération des images NGC/IC...")

# results = {}

# for c_id, ngc_name in caldwell_ngc.items():
    
#     # On interroge Wikipédia avec le VRAI nom (NGC 188, pas C1)
#     image_url = get_wiki_image_safe(ngc_name)
    
#     if image_url:
#         print(f"✅ {c_id} ({ngc_name}) : Image trouvée !")
#         results[c_id] = image_url
#     else:
#         print(f"⚠️ {c_id} ({ngc_name}) : Pas d'image trouvée.")
#         results[c_id] = "PLACEHOLDER_URL" # Mettez une image par défaut
    
#     time.sleep(1) 

# print(results)
# final_data = {}

# for c_id, url_image in results.items():
    
#     # On récupère le nom scientifique (NGC/IC) depuis ton dictionnaire de départ
#     scientific_name = caldwell_ngc.get(c_id, "Inconnu")
    
#     # On crée la structure propre
#     final_data[c_id] = {
#         "scientific_name": scientific_name, # Ex: "NGC 188"
#         "image_url": url_image              # Ex: "https://..."
#     }

# # Sauvegarde dans le JSON
# with open("caldwell_data_complete.json", "w", encoding="utf-8") as f:
#     json.dump(final_data, f, indent=4, ensure_ascii=False)

# print("✅ Fichier 'caldwell_data_complete.json' généré ! Tu as tout dedans.")

#print("Base de données consolidée prête !")
