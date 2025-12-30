from datetime import datetime
from zoneinfo import ZoneInfo
from astropy import units as u
from astropy.coordinates import SkyCoord, Distance
from pyongc.ongc import Dso
import sqlite3
import numpy as np
import pandas as pd
import geopy
from geopy.geocoders import Nominatim
from astropy.coordinates import EarthLocation, AltAz, SkyCoord
from astropy.time import Time
import astropy.units as u
from langchain_core.tools import tool


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

con = sqlite3.connect("Celestial.db")
cur = con.cursor()

from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

# Initialisation des outils (une seule fois pour la perf)
geolocator = Nominatim(user_agent="astronomy_master_agent_v1")
tf = TimezoneFinder()

def get_utc_time_from_city(city_name: str, local_date_str: str = "") -> datetime:
    """
    Prend une ville et une date/heure locale (String), trouve le fuseau horaire
    et renvoie un objet datetime CONVERTI EN UTC.
    
    Args:
        city_name: "Tokyo", "Lyon", "New York"
        local_date_str: "2025-12-30 19:25:00" (ou vide pour 'maintenant')
        
    Returns:
        datetime object (Timezone Aware en UTC) prêt pour Astropy.
    """
    try:
        # 1. Géocodage : Trouver Lat/Lon de la ville
        location = geolocator.geocode(city_name)
        if not location:
            print(f"⚠️ Erreur : Ville '{city_name}' inconnue. Utilisation UTC par défaut.")
            return datetime.now(pytz.utc)
            
        lat, lon = location.latitude, location.longitude

        # 2. Trouver le fuseau horaire (ex: 'Asia/Tokyo')
        tz_str = tf.timezone_at(lng=lon, lat=lat)
        if not tz_str:
            print(f"⚠️ Erreur : Pas de fuseau trouvé pour {city_name}. Utilisation UTC.")
            return datetime.now(pytz.utc)
            
        local_tz = pytz.timezone(tz_str)

        if not local_date_str or local_date_str.strip() == "":
            dt_local = datetime.now(local_tz)
        else:
            try:
                dt_naive = datetime.strptime(local_date_str, "%Y-%m-%d %H:%M:%S")

                dt_local = local_tz.localize(dt_naive)
            except ValueError:
                # Fallback si le format est pourri
                print(f"⚠️ Format date invalide '{local_date_str}'. On prend NOW.")
                dt_local = datetime.now(local_tz)

        dt_utc = dt_local.astimezone(pytz.utc)

        print(f"🌍 CONVERSION TIMEZONE :")
        print(f"   - Ville : {city_name} ({tz_str})")
        print(f"   - Local : {dt_local}")
        print(f"   - UTC   : {dt_utc} <--- C'est ça qu'on envoie à Astropy")

        return dt_utc

    except Exception as e:
        print(f"❌ Erreur critique Timezone : {e}")
        return datetime.now(pytz.utc)
    
print(get_utc_time_from_city("Tokyo","2025-12-30 19:25:00"))

def getLocationByGeo(cityname):
    geolocator = Nominatim(user_agent="astro_app_learning_v1")

    try:
        location = geolocator.geocode(cityname, timeout=10)
        
        if location is None:
            print(f"Erreur : La ville '{cityname}' est introuvable dans la base Nominatim.")
            return None
            
        return (location.latitude, location.longitude)

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Erreur de service Geopy : {e}")
        return None
    except Exception as e:
        print(f"Erreur inattendue : {e}")
        return None

@tool
def get_ra_dec_constraint(city: str, time_input: str = "") -> str:
    """
    Calcule les contraintes d'Ascension Droite (RA) et de Déclinaison (DEC) 
    pour une ville et une heure données.
    Args:
        city: Le nom de la ville (ex: 'Lyon').
        time_input: L'heure au format 'YYYY-MM-DD HH:MM:SS'.
    """

    time_utc = get_utc_time_from_city(city,time_input)
    if time_utc is None:
        observation_time = Time(datetime.now())
    else:
        observation_time = Time(time_utc)

    print("LIEU : ", city, " HEURE : ", observation_time)
        
    coord = getLocationByGeo(city)
    lat, lon = coord
    print(f"Coordonnées : {coord}")

    location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)

    lst = observation_time.sidereal_time('mean', longitude=location.lon) # calcul du temps sidéral local (la valeur est l'ascension droite actuellement au zénith)
    lst_hours = lst.to_value(u.hourangle)
    lst_deg = lst_hours * 15
    print("LST hours : ", lst_hours)

    ra_min_deg = (lst_deg - 90) % 360 # RA -> DIT SI L'OBJET EST SUR LA FACE VISIBLE OU CACHEE 
    ra_max_deg = (lst_deg + 90) % 360 # On transforme direct en angle (90 degré c'est 6h)
    dec_min = lat - 90 # marge de 15 degrés pour la visibilité 

    #LST_current_meridian = float(round(lst_hours, 2))
    ra_start = float(round(ra_min_deg, 2))
    ra_end = float(round(ra_max_deg, 2))
    Dec_visible_min = float(round(dec_min, 2))
    print("DEC : ", Dec_visible_min)

    constraint = f""" ra BETWEEN {ra_start} AND {ra_end} AND dec >= {Dec_visible_min}"""

    if (ra_end < ra_start):
        constraint = f"""(ra BETWEEN 0 AND {ra_end} OR (ra BETWEEN {ra_start} AND 360)) AND dec >= {Dec_visible_min}"""

    if ra_end < ra_start:
        print(f"Intervalle RA (Split) : [0 - {ra_end}] OR [{ra_start} - 360]")
    else:
        print(f"Intervalle RA (Simple) : [{ra_start} - {ra_end}]")
    print("LST:", lst.to_string(unit=u.hour, sep='hms'))

    return {
    "sql_where": constraint,    
    "lst_hms": lst.to_string(unit=u.hour, sep='hms')
}

# constraint = get_ra_dec_constraint("Paris")["sql_where"]

# print(f"""SELECT name FROM Celestial WHERE {constraint} """)
# row = cur.execute(f"""SELECT name FROM Celestial WHERE {constraint} """).fetchall()
# print(row)
