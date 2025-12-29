import streamlit as st
import os
from dotenv import load_dotenv
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain.tools import tool
from langchain_community.callbacks import StreamlitCallbackHandler

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

st.set_page_config(
    page_title="AstroSQL",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("<h1 style='text-align: center; color: grey;'>AstroSQL Agent</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 0.8em; color: #444;'>Interface Base de Données Céleste</p>", unsafe_allow_html=True)

@st.cache_resource
def initialize_agent():
    if not GOOGLE_API_KEY:
        st.error("Clé API manquante dans le fichier .env")
        st.stop()

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=GOOGLE_API_KEY,
        temperature=0
    )
    db = SQLDatabase.from_uri("sqlite:///Celestial.db", sample_rows_in_table_info=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    @tool
    def check_table_columns(table: str) -> str:
        """Useful to get the column names using PRAGMA."""
        clean_table = table.strip("'").strip('"')
        return db.run(f"PRAGMA table_info({clean_table});")

    @tool
    def get_sample_rows(table: str) -> str:
        """Get 3 sample rows to inspect data format."""
        return db.run(f"SELECT * FROM {table} LIMIT 3;")

    @tool
    def check_column_values(input_str: str) -> str:
        """
        INPUT FORMAT: "table_name, column_name"
        """
        try:
            parts = input_str.split(",")
            if len(parts) < 2: return "Error: Input must be 'table, column'"
            table = parts[0].strip().strip("'").strip('"')
            column = parts[1].strip().strip("'").strip('"')
            if table not in db.get_usable_table_names(): return f"Error: Table {table} does not exist."
            return db.run(f"SELECT DISTINCT {column} FROM {table} LIMIT 20;")
        except Exception as e: return f"Error inspecting values: {e}"
        

    # A CHANGER je veux classer l'info : infos générales -> tu réponds,  et demande d'observation -> tu appel le check_visibility qui va transformer la ville en Coordonnée (via une fonction qui utilisera la lib geopy) et faire le calcul de contrainte ra/dec min et max
    # cette contrainte est envoyé 

    prompt = f"""You are an space sql agent, your goal is to give useful enrich informations 
to the user based on your knowledge and the {db.dialect} query you can execute on the database.BEFORE writing ANY SQL query:

CRITICAL WARNING: 
The standard 'sql_db_schema' tool is BROKEN for this database and returns empty results "()".

MANDATORY STRATEGY:
1. ALWAYS CALL sql_db_list_tables and dont invent table
2. ALWAYS CALL check_table_columns on the relevant table AND DO NOT TRUST sql_db_schema
3. ALWAYS call get_sample_rows to inspect example values if the names you saw is not on the column/table (
4. ALWAYS Inspect the differents values for each column using check_column_values 

BEFORE any filtering:
- CALL check_column_values(<column>) to retrieve ALL distinct values.
- STORE these values in memory/context.
- USE ONLY these values in WHERE clauses.
- NEVER omit a value unless the user explicitly excludes it.

DONT EVER INCLUDE NONE VALUES OR NON-SPECIFIED VALUES For the values that the user asked
WHENEVER there is None Values Return, Create another query
5. ALWAYS call sql_db_query_checker before sql_db_query.
6. NEVER CREATE/DELETE/UPDATE a table. 
DONT USE "Create table".
If the table you saw dont exists, CALL sql_db_list_table and look at the others table
NEVER INCLUDE non-specified or None values into the query/result even if its mean to create another query

ALWAYS USE YOUR KNOWLEDGE for the details : NOT EVERYTHING IS ON THE DATABASE
FOR EVERY Objects you return ALWAYS return Object and the URL


Question: {{input}}
Agent Scratchpad: {{agent_scratchpad}}
"""

    agent_executor = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=False, 
        agent_type="zero-shot-react-description",
        extra_tools=[check_table_columns, get_sample_rows, check_column_values],
        suffix=prompt,
        handle_parsing_errors=True
    )
    return agent_executor

try:
    agent = initialize_agent()
except Exception as e:
    st.error(f"Erreur critique au chargement de l'agent : {e}")
    st.stop()


# --- GESTION DE L'INTERFACE DE CHAT ---

# Initialisation de l'historique si c'est le premier lancement
if "messages" not in st.session_state:
    st.session_state.messages = []

# Affichage des anciens messages de la session
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ZONE DE SAISIE DU PROMPT (Le bas de page)
# ... (le code d'avant ne change pas)

# 7. ZONE DE SAISIE
if prompt := st.chat_input("Ex: Nébuleuses les plus brillantes..."):
    
    # Affichage du message utilisateur
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Réponse de l'Assistant
    with st.chat_message("assistant"):
        # CRUCIAL : On crée le conteneur pour le callback
        st_callback = StreamlitCallbackHandler(st.container())
        
        try:
            response = agent.invoke(
                {"input": prompt}, 
                {"callbacks": [st_callback]} 
            )
            
            output = response['output']
            
            raw_links = re.findall(r'(https?://[^\s\)]+)', output)
            
            clean_links = []
            for link in raw_links:
                clean = link.rstrip(".,;)\"'").split('\n')[0]
                
                if clean.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    clean_links.append(clean)
            
            unique_links = list(set(clean_links))
            print(unique_links)

            if unique_links:
                col1, col2 = st.columns([6, 4])
                
                with col1:
                    st.markdown(output)
                
                with col2:
                    st.markdown("### 📸 Aperçus")
                    for img_url in unique_links:
                        try:
                            st.image(img_url, width=250) # use_container_width remplace use_column_width (déprécié)
                        except:
                            st.caption(f"Image introuvable : {img_url}")

            else:
                st.markdown(output)

            # Sauvegarde dans l'historique
            st.session_state.messages.append({"role": "assistant", "content": output})
            
        except Exception as e:
            st.error(f"Erreur d'exécution: {e}")