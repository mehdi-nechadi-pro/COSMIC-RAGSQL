from typing import Any, Dict, List
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
    hour: str 
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

    print("Données par le front-end : \n Prompt : ", request.message,"\n Ville :", request.city, "(",request.latitude,",",request.longitude,") \n Heure :", request.hour)
    
    initial_state = {
        "infos": request.message,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "hour": request.hour,
        "final_target": [],
        "messages": full_conversation,
        "detected_city": request.city,
    }

    #print("Initial_State envoyé au graph : ", initial_state)

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
        constellations = result.get("constellations_target")
        local_hour = result.get("local_hour")

        print("Résultats données par le graph: \n Ville detectée = ", detected_city, "(",latitude,",",longitude,") \n Heure Locale : ", local_hour, "\n Heure UTC : ", hour)

        # Return result to the front-end
        return {
            "reply": reply,
            "targets": targets,
            "latitude": latitude,
            "longitude": longitude,
            "hour": local_hour,
            "local_hour": local_hour,
            "detected_city": detected_city,
            "constellations": constellations
        }
        

    except Exception as e:
        print(f"🔥 Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))