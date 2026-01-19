from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from geopy.geocoders import Nominatim
from astropy_function import format_utc_to_local
from graph import graph

geolocator = Nominatim(user_agent="mon_astro_app_v1")

def get_city_from_latlon(lat, lon):
    try:
        location = geolocator.reverse((lat, lon), language='fr')
        address = location.raw.get('address', {})
        return address.get('city') or address.get('town') or address.get('village') or "Lieu Inconnu"
    except:
        return None


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

class UserRequest(BaseModel): 
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

    detected_city = get_city_from_latlon(request.latitude, request.longitude)
    print("Heure donnée par le front : ", request.hour, " et ville : ", detected_city)

    # Initial state for the graph
    initial_state = {
        "infos": request.message,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "hour": request.hour,
        "final_target": [],
        "messages": [("user", request.message)] ,
        "detected_city": detected_city
    }

    try:
        # Graph Call
        result = graph.invoke(initial_state)
        
        # Get Results from the graph response
        reply = result.get("vulgarisation_output", "Pas de réponse générée.")
        targets = result.get("final_target", [])
        latitude = result.get("latitude")
        longitude = result.get("longitude")
        hour = result.get("hour")
        detected_city = result.get("detected_city")
        timezone = result.get("timezone")
        constellations = result.get("constellations_target")
        local_hour = result.get("local_hour")
        print("constellation: ",constellations)

        final_local_hour_str = format_utc_to_local(detected_city, hour, timezone) # obligé d'envoyer en local sinon le LLM comprends rien

        print("🔥 Résultats données par le (graph) : Ville detectée= ", detected_city, "Heure UTC : ", hour ," Latitude= ", latitude, " Longitude= ", longitude)

        # Return result to the front-end
        return {
            "reply": reply,
            "targets": targets,
            "latitude": latitude,
            "longitude": longitude,
            "hour": final_local_hour_str,
            "local_hour": local_hour,
            "detected_city": detected_city,
            "constellations": constellations
        }
        

    except Exception as e:
        print(f"🔥 Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))