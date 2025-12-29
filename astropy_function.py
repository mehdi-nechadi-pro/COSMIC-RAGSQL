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

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

con = sqlite3.connect("Celestial.db")
cur = con.cursor()

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

def get_ra_dec_constraint(city: str, time_input=None) -> str:
    if time_input is None:
        observation_time = Time(datetime.now())
    else:
        observation_time = Time(time_input)

    print("LIEU : ", city, " HEURE : ", observation_time)
        
    coord = getLocationByGeo(city)
    lat, lon = coord
    print(f"Résultat : {coord}")

    location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)

    lst = observation_time.sidereal_time('mean', longitude=location.lon) # calcul du temps sidéral local (la valeur est l'ascension droite actuellement au zénith)
    lst_hours = lst.to_value(u.hourangle)
    lst_deg = lst_hours * 15
    print("LST hours : ", lst_hours)

    ra_min_deg = (lst_hours - 90) % 360 # RA -> DIT SI L'OBJET EST SUR LA FACE VISIBLE OU CACHEE 
    ra_max_deg = (lst_hours + 90) % 360 # On transforme direct en angle (90 degré c'est 6h)
    dec_min = lat - 90 # marge de 15 degrés pour la visibilité 

    #LST_current_meridian = float(round(lst_hours, 2))
    ra_start = float(round(ra_min_deg, 2))
    ra_end = float(round(ra_max_deg, 2))
    Dec_visible_min = float(round(dec_min, 2))

    constraint = f""" ra BETWEEN {ra_start} AND {ra_end} 
        AND dec >= {Dec_visible_min}"""

    if (ra_end < ra_start):
        constraint = f"""(ra BETWEEN 0 AND {ra_end} 
        OR (ra BETWEEN {ra_start} AND 360))
        AND dec >= {Dec_visible_min}"""

    print("Intervalle angle RA: [",ra_start ,"-", ra_end,"]")

    return {
    "sql_where": constraint,
    "meridian_deg": lst_deg,
    "lst_hms": lst.to_string(unit=u.hour, sep='hms')
}

constraint = get_ra_dec_constraint("Paris")["sql_where"]

# print(f"""SELECT name FROM Celestial WHERE {constraint} """)
row = cur.execute(f"""SELECT name FROM Celestial WHERE {constraint} """).fetchall()
print(row)
