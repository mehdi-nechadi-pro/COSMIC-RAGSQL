from astropy import units as u
from astropy.coordinates import SkyCoord, Distance
from pyongc.ongc import Dso
import sqlite3
import numpy as np
import pandas as pd
from geopy.geocoders import Nominatim
from astropy.coordinates import EarthLocation, AltAz, SkyCoord
from astropy.time import Time
import astropy.units as u

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

con = sqlite3.connect("base_fin.db")
cur = con.cursor()

row = cur.execute("""SELECT ra, dec FROM Celestial WHERE name = 'M2'
""").fetchone()

print(row)
print(row[0])

ra, dec = row

m2 = SkyCoord(ra * u.deg, dec * u.deg)
print("M2 : ", m2)

M1 = SkyCoord.from_name("M1")
#print(M1)
#print(M1.ra)
#print(M1.dec)


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
    

coord = getLocationByGeo("Paris")
lat, lon = coord
print(f"Résultat : {coord}")

location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)

#time = Time(datetime.now())
time = Time('2025-12-29 17:02:20')

lst = time.sidereal_time('mean', longitude=location.lon) # calcul du temps sidéral local (la valeur est l'ascension droite actuellement au zénith)
lst_hours = lst.to_value(u.hourangle)
print(lst_hours)
print("RA MIN = ", lst_hours)

ra_min = (lst_hours - 6) % 24 # RA -> DIT SI L'OBJET EST SUR LA FACE VISIBLE OU CACHEE 
ra_max = (lst_hours + 6) % 24
dec_min = lat - 90 # marge de 15 degrés DEC -> 

LST_current_meridian = float(round(lst_hours, 2))
RA_visible_start = float(round(ra_min, 2))
RA_visible_end = float(round(ra_max, 2))
Dec_visible_min = float(round(dec_min, 2))

RA_visible_start_angle = RA_visible_start*15
RA_visible_end_angle = RA_visible_end*15

print ("RA start = ", RA_visible_start, " | RA end = ", RA_visible_end)

print("RA_BDD :", RA_visible_start_angle, "-", RA_visible_end_angle)

# heure : 4h et 19h
# angle : 60 et 285

row = cur.execute(f"""SELECT name FROM Celestial WHERE ra 
    BETWEEN {RA_visible_start_angle} AND {RA_visible_end_angle} 
    AND dec >= {Dec_visible_min}""").fetchall()

# heure : 18h et 3h 
# angle : 285 et 45

if (RA_visible_end < RA_visible_start):
    row = cur.execute(f"""SELECT name FROM Celestial WHERE (ra 
        BETWEEN 0 AND {RA_visible_end_angle} OR (ra BETWEEN {RA_visible_start_angle} AND 360))
        AND dec >= {Dec_visible_min} AND (lower(name) LIKE '%M%')""").fetchall()
    print(f"""SELECT name FROM Celestial WHERE (ra 
        BETWEEN 0 AND {RA_visible_end_angle} OR (ra BETWEEN {RA_visible_start_angle} AND 360))
        AND dec >= {Dec_visible_min} AND (lower(name) LIKE '%M%')""")


print(row)