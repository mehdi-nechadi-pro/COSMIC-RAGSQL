import math
import re
from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, get_body, get_sun, solar_system_ephemeris
from astropy.time import Time
from dateutil import parser
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz

geolocator = Nominatim(user_agent="mon_astro_app_v1")
tf = TimezoneFinder()

TIME_TOKEN_RULES = {
    "maintenant": None,
    "now": None,
    "ce soir": "20:00",
    "tonight": "20:00",
    "demain matin": "06:00",
    "tomorrow morning": "06:00",
}


@lru_cache(maxsize=128)
def get_coordinates(city_name: str):
    """
    Prend un nom de ville et renvoie (lat, lon) et la timezone.
    Retourne toujours une paire cohérente ou lève une erreur contrôlée au niveau appelant.
    """
    try:
        location = geolocator.geocode(city_name)
        if not location:
            return (None, None), "UTC"

        lat = location.latitude
        lon = location.longitude
        tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
        return (lat, lon), tz_str

    except Exception as e:
        print(f"Erreur Geocoding : {e}")
        return (None, None), "UTC"


def resolve_city_to_coords_and_tz(city_name: str):
    coords, tz_name = get_coordinates(city_name)
    if coords[0] is None or coords[1] is None:
        raise ValueError(f"Ville introuvable ou non resolvable : {city_name}")
    return coords, tz_name


def resolve_local_time_to_utc(timezone_name: str, user_input_str: str = "", now_local: datetime | None = None) -> datetime:
    """
    Centralise la conversion d'une heure locale humaine vers UTC.
    Le LLM ne doit plus fournir le datetime final ; il fournit seulement un contexte.
    """
    target_tz = ZoneInfo(timezone_name) if timezone_name else ZoneInfo("UTC")
    if now_local is None:
        now_local = datetime.now(target_tz)

    clean_str = (user_input_str or "").strip()
    if clean_str == "":
        return now_local.astimezone(ZoneInfo("UTC"))

    normalized = clean_str.lower().strip()
    for key, value in TIME_TOKEN_RULES.items():
        if normalized == key:
            if value is None:
                return now_local.astimezone(ZoneInfo("UTC"))
            hh, mm = map(int, value.split(":"))
            candidate = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if candidate <= now_local:
                candidate += timedelta(days=1)
            return candidate.astimezone(ZoneInfo("UTC"))

    match = re.search(r"(demain|tomorrow).*?(\d{1,2})\s*(?:h|heure|:)?\s*(\d{0,2})", normalized)
    if match:
        hour = int(match.group(2))
        minute = int(match.group(3)) if match.group(3) else 0
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        return candidate.astimezone(ZoneInfo("UTC"))

    try:
        parsed = parser.parse(clean_str, default=now_local)
        if parsed.tzinfo is not None:
            return parsed.astimezone(ZoneInfo("UTC"))
        local_dt = parsed.replace(tzinfo=target_tz)
        return local_dt.astimezone(ZoneInfo("UTC"))
    except (ValueError, TypeError):
        return now_local.astimezone(ZoneInfo("UTC"))


def get_utc_date(timezone, user_input_str: str = "") -> datetime:
    """Compatibilité: garde l'ancien nom et délègue au système unifié."""
    tz_name = timezone or "UTC"
    now_local = datetime.now(ZoneInfo(tz_name)) if tz_name != "UTC" else datetime.now(ZoneInfo("UTC"))
    return resolve_local_time_to_utc(tz_name, user_input_str, now_local)

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

def get_celestial_constraint(lat: float, lon: float, time_utc: str = "") -> str:
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

    sun = get_sun(observation_time)
    sun_altaz = sun.transform_to(AltAz(obstime=observation_time, location=location))
    sun_altitude = sun_altaz.alt.degree

    if sun_altitude > -18: # Crepuscule Astronomique
        return {
            "error": f"The sun is at altitude={sun_altitude}, so no deep sky objects can be seen",
            "sql_where": "",
            "lst_hms": lst.to_string(unit=u.hour, sep='hms')
        }
    
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
        
    is_daytime = sun_alt > -6 # Crépuscule Astronomique
    
    if is_daytime:
        targets = ['moon']
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