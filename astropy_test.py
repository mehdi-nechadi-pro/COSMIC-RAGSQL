from datetime import datetime
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

row = cur.execute("""SELECT ra, dec FROM Celestial WHERE name = 'M1'
""").fetchone()

ra, dec = row

m1 = SkyCoord(ra * u.deg, dec * u.deg)
print(m1)

M1 = SkyCoord.from_name("M1")
print(M1)
print(M1.ra)
print(M1.dec)

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
    

coord = getLocationByGeo("Lyon")
lat, lon = coord
print(f"Résultat : {coord}")

location = EarthLocation(lat*u.deg, lon*u.deg)

time = Time(datetime.now())
print(time)

lst = time.sidereal_time('mean', longitude=location.lon)
lst_hours = lst.to_value(u.hourangle)

ra_min = (lst_hours - 6) % 24
ra_max = (lst_hours + 6) % 24
dec_min = lat - 90 + 15 # marge de 15 degrés 

LST_current_meridian = float(round(lst_hours, 2))
RA_visible_start = float(round(ra_min, 2))
RA_visible_end = float(round(ra_max, 2))
Dec_visible_min = float(round(dec_min, 2))


print(LST_current_meridian, " RA [", RA_visible_start, "-",RA_visible_end, "] Dec > ",Dec_visible_min)

row = cur.execute(f"""SELECT name FROM Celestial WHERE ra 
    BETWEEN {RA_visible_end} AND {RA_visible_start} 
    AND dec >= {Dec_visible_min}""").fetchall()

print(row)