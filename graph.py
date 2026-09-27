from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Annotated, Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, Table, create_engine, event, or_, select, text
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from astropy_function import (
    get_celestial_constraint,
    maths_altitude,
    resolve_city_to_coords_and_tz,
    get_visible_solar_system_objects,
)
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode, tools_condition
from prompts import ORCHESTRATOR_PROMPT, UNIVERSAL_ASTRONOMER_PROMPT, VULGARISATION_PROMPT
from time_utils import (
    TimeRequest,
    default_time_request,
    resolve_time_request,
)

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class AgentState(TypedDict):
    city: str   # "Lyon", "Paris"
    time_request: Optional[TimeRequest]
    observation_time_utc: datetime
    intent: str  # "Observation", "education"
    infos: str  # "Whats the best nebula we can see ?"
    vulgarisation_output: str   # "Here is what you can see"
    chat_reply: str
    messages: Annotated[list, add_messages] # Historique des messages
    final_target: List[Dict[str, Any]] # JSON OBJETS TROUVES
    detected_city: Optional[str] = Field(description="Nom de la ville demandée par l'user, si différente de l'actuelle.")
    latitude: float
    longitude: float
    sql_where: Dict[str, Any]
    planets: Dict[str, Any]
    timezone: str
    constellations_target: List[str]
graph_builder = StateGraph(AgentState)

llm_pro = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        google_api_key=GOOGLE_API_KEY,
        temperature=0
)
llm_lite = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        google_api_key=GOOGLE_API_KEY,
        temperature=0
)

class RoutingAndExtraction(BaseModel):
    intent: str     #"observation" ou "education"
    city: Optional[str] = Field(None)     
    time: TimeRequest | None = None
    mission: Optional[str]

ALLOWED_TARGET_FILTER_KEYS = {
    "name",
    "type",
    "constellation",
    "catalogue",
    "magnitude_min",
    "magnitude_max",
    "ra_min",
    "ra_max",
    "dec_min",
    "dec_max",
    "limit",
}
MAX_TARGET_LIMIT = 50
ACTIVE_VISIBILITY_SQL = ""


def set_active_visibility_sql(sql_expression: Optional[str]) -> None:
    global ACTIVE_VISIBILITY_SQL
    ACTIVE_VISIBILITY_SQL = sql_expression.strip() if sql_expression else ""


