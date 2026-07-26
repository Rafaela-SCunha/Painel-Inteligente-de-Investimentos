import os
#from dotenv import load_dotenv
import streamlit as st
from supabase import create_client, Client

# Carrega as variáveis contidas no arquivo .env para a memória do sistema
#load_dotenv()

#URL = os.getenv("SUPABASE_URL")
#KEY = os.getenv("SUPABASE_KEY")

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except (FileNotFoundError, KeyError):
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Erro crítico: As variáveis SUPABASE_URL e SUPABASE_KEY não foram encontradas!")


# Cria o cliente global que todo o projeto vai usar
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)