from datetime import datetime
from astropy import units as u
from geopy.geocoders import Nominatim
from astropy.coordinates import EarthLocation, get_sun, AltAz, solar_system_ephemeris, get_body
from astropy.time import Time
from dateutil import parser
import math
from timezonefinder import TimezoneFinder
import pytz
from functools import lru_cache

geolocator = Nominatim(user_agent="mon_astro_app_v1")

@lru_cache(maxsize=128)
def get_coordinates(city_name: str):
    print("Get Coords : ", city_name)
    """
    Prend un nom de ville (ex: 'Lyon') et renvoie (lat, lon) et la timezone.
    Renvoie None si introuvable.
    """
    try:
        location = geolocator.geocode(city_name)
        if not location:            
            return None, "UTC"
        
        lat = location.latitude
        lon = location.longitude
        tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
        return (lat, lon), tz_str
    
    except Exception as e:
        print(f"Erreur Geocoding : {e}")
        return None

tf = TimezoneFinder()

def format_utc_to_local(city: str, utc_dt: datetime, tz_str= None) -> str:
    """
    Prend une date UTC et une ville et une timezone, et renvoie l'heure locale formatée pour le front-end.
    Ex: 2026-01-04 19:15 UTC -> "2026-01-04 20:15:00" (si Paris)
    """

    if isinstance(utc_dt, str):
        try:
            utc_dt = parser.parse(utc_dt)
        except Exception:
            return utc_dt
        
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)

    if(tz_str is None):
        coords, tz_str = get_coordinates(city)
        if not coords:
            return utc_dt.strftime("%Y-%m-%d %H:%M:%S") + " (UTC)" # Fallback
    
    target_tz = pytz.timezone(tz_str) if tz_str else pytz.utc
    
    local_dt = utc_dt.astimezone(target_tz)

    print ("Format UTC -> Local (", city,",",utc_dt, " UTC) -> ", local_dt.isoformat())
    
    return local_dt.isoformat()

def get_target_utc_date(timezone, user_input_str: str = "") -> datetime:
    """
    Transforme l'input du LLM en UTC grâce à l'heure locale et la timezone
    """
    now_utc = datetime.now(pytz.utc)

    if not user_input_str or user_input_str.strip() == "":
        return now_utc

    target_tz = pytz.timezone(timezone) if timezone else pytz.utc

    default_dt = now_utc.astimezone(target_tz)

    try:
        clean_str = user_input_str.strip()

        parsed = parser.parse(clean_str, default=default_dt)

        if parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) is not None:
            final_utc = parsed.astimezone(pytz.utc)

        else:
            local_dt = target_tz.localize(parsed)
            final_utc = local_dt.astimezone(pytz.utc)
            
    except (ValueError, TypeError) as e:
        print(f"🔥 Erreur parsing '{user_input_str}', fallback NOW.")
        final_utc = now_utc
    
    print("Get Target UTC (" ",",user_input_str,  ": LOCAL) -> ",final_utc ," ")
    return final_utc

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

def get_ra_dec_constraint(lat: float, lon: float, time_utc: str = "") -> str:
    """
    Calcule les contraintes d'Ascension Droite (RA) et de Déclinaison (DEC) 
    pour une ville et une heure données.
    Args:
        lat: La latitude
        lon: La longitude
        time_utc: L'heure au format UTC
    """

    observation_time = Time(time_utc)

    location = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)

    lst = observation_time.sidereal_time('mean', longitude=location.lon) # calcul du temps sidéral local (la valeur est l'ascension droite actuellement au zénith)
    lst_hours = lst.to_value(u.hourangle)
    print("LST hours : ", lst_hours)

    sun = get_sun(observation_time)
    sun_altaz = sun.transform_to(AltAz(obstime=observation_time, location=location))
    sun_altitude = sun_altaz.alt.degree
    print (sun_altitude)
    if sun_altitude > -18: # crepuscule astronomiquea
        # print("SUN IS THERE")
        return {
            "error": f"The sun is at altitude={sun_altitude}, so nothing except it can be seen",
            "sql_where": "",
            "lst_hms": lst.to_string(unit=u.hour, sep='hms')
        }

    # print("SUN IS NOT THERE")
    constraint = f""" IS_VISIBLE(ra,dec,{lat}, {lst_hours}, 5)"""
    return {
    "error" : "",
    "sql_where": constraint,    
    "lst_hms": lst.to_string(unit=u.hour, sep='hms')
}


def get_visible_solar_system_objects(lat:str, lon:str, time_utc: str):
    """
    Simplifié : Renvoie un booléen 'is_daytime' et la liste 'observables'.
    Si il fait jour, la liste ne contient QUE le Soleil/Lune (si levés).
    Les planètes invisibles sont exclues d'office.
    Args: 
    location_lat: location latitude
    location_lon: location longitude 
    time_utc: L'heure au format UTC
    """
    t = Time(time_utc)

    loc = EarthLocation(lat=lat*u.deg, lon=lon*u.deg)
    
    # 1. Check Soleil (Jour ou Nuit ?)
    with solar_system_ephemeris.set('builtin'):
        altaz_frame = AltAz(obstime=t, location=loc)
        sun_obj = get_body('sun', t, loc).transform_to(altaz_frame)
        sun_alt = float(sun_obj.alt.degree)
        
    is_daytime = sun_alt > -6
    
    if is_daytime:
        targets = ['sun', 'moon']
    else:
        targets = ['moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune']

    observables = []

    # 3. Calculs
    with solar_system_ephemeris.set('builtin'):
        for name in targets:

            if name == 'sun':
                alt, az = sun_alt, float(sun_obj.az.degree)
                icrs = get_body('sun', t, loc) # Juste pour RA/Dec
            else:
                body = get_body(name, t, loc)
                pos = body.transform_to(altaz_frame)
                alt, az = float(pos.alt.degree), float(pos.az.degree)
                icrs = body

            if alt > 0:
                observables.append({
                    "name": name,
                    "alt": round(alt, 1),
                    "az": round(az, 1),
                    "ra": round(float(icrs.ra.degree), 4),
                    "dec": round(float(icrs.dec.degree), 4)
                })

    return {
        "is_daytime": is_daytime,
        "observables": observables
    }

# print(get_visible_solar_system_objects(48.8566,2.3522,'2026-01-04 18:00:00'))