from datetime import datetime
import json
import locale
import os
import sqlite3
from typing import Annotated, Any, Dict, List, Optional
from dotenv import load_dotenv
from pydantic import Field, BaseModel
from sqlalchemy import create_engine, event
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from astropy_function import get_ra_dec_constraint, get_target_utc_date, maths_altitude, get_coordinates, get_visible_solar_system_objects
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import AIMessage
from prompts import UNIVERSAL_ASTRONOMER_PROMPT, VULGARISATION_PROMPT

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class AgentState(TypedDict):
    city: str   # "Lyon", "Paris"
    hour: str   # "2025-12-30 17:29:45.285278"
    intent: str  # "Observation", "education"
    infos: str  # "Whats the best nebula we can see ?"
    vulgarisation_output: str   # "Blablabla"
    messages: Annotated[list, add_messages] # LISTE DES MESSAGES
    final_target: List[Dict[str, Any]] # JSON OBJETS TROUVES
    detected_city: Optional[str] = Field(description="Nom de la ville demandée par l'user, si différente de l'actuelle.")
    latitude: float
    longitude: float
    sql_where: str
    planets: str
    timezone: str
    constellations_target: List[str]
graph_builder = StateGraph(AgentState)

llm_pro = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0
)
llm_lite = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=GOOGLE_API_KEY,
        temperature=0
)

class RoutingAndExtraction(BaseModel):
    intent: str     #"observation" ou "education"
    city: Optional[str] = Field(None)     
    hour: Optional[str] = Field(None) 

def update_if_valid(current_val, new_val):
    bad_values = ["null", "Null", "None", "", None]
    print("APPEL UPDATE -- current=", current_val, " new=", new_val)
    if new_val in bad_values:
        return current_val
    return new_val

def create_sql_tool(db):
    @tool
    def execute_sql(query: str) -> str:
        """
        Exécute une requête SQL SELECT sur la base de données Celestial.
        Prend en entrée une requête SQL valide et renvoie les résultats formatés.
        """
        try:
            return db.run(query)
        except Exception as e:
            return f"Erreur lors de l'exécution SQL : {e}"
            
    return execute_sql


