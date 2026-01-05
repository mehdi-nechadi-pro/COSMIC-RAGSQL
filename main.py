import sys
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from geopy.geocoders import Nominatim
from astropy_function import get_target_utc_date, format_utc_to_local_display

geolocator = Nominatim(user_agent="mon_astro_app_v1")

def get_city_from_latlon(lat, lon):
    try:
        location = geolocator.reverse((lat, lon), language='fr')
        address = location.raw.get('address', {})
        return address.get('city') or address.get('town') or address.get('village') or "Lieu Inconnu"
    except:
        return None

# --- IMPORT DU CERVEAU ---
# On part du principe que ton fichier s'appelle graph.py
try:
    from graph import graph
except ImportError:
    print("⚠️ ERREUR CRITIQUE : Impossible d'importer 'graph' depuis 'graph.py'")
    graph = None

app = FastAPI()

# Servir les fichiers statiques (JS, CSS, HTML)
app.mount("/static", StaticFiles(directory="static"), name="static")

class UserRequest(BaseModel): # Verification Typage et Init qui sera envoyé juste en bas
    message: str
    city: str
    hour: str 
    latitude: float
    longitude: float


@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.post("/api/chat")
async def chat_endpoint(request: UserRequest):
    print(f"📩 Message reçu : {request.message}")

    if not graph:
        return {"reply": "Erreur : Le graphe n'est pas chargé côté serveur.", "targets": []}
    
    print("HEURE DONNE DES LE DEBUT : ", request.hour)

    detected_city = get_city_from_latlon(request.latitude, request.longitude)

    try:
        initial_local_hour = format_utc_to_local_display(detected_city, request.hour)
    except Exception as e:
        print(f"⚠️ Erreur conversion init: {e}")
        initial_local_hour = request.hour

    # 1. Préparer l'état pour LangGraph
    initial_state = {
        "infos": request.message,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "hour": initial_local_hour,
        "final_target": [],
        "messages": [("user", request.message)] ,
        "detected_city": get_city_from_latlon(request.latitude, request.longitude)
    }


    # 2. Lancer l'IA
    try:
        result = graph.invoke(initial_state)
        
        # 3. Récupérer les résultats
        reply = result.get("vulgarisation_output", "Pas de réponse générée.")
        targets = result.get("final_target", [])
        latitude = result.get("latitude")
        longitude = result.get("longitude")
        hour = result.get("hour")
        detected_city = result.get("detected_city")

        print("🔥 RESULTATS BACKEND OBTENUS : Ville detectée= ", detected_city, "Heure : ", hour ," Latitude= ", latitude, " Longitude= ", longitude)

        dt_utc = get_target_utc_date(detected_city, result.get("hour"))
        final_local_hour_str = format_utc_to_local_display(detected_city, dt_utc)

        return {
            "reply": reply,
            "targets": targets,
            "latitude": latitude,
            "longitude": longitude,
            "hour": final_local_hour_str,
            "detected_city": detected_city
        }
        

    except Exception as e:
        print(f"🔥 Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))