class TargetFilters(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    constellation: Optional[str] = None
    catalogue: Optional[str] = None
    magnitude_min: Optional[float] = Field(default=None, ge=0.0)
    magnitude_max: Optional[float] = Field(default=None, ge=0.0)
    ra_min: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    ra_max: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    dec_min: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    dec_max: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    limit: int = Field(default=8, ge=1, le=MAX_TARGET_LIMIT)


def validate_target_filters(filters_json: Any) -> Dict[str, Any]:
    if filters_json is None:
        return {"limit": 8}

    if not isinstance(filters_json, dict):
        raise ValueError("filters_json must be a dictionary, not raw SQL text.")

    unknown = set(filters_json.keys()) - ALLOWED_TARGET_FILTER_KEYS
    if unknown:
        raise ValueError(
            f"Unknown target filter(s): {sorted(unknown)}. "
            f"Allowed keys: {sorted(ALLOWED_TARGET_FILTER_KEYS)}"
        )

    prohibited_sql = {"query", "sql", "raw_sql", "statement", "command"}
    if prohibited_sql.intersection(filters_json):
        raise ValueError("Raw SQL payloads are forbidden. Send validated filters only.")

    for key, value in filters_json.items():
        if isinstance(value, str):
            lowered = value.lower()
            if any(token in lowered for token in ["select", "insert", "update", "delete", "drop", "alter", "truncate", "union", "--", ";"]):
                raise ValueError("String values must not contain raw SQL clauses or separators.")
            if any(keyword in lowered for keyword in ["from ", "where ", "join ", "order by", "group by"]):
                raise ValueError("String values must not look like SQL fragments.")

    cleaned = TargetFilters.model_validate(filters_json).model_dump(exclude_none=True)
    if cleaned.get("limit", 8) > MAX_TARGET_LIMIT:
        raise ValueError(f"limit must be <= {MAX_TARGET_LIMIT}")
    return cleaned


def build_targets_query(filters: Dict[str, Any], engine, visibility_sql: Optional[str] = None):
    metadata = MetaData()
    celestial = Table("Celestial", metadata, autoload_with=engine)
    conditions = []
    ra_min = filters.get("ra_min")
    ra_max = filters.get("ra_max")

    for field, value in filters.items():
        if field == "limit":
            continue

        if field in {"ra_min", "ra_max", "dec_min", "dec_max"}:
            continue

        column = getattr(celestial.c, field, None)
        if column is None:
            raise ValueError(f"Unsupported filter field: {field}")

        if field in {"name", "type", "constellation", "catalogue"}:
            conditions.append(column.ilike(f"%{value}%"))
        elif field == "magnitude_min":
            conditions.append(column >= value)
        elif field == "magnitude_max":
            conditions.append(column <= value)

    if ra_min is not None and ra_max is not None and ra_min > ra_max:
        conditions.append(or_(celestial.c.ra >= ra_min, celestial.c.ra <= ra_max))
    else:
        if ra_min is not None:
            conditions.append(celestial.c.ra >= ra_min)
        if ra_max is not None:
            conditions.append(celestial.c.ra <= ra_max)

    if filters.get("dec_min") is not None:
        conditions.append(celestial.c.dec >= filters["dec_min"])
    if filters.get("dec_max") is not None:
        conditions.append(celestial.c.dec <= filters["dec_max"])

    if visibility_sql:
        visibility_sql = visibility_sql.strip()
        if not visibility_sql.endswith("= 1") and not visibility_sql.endswith("=1"):
            visibility_sql = f"({visibility_sql}) = 1"
        conditions.append(text(visibility_sql))

    stmt = select(celestial).where(*conditions).limit(filters.get("limit", 8))
    return stmt


@tool
def search_targets(filters_json: dict) -> str:
    """
    Search the Celestial catalog using validated server-side filters only.
    The model must pass a dict with allowed keys like name/type/constellation/limit.
    No raw SQL strings or SQL clauses are allowed.
    """
    try:
        cleaned_filters = validate_target_filters(filters_json)
        query = build_targets_query(cleaned_filters, engine, ACTIVE_VISIBILITY_SQL)
        with engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return json.dumps([dict(row) for row in rows])
    except Exception as exc:  # pragma: no cover - defensive guard
        return json.dumps({"error": str(exc)})


def run_tools(state):
    try:
        return tool_node.invoke(state)
    finally:
        set_active_visibility_sql("")


def _register_custom_functions(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function("IS_VISIBLE", 5, maths_altitude)

engine = create_engine("sqlite:///Celestial.db")

event.listen(engine, 'connect', _register_custom_functions)

db = SQLDatabase(engine)


schema_brut = db.run("PRAGMA table_info(Celestial);")

tools = [search_targets]
tool_node = ToolNode(tools)
llm_with_tools = llm_pro.bind_tools(tools)

def extract_text_from_content(content: Any) -> str:
    """Normalize Gemini content payloads into a plain text string."""
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks: List[str] = []
        for block in content:
            if isinstance(block, dict):
                if "text" in block and isinstance(block["text"], str):
                    chunks.append(block["text"])
                elif "value" in block and isinstance(block["value"], str):
                    chunks.append(block["value"])
                elif "content" in block and isinstance(block["content"], str):
                    chunks.append(block["content"])
            elif isinstance(block, str):
                chunks.append(block)
        return "".join(chunks)

    if isinstance(content, dict):
        for key in ("text", "value", "content"):
            if isinstance(content.get(key), str):
                return content[key]
        return json.dumps(content, ensure_ascii=False)

    return str(content)


def print_clean_debug(step_name, message_object):
    """Affiche le contenu du LLM proprement en virant la signature Google."""
    content = message_object.content
    
    print(f"\n--- DEBUG {step_name} ---")
    print(f" CONTENU : {extract_text_from_content(content)}")
    
    if hasattr(message_object, 'tool_calls') and message_object.tool_calls:
        for tool in message_object.tool_calls:
            print(f" APPEL OUTIL : {tool['name']} avec args={tool['args']}")

    print("-" * 30)

def orchestrateur(state = AgentState):
    print("--------- Entrée Orchestrateur ---------")
    structured_llm = llm_pro.with_structured_output(RoutingAndExtraction)

    history = state.get("messages", [])

    now_utc = datetime.now(timezone.utc)
    city = state.get("detected_city")

    system_msg = {
        "role": "system",
        "content": ORCHESTRATOR_PROMPT.format(
            current_time_str=now_utc.isoformat(),
            current_day_str=now_utc.astimezone().strftime("%A %d %B %Y"),
            city=city or "inconnue",
            now=now_utc,
        ),
    }

    final_message = [system_msg] + history
    res = structured_llm.invoke(final_message)
    print(f"[TIME] TimeRequest renvoyé par le LLM : {res.time!r}")
    
    final_city = (res.city or "").strip()
    if final_city.lower() in {"", "none", "null"}:
        final_city = state.get("detected_city") or "Paris"
    coords, timezone_name = resolve_city_to_coords_and_tz(final_city)
    latitude, longitude = coords
    final_mission = res.mission

    print("Timezone =", timezone_name)
    time_request = res.time

    if time_request is None:
        time_request = state.get("time_request")

    if time_request is None:
        time_request = default_time_request()

    observation_time_utc = resolve_time_request(time_request, timezone_name, now_utc)
    target_local = observation_time_utc.astimezone(ZoneInfo(timezone_name))
    print("- Valeur gardée et envoyée à l'astronomer\n Intent :", res.intent,
          "\n Mission :", final_mission, "\n Ville :", final_city,
          "\n Heure locale :", target_local, "\n Heure UTC :", observation_time_utc)
    constraint = get_celestial_constraint(latitude, longitude, observation_time_utc)
    planets = get_visible_solar_system_objects(latitude, longitude, observation_time_utc)
    print("- Valeur de calcul stockée : \n Erreur_Soleil: ", constraint.get("error"), " \n Planetes visibles : ", [obj['name'] for obj in planets.get("observables")], "\n ----------------------------------------") 

    return {"intent": res.intent,
            "detected_city": final_city,
            "time_request": time_request,
            "observation_time_utc": observation_time_utc,
            "latitude": latitude,
            "longitude": longitude,
            "sql_where": constraint,
            "planets": planets,
            "timezone" : timezone_name,
            "infos": final_mission,} 

def astronomer(state = AgentState):
    print("--------- Entrée Astronomer ---------")
    mission_finale = state.get("infos")

    system_message = SystemMessage(content=UNIVERSAL_ASTRONOMER_PROMPT.format(
        schema=schema_brut,
        city=state.get("detected_city"),
        hour=state.get("observation_time_utc"),
        mission=mission_finale,
        sql_where=state.get("sql_where"),
        sun_error=state.get("sql_where", {}).get("error", ""),
        planets=state.get("planets")
    ))
    human_instruction = HumanMessage(content=f"Instruction : {mission_finale}")

    working_memory = []
    all_messages = state.get("messages", [])
    
    for msg in all_messages:
        if isinstance(msg, ToolMessage):
            working_memory.append(msg)
        elif isinstance(msg, AIMessage) and msg.tool_calls:
            working_memory.append(msg)
    
    final_message = [system_message, human_instruction] + working_memory

    set_active_visibility_sql(state.get("sql_where", {}).get("sql_where") or "")
    try:
        res = llm_with_tools.invoke(final_message)
    except Exception:
        set_active_visibility_sql("")
        raise

    if not res.tool_calls:
        set_active_visibility_sql("")
    print_clean_debug("Astro", res)

    raw_content = extract_text_from_content(res.content)
    clean_text = raw_content.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(clean_text)

        final_target = data.get("targets", [])
        chat_reply = data.get("chat_reply", "Voici les résultats.")
        constellations_target = data.get("constellations_IAU")
    
        final_msg = AIMessage(content=chat_reply)
        
        return {
            "messages": [final_msg], 
            "chat_reply": chat_reply,
            "final_target": final_target,
            "constellations_target": constellations_target
        }

    except json.JSONDecodeError:
        return {
            "messages": [res], 
            "chat_reply": extract_text_from_content(res.content),
            "final_target": [],
            "constellations_target": []
        }

def vulgarisation(state = AgentState):
    print("--------- Entrée Vulgarisateur ---------")

    prompt = VULGARISATION_PROMPT.format(
        mission=state.get("infos") or "Question d'astronomie générale",
        city=state.get("detected_city") or "inconnue",
        timezone=state.get("timezone") or "UTC",
        observation_time_utc=state.get("observation_time_utc") or "inconnu",
        sun_error=state.get("sql_where", {}).get("error", "aucune contrainte"),
        planets=state.get("planets") or {"observables": []},
    )

    res = llm_lite.invoke(prompt)
    print(res)

    return {"vulgarisation_output": extract_text_from_content(res.content)}


def orchestr_switch(state = AgentState):
    if state.get("intent") == "education":
        return "vulgaris"
    else:
        return "astronome"

dict_ = {'astronome':'astro', 'vulgaris':'vulga'}

graph_builder.add_node("orchest", orchestrateur)
graph_builder.add_node("astro", astronomer)
graph_builder.add_node("tools", run_tools)
graph_builder.add_node("vulga", vulgarisation)

graph_builder.set_entry_point("orchest")
graph_builder.add_conditional_edges("orchest", orchestr_switch, {"astronome": "astro", "vulgaris": "vulga"})
graph_builder.add_conditional_edges("astro", tools_condition, {"tools": "tools", "__end__": "vulga"})

graph_builder.add_edge("tools", "astro")
graph_builder.set_finish_point("vulga")

graph = graph_builder.compile()


