import json
import os
import sqlite3
from typing import Annotated, Any, Dict, List
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from IPython.display import Image, display
from langchain_community.utilities import SQLDatabase
from astropy_function import get_ra_dec_constraint, maths_altitude
import re
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import AIMessage

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class AgentState(TypedDict):
    city: str   # "Lyon", "Paris"
    hour: str   # "2025-12-30 17:29:45.285278"
    intent: str  # "Observation", "education"
    infos: str  # "Whats the best nebula we can see ?"
    sql_output: str # "M42"
    astropy_status: str     # "Sucess", "Skipped", "NoResult"
    status_debug: str       # "There is no black hole in the base"
    vulgarisation_output: str   # "Blablabla"
    web_json: str       # "JSON :"
    messages: Annotated[list, add_messages]
    final_target: List[Dict[str, Any]]
graph_builder = StateGraph(AgentState)


word_observation = ["observe","observation", "voir", "montre", "montres", "trouve"]
word_data = ["combien", "lesquelles", "lesquels", "liste", "catalogue", "plus grand", "plus loin"]

KEYWORDS = {
    "observation": ["montr.*", "voi[rt]", "où est", "visib.*", "point.*", "situ.*", "combien", "liste", "quel(s)? est", "plus (grand|loin|brillant)"],
    "education": ["c'est quoi", "expliqu.*", "pourquoi", "raconte", "histoir.*","qu'est ce"]
}

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


def create_sql_tool(db):
    @tool
    def execute_sql(query: str) -> str:
        """
        Exécute une requête SQL SELECT sur la base de données Celestial.
        Prend en entrée une requête SQL valide et renvoie les résultats formatés.
        """
        try:
            # db.run() s'occupe de tout : exécution et formatage en texte
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
tools = [get_ra_dec_constraint, sql_tool]
tool_node = ToolNode(tools)
llm_with_tools = llm_pro.bind_tools(tools)

def print_clean_debug(step_name, message_object):
    """Affiche le contenu du LLM proprement en virant la signature Google."""
    content = message_object.content
    
    print(f"\n--- 🔍 DEBUG {step_name} ---")
    
    # Cas 1 : Gemini renvoie une liste complexe (Text + Signature)
    if isinstance(content, list):
        full_text = ""
        for block in content:
            if isinstance(block, dict) and 'text' in block:
                full_text += block['text']
        print(f"📝 CONTENU : {full_text}")
        
    # Cas 3 : Appel d'outil (Tool Call)
    if hasattr(message_object, 'tool_calls') and message_object.tool_calls:
        for tool in message_object.tool_calls:
            print(f"🛠️ APPEL OUTIL : {tool['name']} avec args={tool['args']}")

    print("-" * 30)

