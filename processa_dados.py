import pandas as pd
import numpy as np
import re
from features import gerar_features
from conexao_supabase import supabase


# =================================================
# 0. MAPA DE ESPECIALISTAS SETORIAIS
# =================================================
# Este dicionário diz exatamente quais indicadores importam para cada ativo.
# Qualquer indicador que não estiver na lista será sumariamente ignorado pela IA.
MAPA_SETORIAL = {
    # --- SETOR DE ENERGIA (Petróleo) ---
    "PETR4.SA": ["bz", "usdbrl", "bvsp"],
    "PRIO3.SA": ["bz", "usdbrl", "bvsp"],
    
    # --- SETOR DE MATERIAIS BÁSICOS (Mineração/Siderurgia) ---
    "VALE3.SA": ["tio", "usdbrl", "bvsp"],
    "GGBR4.SA": ["tio", "usdbrl", "bvsp"],
    "CSNA3.SA": ["tio", "usdbrl", "bvsp"],
    
    # --- SETOR FINANCEIRO (Bancos) ---
    # OBS: Usaremos o BOVA11 como proxy da força financeira/juros
    "ITUB4.SA": ["bvsp", "usdbrl", "bova11"], 
    "BBDC4.SA": ["bvsp", "usdbrl", "bova11"],
    "BBAS3.SA": ["bvsp", "usdbrl", "bova11"],
}

# =================================================
# 0.1 FUNÇÃO AUXILIAR DE PADRONIZAÇÃO DE NOMES
# =================================================
def limpar_nome_indicador(ticker):
    """
    Padroniza qualquer ticker estranho do Yahoo para um prefixo limpo.
    Ex: '^BVSP' -> 'bvsp' | 'USDBRL=X' -> 'usdbrl' | 'BZ=F' -> 'bz'
    """
    nome_limpo = ticker.lower()
    nome_limpo = re.sub(r'[\^=FX\-]', '', nome_limpo)
    return nome_limpo


# =================================================
# 1. CARREGAMENTO E ALINHAMENTO DE DADOS NO SUPABASE
# =================================================
def carregar_dados(ticker_alvo, modo="treino"):
    print(f"--- Carregando dados para {ticker_alvo} ({modo.upper()}) ---")
    
    res_id = supabase.table("cad_ativos").select("id").eq("ticker", ticker_alvo).execute()
    if not res_id.data:
        print("❌ Ativo não encontrado!")
        return None
    ativo_id = res_id.data[0]['id']

    # --- LÓGICA DE BUSCA DA AÇÃO (PAGINADA) ---
    dados_acao = []
    if modo == "previsao":
        res_precos = supabase.table("precos_diarios").select("data, preco_fechamento, volume")\
            .eq("ativo_id", ativo_id).order("data", desc=True).limit(150).execute()
        dados_acao = res_precos.data
    else:
        offset = 0
        limit = 1000
        while True:
            res_precos = supabase.table("precos_diarios").select("data, preco_fechamento, volume")\
                .eq("ativo_id", ativo_id).order("data", desc=True).range(offset, offset + limit - 1).execute()
            
            dados_acao.extend(res_precos.data)
            if len(res_precos.data) < limit:
                break 
            offset += limit

    if not dados_acao: return None
        
    df = pd.DataFrame(dados_acao)
    print(f"📊 Total de linhas da ação carregadas: {len(df)}")
    
    df['data'] = pd.to_datetime(df['data']).dt.date
    df = df.sort_values('data').set_index('data')

    # Busca e cruza os indicadores vinculados
    vinc_res = supabase.table("ativo_indicador_setorial") \
        .select("indicador_id, cad_indicadores(ticker, nome)") \
        .eq("ticker_ativo", ticker_alvo).execute()

    if vinc_res.data:
        for vinculo in vinc_res.data:
            ind_id = vinculo['indicador_id']
            ind_ticker = vinculo['cad_indicadores']['ticker']
            col_name = limpar_nome_indicador(ind_ticker)

            # --- FILTRO SETORIAL (O LEÃO DE CHÁCARA) ---
            if ticker_alvo in MAPA_SETORIAL:
                if col_name not in MAPA_SETORIAL[ticker_alvo]:
                    continue # Bloqueia o ruído e não carrega essa variável!

            # --- LÓGICA DE BUSCA DOS INDICADORES (PAGINADA) ---
            dados_ind = []
            if modo == "previsao":
                res_ind = supabase.table("precos_indicadores").select("data, preco_fechamento, volume")\
                    .eq("indicador_id", ind_id).order("data", desc=True).limit(150).execute()
                dados_ind = res_ind.data
            else:
                offset_ind = 0
                while True:
                    res_ind = supabase.table("precos_indicadores").select("data, preco_fechamento, volume")\
                        .eq("indicador_id", ind_id).order("data", desc=True).range(offset_ind, offset_ind + limit - 1).execute()
                    
                    dados_ind.extend(res_ind.data)
                    if len(res_ind.data) < limit:
                        break
                    offset_ind += limit
            
            if dados_ind:
                df_ind = pd.DataFrame(dados_ind)
                df_ind['data'] = pd.to_datetime(df_ind['data']).dt.date
                df_ind = df_ind.sort_values('data').set_index('data')

                df[f'setor_{col_name}_close'] = df_ind['preco_fechamento']
                df[f'setor_{col_name}_vol'] = df_ind['volume']

    df = df.ffill().bfill()
    return df


