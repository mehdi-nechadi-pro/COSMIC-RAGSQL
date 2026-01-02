from datetime import datetime
from astropy import units as u
import sqlite3
from geopy.geocoders import Nominatim
from astropy.coordinates import EarthLocation
from astropy.time import Time
import astropy.units as u
from langchain_core.tools import tool
import math
from timezonefinder import TimezoneFinder
import pytz

# Initialisation des outils (une seule fois pour la perf)
geolocator = Nominatim(user_agent="astronomy_master_agent_v1")
tf = TimezoneFinder()

def maths_altitude(ra, dec, lat, lst, min_alt=0):
    """
    Prend un RA/DEC d'un objet et la latitude et le LST d'une localisation
    Renvoie 1 si l'objet est visible et 0 sinon 
    """
    try:
        ra_rad = math.radians(float(ra))
        dec_rad = math.radians(float(dec))
        lat_rad = math.radians(float(lat))
        lst_rad = math.radians(float(lst) * 15)
        
        ha_rad = lst_rad - ra_rad
        
        sin_alt = (math.sin(lat_rad) * math.sin(dec_rad)) + \
                  (math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad))
        
        limit = math.sin(math.radians(float(min_alt)))
        return 1 if sin_alt > limit else 0
    except:
        return 0

def get_utc_time_from_city(city_name: str, local_date_str: str = ""):
    """
    Retourne un tuple : (datetime_utc, latitude, longitude)
    Renvoie (None, None, None) en cas d'échec critique.
    """
    try:
        # 1. Géocodage
        location = geolocator.geocode(city_name)
        if not location:
            print(f"⚠️ Erreur : Ville '{city_name}' inconnue.")
            return None, None, None
            
        lat, lon = location.latitude, location.longitude

        # 2. Timezone
        tz_str = tf.timezone_at(lng=lon, lat=lat)
        if not tz_str:
            print(f"⚠️ Avertissement : Pas de fuseau trouvé pour {city_name}. Utilisation UTC par défaut.")
            return datetime.now(pytz.utc), lat, lon
            
        local_tz = pytz.timezone(tz_str)

        # 3. Conversion Date
        if not local_date_str or local_date_str.strip() == "":
            dt_local = datetime.now(local_tz)
        else:
            try:
                dt_naive = datetime.strptime(local_date_str, "%Y-%m-%d %H:%M:%S")
                dt_local = local_tz.localize(dt_naive)
            except ValueError:
                print(f"⚠️ Format date invalide. Utilisation de NOW.")
                dt_local = datetime.now(local_tz)

        dt_utc = dt_local.astimezone(pytz.utc)

        print(f"🌍 {city_name} ({lat:.2f}, {lon:.2f}) | Local: {dt_local} -> UTC: {dt_utc}")
        return dt_utc, lat, lon

    except Exception as e:
        print(f"❌ Erreur critique Timezone : {e}")
        return None, None, None
    
con = sqlite3.connect("Celestial.db")
cur = con.cursor()
con.create_function("IS_VISIBLE", 5, maths_altitude) 
cur = con.cursor()

@tool
def get_ra_dec_constraint(city: str, time_input: str = "") -> str:
    """
    Calcule les contraintes d'Ascension Droite (RA) et de Déclinaison (DEC) 
    pour une ville et une heure données.
    Args:
        city: Le nom de la ville (ex: 'Lyon').
        time_input: L'heure au format 'YYYY-MM-DD HH:MM:SS'.
    """

    time_utc, lat, lon = get_utc_time_from_city(city,time_input)
    if time_utc is None:
        observation_time = Time(datetime.now())
    else:
        observation_time = Time(time_utc)

    print("LIEU : ", city, " HEURE : ", observation_time)

    location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)

    lst = observation_time.sidereal_time('mean', longitude=location.lon) # calcul du temps sidéral local (la valeur est l'ascension droite actuellement au zénith)
    lst_hours = lst.to_value(u.hourangle)
    print("LST hours : ", lst_hours)

    constraint = f""" IS_VISIBLE(ra,dec,{lat}, {lst_hours}, 5)"""
    return {
    "sql_where": constraint,    
    "lst_hms": lst.to_string(unit=u.hour, sep='hms')
}
