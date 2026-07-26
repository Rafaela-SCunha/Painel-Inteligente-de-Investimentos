import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis contidas no arquivo .env para a memória do sistema
load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_KEY")

if not URL or not KEY:
    raise ValueError("Erro crítico: As variáveis SUPABASE_URL e SUPABASE_KEY não foram encontradas no arquivo .env!")

# Cria o cliente global que todo o projeto vai usar
supabase: Client = create_client(URL, KEY)