def _register_custom_functions(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("IS_VISIBLE", 5, maths_altitude)

engine = create_engine("sqlite:///Celestial.db")

event.listen(engine, 'connect', _register_custom_functions)

db = SQLDatabase(engine)


schema_brut = db.run("PRAGMA table_info(Celestial);")

sql_tool = create_sql_tool(db)
tools = [sql_tool]
tool_node = ToolNode(tools)
llm_with_tools = llm_pro.bind_tools(tools)

def print_clean_debug(step_name, message_object):
    """Affiche le contenu du LLM proprement en virant la signature Google."""
    content = message_object.content
    
    print(f"\n--- 🔍 DEBUG {step_name} ---")
    
    if isinstance(content, list):
        full_text = ""
        for block in content:
            if isinstance(block, dict) and 'text' in block:
                full_text += block['text']
        print(f"📝 CONTENU : {full_text}")
        
    if hasattr(message_object, 'tool_calls') and message_object.tool_calls:
        for tool in message_object.tool_calls:
            print(f"🛠️ APPEL OUTIL : {tool['name']} avec args={tool['args']}")

    print("-" * 30)

def orchestrateur(state = AgentState):

    structured_llm = llm_lite.with_structured_output(RoutingAndExtraction)

    history = state.get("messages", [])
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8') 
    except:
        pass
    now = datetime.now()

    current_time_str = now.strftime("%Y-%m-%d %H:%M:%S") 
    current_day_str = now.strftime("%A %d %B %Y")
    city = state.get("detected_city")

    system_msg = {
        "role": "system", 
        "content": f"""
--- CONTEXTE TEMPOREL CRITIQUE ---
Date et Heure Système Actuelles : {current_time_str}
Nous sommes le : {current_day_str}
Ville actuellement connue par le système : {city}
----------------------------------
RÈGLE ABSOLUE : Utilise cette date comme référence unique pour "aujourd'hui", "ce soir", "demain".
MODIFIE LA VILLE UNIQUEMENT si elle est donnée dans le prompt
NE DEVINE PAS L'ANNÉE. L'année est {now.year}.
NE TOUCHES PAS AUX FUSEAUX HORAIRES, l'utilisateur demande 18h -> tu renvoies 18h
----------------------------------
Tu es un extracteur astronome.
Extrais l'intention ("observation" ou "education").
Extrais l'heure et le lieu SI ils sont donnés.
INTERDICTION D'HALLUCINER, si une ou plusieurs des valeurs sont non trouvés RENVOIE RIEN
SI C'EST de le déduire alors déduis l'heure (matin -> 6h, soir -> 20h) SOUS CE FORMAT: "2050-01-01T22:53:00" en LOCAL, AUCUNE CONVERSION AUTORISEE
Sinon renvoie rien. """
}

    final_message = [system_msg] + history
    res = structured_llm.invoke(final_message)

    print("Données de la réponse LLM :", res.intent, " Ville ? ", res.city, " Heure ? ", res.hour)

    # ALL datas are available for the computation 
    final_city = update_if_valid(state.get("detected_city"),res.city)
    final_hour = update_if_valid(state.get("hour"),res.hour)
    coords, timezone = get_coordinates(final_city)
    latitude,longitude = coords
    final_utc = get_target_utc_date(timezone, final_hour)

    # print("Valeur gardé et envoyé à l'astronomer : ",final_city, " ", final_hour, "utc : ", final_utc)

    constraint = get_ra_dec_constraint(latitude, longitude, final_utc)
    planets = get_visible_solar_system_objects(latitude, longitude, final_utc)

    # print("Contrainte stockée dans sql_where : ", constraint)

    return {"intent": res.intent,
            "detected_city": final_city,
            "hour": final_utc,
            "latitude": latitude,
            "longitude": longitude,
            "sql_where": constraint,
            "planets": planets,
            "timezone" : timezone}

def astronomer(state = AgentState):
    # print("Données entrée Astronomer : Heure=",state.get("hour"), " Ville=", 
    state.get("detected_city"), " lat/lon= (", state.get("latitude"), ",", state.get("longitude"), ")"
    history = state.get("messages", [])

    system_message = {
        "role": "system",
        "content": UNIVERSAL_ASTRONOMER_PROMPT.format(
            schema=schema_brut,
            city=state.get("detected_city"),
            hour=state.get("hour"),
            mission=state.get("infos"),
            sql_where = state.get("sql_where"),
            planets= state.get("planets")
        )
    }
    final_message = [system_message] + history

    res = llm_with_tools.invoke(final_message)
    print_clean_debug("Astro", res)
    raw_content = res.content
    
    #----------- PARSING JSON ------------#
    if isinstance(raw_content, list):
        raw_content = "".join([block["text"] for block in raw_content if block.get("type") == "text"])

    clean_text = raw_content.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(clean_text)

        final_target = data.get("targets", [])
        chat_reply = data.get("chat_reply", "Voici les résultats.")
        constellations_target = data.get("constellations_IAU")
    
        final_msg = AIMessage(content=chat_reply)
        
        return {
            "messages": [final_msg], 
            "final_target": final_target,
            "constellations_target": constellations_target
        }

    except json.JSONDecodeError:
        return {
            "messages": [res], 
            "final_target": [],
            "constellations_target": []
        }

def vulgarisation(state = AgentState):
    last_message = state["messages"][-1].content

    prompt = VULGARISATION_PROMPT.format(
            last_message=last_message,
        )

    res = llm_lite.invoke(prompt)

    # print("Données dans vulga : Heure=",state.get("hour"), " Ville=", 
    state.get("detected_city"), " lat/lon= (", state.get("latitude"), ",", state.get("longitude")
    return {"vulgarisation_output": res.content}


def orchestr_switch(state = AgentState):
    if state.get("intent") == "education":
        return "vulgaris"
    else:
        return "astronome"

dict_ = {'astronome':'astro', 'vulgaris':'vulga'}

graph_builder.add_node("orchest", orchestrateur)
graph_builder.add_node("astro", astronomer)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("vulga", vulgarisation)

graph_builder.set_entry_point("orchest")
graph_builder.add_conditional_edges("orchest", orchestr_switch, {"astronome": "astro", "vulgaris": "vulga"})
graph_builder.add_conditional_edges("astro", tools_condition, {"tools": "tools", "__end__": "vulga"})

graph_builder.add_edge("tools", "astro")
graph_builder.set_finish_point("vulga")

graph = graph_builder.compile()