# =================================================
# 2. CAMADA DE INTELIGÊNCIA (FEATURE ENGINEERING)
# =================================================
def calcular_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calcular_indicadores_tecnicos(df):
    df['retorno'] = df['preco_fechamento'].pct_change()
    df['retorno_ontem'] = df['retorno'].shift(1)

    ema_9 = df['preco_fechamento'].ewm(span=9).mean()
    ema_21 = df['preco_fechamento'].ewm(span=21).mean()

    df['dist_ema_9'] = (df['preco_fechamento']/ema_9) - 1
    df['dist_ema_21'] = (df['preco_fechamento']/ema_21) - 1

    df['rsi'] = calcular_rsi(df['preco_fechamento'], 14)
    df['volume_relativo'] = df['volume'] / df['volume'].rolling(20).mean()
    df['volatilidade'] = df['retorno'].rolling(20).std()

    ma20 = df['preco_fechamento'].rolling(window=20).mean()
    std20 = df['preco_fechamento'].rolling(window=20).std()
    df['b_percent'] = (df['preco_fechamento'] - (ma20 - 2 * std20) / (4 * std20))  
    return df

def aplicar_features_setoriais(df):
    for col in [c for c in df.columns if 'setor_' in c and '_close' in c]:
        if any(x in col for x in ['bvsp', 'ifix', 'spx']): continue
        
        prefix = col.replace('setor_', '').replace('_close', '')
        
        retorno_ind_lag = df[col].pct_change().shift(1)
        df[f'retorno_{prefix}_lag'] = retorno_ind_lag
        
        df[f'spread_{prefix}'] = df['preco_fechamento'].pct_change().shift(1) - retorno_ind_lag
        df[f'corr_{prefix}'] = df['preco_fechamento'].pct_change().shift(1).rolling(10).corr(retorno_ind_lag)

    indices = [c for c in df.columns if 'bvsp' in c or 'ifix' in c]
    for idx in indices:
        if '_close' in idx:
            prefix_idx = 'ibov' if 'bvsp' in idx else 'ifix'
            
            retorno_mercado_lag = df[idx].pct_change().shift(1)
            df[f'retorno_{prefix_idx}_lag'] = retorno_mercado_lag
            
            retorno_acao_lag = df['preco_fechamento'].pct_change().shift(1)
            df[f'beta_{prefix_idx}'] = retorno_acao_lag.rolling(20).cov(retorno_mercado_lag) / \
                                      retorno_mercado_lag.rolling(20).var()
    return df


# =================================================
# 3. LIMPEZA FINAL E ORQUESTRAÇÃO
# =================================================
def limpar_dados(df):
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.ffill()
    df = df.dropna()
    return df

def processa_dados_completa(ticker, margem=3.0, modo="treino"):
    df = carregar_dados(ticker, modo=modo)
    if df is None: return None

    # Gerar as features estruturadas a partir de features.py
    df = gerar_features(df)
    
    if modo == "treino":
        # ==========================================
        # REGRAS EXCLUSIVAS DE TREINAMENTO
        # ==========================================
        # 1. Filtro de Volatilidade (Remove dias parados)
        df['volatilidade_filtro'] = df['preco_fechamento'].pct_change().rolling(20).std()
        corte_volatilidade = df['volatilidade_filtro'].quantile(0.25)
        df = df[df['volatilidade_filtro'] > corte_volatilidade]
        
        # 2. Filtro de Ruído (Remove dias de 0x0)
        df = df[df['retorno'].abs() > 0.001]
        
        # 3. Criação do Alvo (O Futuro)
        margem_decimal = margem / 100.0
        df['retorno_3d'] = df['preco_fechamento'].pct_change(3).shift(-3)
        df['target'] = (df['retorno_3d'] >= margem_decimal).astype(int)
        
        # Limpa as sobras do filtro
        df = df.drop(columns=['volatilidade_filtro'])
        df = limpar_dados(df)
        return df.dropna()
    else:
        # ==========================================
        # REGRAS DE PREVISÃO (O DIA DE HOJE)
        # ==========================================
        # Na previsão, precisamos da última linha (hoje) de qualquer jeito.
        # Apenas preenchemos eventuais buracos de indicadores atrasados.
        df = df.ffill().bfill()
        return df
        