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

con = sqlite3.connect("base_fin.db")
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
    print("LST hours : ", lst_hours)

    ra_min = (lst_hours - 6) % 24 # RA -> DIT SI L'OBJET EST SUR LA FACE VISIBLE OU CACHEE 
    ra_max = (lst_hours + 6) % 24
    dec_min = lat - 90 # marge de 15 degrés pour la visibilité 

    LST_current_meridian = float(round(lst_hours, 2))
    RA_visible_start = float(round(ra_min, 2))
    RA_visible_end = float(round(ra_max, 2))
    Dec_visible_min = float(round(dec_min, 2))

    RA_visible_start_angle = RA_visible_start*15
    RA_visible_end_angle = RA_visible_end*15

    constraint = f""" ra BETWEEN {RA_visible_start} AND {RA_visible_end} 
        AND dec >= {Dec_visible_min}"""

    if (RA_visible_end < RA_visible_start):
        constraint = f"""(ra BETWEEN 0 AND {RA_visible_end_angle} 
        OR (ra BETWEEN {RA_visible_start_angle} AND 360))
        AND dec >= {Dec_visible_min}"""

    print("Intervalle angle RA: [",RA_visible_start_angle ,"-", RA_visible_end_angle,"]")

    return constraint


constraint = get_ra_dec_constraint("Paris")

# print(f"""SELECT name FROM Celestial WHERE {constraint} """)
row = cur.execute(f"""SELECT name FROM Celestial WHERE {constraint} """).fetchall()
print(row)
