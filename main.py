from typing import Any, Dict, List
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from graph import graph

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

class UserRequest(BaseModel): 
    message: str
    city: str
    latitude: float
    longitude: float
    history: List[Dict[str, Any]] = []

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.post("/api/chat")
async def chat_endpoint(request: UserRequest):
    print(f"📩 Message reçu : {request.message}")

    history_msgs = [
        ("assistant" if m.get('role') in ["ai", "assistant", "bot"] else "user", m.get('content', ''))
        for m in request.history if m.get('content')
    ]
    full_conversation = history_msgs[-4:]

    print("Données par le front-end : \n Prompt : ", request.message,"\n Ville :", request.city, "(",request.latitude,",",request.longitude,")")
    
    initial_state = {
        "infos": request.message,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "final_target": [],
        "messages": full_conversation,
        "detected_city": request.city,
    }

    #print("Initial_State envoyé au graph : ", initial_state)

    try:
        # Graph Call
        result = graph.invoke(initial_state)
        
        # Get Results from the graph response
        reply = result.get("chat_reply") or result.get("vulgarisation_output") or "Pas de réponse générée."
        targets = result.get("final_target", [])
        latitude = result.get("latitude")
        longitude = result.get("longitude")
        observation_time_utc = result.get("observation_time_utc")
        detected_city = result.get("detected_city")
        constellations = result.get("constellations_target")
        timezone_name = result.get("timezone")
        local_hour = observation_time_utc.astimezone(ZoneInfo(timezone_name))

        print("Résultats données par le graph: \n Ville detectée = ", detected_city, "(",latitude,",",longitude,") \n Heure Locale : ", local_hour, "\n Heure UTC : ", observation_time_utc)

        # Return result to the front-end
        return {
            "reply": reply,
            "targets": targets,
            "latitude": latitude,
            "longitude": longitude,
            "observation_time_utc": observation_time_utc.isoformat().replace("+00:00", "Z"),
            "observation_time_local": local_hour.isoformat(),
            "timezone": timezone_name,
            "detected_city": detected_city,
            "constellations": constellations
        }
        

    except Exception as e:
        print(f"🔥 Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))