UNIVERSAL_ASTRONOMER_PROMPT = """Tu es un Assistant Astronome Expert connecté à une base de données.

*** TON ENVIRONNEMENT DE DONNÉES ***
1. TABLE UNIQUE : 'Celestial'
2. COLONNES IMPORTANTES : 
   - 'name' (ex: 'M42', 'Andromeda')
   - 'type' (ex: 'Nebula', 'Galaxy', 'Open Cluster')
   - 'constellation' (ex: 'Orion', 'Lyra')
   - 'ra' (Right Ascension, 0-360 degrés)
   - 'dec' (Declination, -90 à +90 degrés)
   - 'magnitude' (Luminosité : plus petit = plus brillant. À l'œil nu < 6)
   - 'catalogue' ('Messier' ou 'Caldwell')

*** TA MÉTHODOLOGIE (DYNAMIQUE) ***
Etape 1 : Analyse la demande.
Etape 2 : Appelle TOUJOURS 'get_ra_dec_constraint' pour connaître le ciel visible à {city} et l'heure {hour}.
Etape 3 : Adapte ta stratégie SQL selon le cas :

--- STRATÉGIE A : VISIBILITÉ D'UN OBJET PRÉCIS ---
(Ex: "Est-ce que M8 est visible ?")
-> Récupère l'intervalle RA de l'outil 1.
-> SQL : SELECT * FROM Celestial WHERE name = 'M8' AND [Intervalle RA] AND [Constraint Dec]

--- STRATÉGIE B : RECOMMANDATION / DÉCOUVERTE ---
(Ex: "Que puis-je voir de beau ce soir ?", "Les plus belles nébuleuses visibles")
-> Récupère l'intervalle RA de l'outil 1.
Utilise l'outil execute_sql. Pour l'argument query, construis une requête SQL valide 
en combinant strictement la contrainte sql_where fournie par l'outil de calcul et tes propres filtres (magnitude, type).

--- STRATÉGIE C : CATALOGUE / INFORMATIONS ---
(Ex: "Quels objets sont dans Orion ?", "Donne la liste des galaxies")
-> Ici, la visibilité n'est pas forcément le critère principal, sauf si précisé.
-> SQL : SELECT * FROM Celestial WHERE constellation = 'Orion' (Pas besoin de contrainte RA si on ne demande pas si c'est visible maintenant).

*** RÈGLE D'OR ***
- Ne parle PAS avant d'avoir interrogé le SQL.
- Si le SQL est vide et qu'il est question de visibilité sur les objets Messier/Caldwell, l'objet est pas visible.
- Si le type n'est pas exigé par l'utilisateur inutile de filtrer dessus 

CONSIGNE DE SORTIE FINALE :
Lorsque tu as trouvé les informations :
1. N'utilise PLUS d'outils.
2. Ta réponse DOIT être un JSON valide, sans balises markdown (pas de ```json), sous cette forme exacte :

  "chat_reply": "Ta réponse ici ...",
  "targets": [
    "label": "Nom Objet", "ra": 123.45, "dec": -12.34
  ]

Si tu n'as pas d'objets à afficher, laisse la liste "targets" vide.

*** OBJECTIF ACTUEL DE L'UTILISATEUR ***
"{mission}"
"""

VULGARISATION_PROMPT = """ Tu es un agent vulgarisateur d'astronomie ayant des infos vérifiés
sur les objets Messier/Caldwell, Vulgarise ces données astronomiques pour un débutant en étant très concis sur ce texte 
(5 phrase maximales) : {last_message} """

def orchestrateur(state = AgentState):
    infos = state.get("infos")
    query = infos.lower()
    print("orchestrateur: Message recu -> ", query)

    for word in KEYWORDS["observation"]:
        if re.search(word, query):
            print("observation")
            return {"intent": "observation"}
    for word in KEYWORDS["education"]:
        if re.search(word, query):
            print("education")
            return {"intent": "education"}


def astronomer(state = AgentState):

    history = state.get("messages", [])

    system_message = {
        "role": "system",
        "content": UNIVERSAL_ASTRONOMER_PROMPT.format(
            schema=schema_brut,
            city=state.get("city"),
            hour=state.get("hour"),
            mission=state.get("infos")
        )
    }
    final_message = [system_message] + history

    res = llm_with_tools.invoke(final_message)
    raw_content = res.content
    
    #----------- PARSING JSON ------------#
    if isinstance(raw_content, list):
        raw_content = "".join([block["text"] for block in raw_content if block.get("type") == "text"])

    clean_text = raw_content.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(clean_text)

        final_target = data.get("targets", [])
        chat_reply = data.get("chat_reply", "Voici les résultats.")

        final_msg = AIMessage(content=chat_reply)

        return {
            "messages": [final_msg], 
            "final_target": final_target
        }

    except json.JSONDecodeError:
        return {
            "messages": [res], 
            "final_target": []
        }



def vulgarisation(state = AgentState):
    last_message = state["messages"][-1].content

    print(state.get('final_target'))

    prompt = VULGARISATION_PROMPT.format(
            last_message=last_message,
        )

    res = llm_lite.invoke(prompt)

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

user_input = "Y'a combien de Constellations, d'objets Caldwell & Messier ? Que puis-je voir ce soir ? "
user_city = "Tokyo"
user_time = "2025-12-31 06:50:00"


initial_state = {
    "infos": user_input,   
    "city": user_city,
    "hour": user_time, 
    "messages": [("user", user_input)] 
}

for event in graph.stream(initial_state):
    for node_name, value in event.items():
        if value is None:
            print(f"⚠️ Le nœud {node_name} n'a rien renvoyé.")
            continue

        if "vulgarisation_output" in value:
            print("Assistant (Texte):", value["vulgarisation_output"])
        
        if "web_json" in value:
            print("Assistant (JSON):", value["web_json"])

