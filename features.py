import numpy as np
import pandas as pd

# =================================================
# 1. RETORNOS E LAGS (MEMÓRIA DO MERCADO)
# =================================================
def criar_features_lag(df):
    df['retorno'] = df['preco_fechamento'].pct_change()

    for lag in [1, 2, 3, 5, 10]:
        df[f'retorno_lag_{lag}'] = df['retorno'].shift(lag)
        df[f'volume_lag_{lag}'] = df['volume'].shift(lag)

    return df

# =================================================
# 2. MOMENTUM E DIREÇÃO
# =================================================
def criar_features_momentum(df):
    df['mom_3'] = df['preco_fechamento'].pct_change(3)
    df['mom_5'] = df['preco_fechamento'].pct_change(5)
    df['mom_10'] = df['preco_fechamento'].pct_change(10)
    df['mom_20'] = df['preco_fechamento'].pct_change(20)

    # Aceleração
    df['mom_acc'] = df['mom_5'] - df['mom_10']
    df['mom_5_lag1'] = df['mom_5'].shift(1)

    # Direcionalidade
    df['up_moves'] = (df['retorno'] > 0).rolling(10).mean()
    df['down_moves'] = (df['retorno'] < 0).rolling(10).mean()

    return df

# =================================================
# 3. VOLATILIDADE (RISCO / REGIME)
# =================================================
def criar_features_volatilidade(df):
    df['vol_10'] = df['retorno'].rolling(10).std()
    df['vol_20'] = df['retorno'].rolling(20).std()

    # Regime / Razão de volatilidade
    den = df['vol_20'].rolling(50).mean()
    df['vol_ratio'] = df['vol_20'] / den.replace(0, np.nan)
    df['vol_regime'] = df['vol_10'] / df['vol_20'].replace(0, np.nan)

    return df

# =================================================
# 4. VOLUME (INTELIGÊNCIA DE FLUXO)
# =================================================
def criar_features_volume(df):
    df['volume_ma10'] = df['volume'].rolling(10).mean()
    df['volume_ma20'] = df['volume'].rolling(20).mean()
    
    df['volume_rel'] = df['volume'] / df['volume_ma20'].replace(0, np.nan)
    
    den = df['volume'].rolling(50).mean()
    df['volume_spike'] = df['volume'] / den.replace(0, np.nan)

    df['vol_10_lag1'] = df['vol_10'].shift(1)
    df['volume_momentum'] = df['volume'] * df['retorno']

    return df

# =================================================
# 5. TENDÊNCIA E ESTRUTURA
# =================================================
def criar_features_tendencia(df):
    ma10 = df['preco_fechamento'].rolling(10).mean()
    ma20 = df['preco_fechamento'].rolling(20).mean()
    ma50 = df['preco_fechamento'].rolling(50).mean()

    df['trend_10_20'] = ma10 / ma20.replace(0, np.nan)
    df['trend_20_50'] = ma20 / ma50.replace(0, np.nan)
    df['trend_ratio'] = ma10 / ma50.replace(0, np.nan)
    
    ma5 = df['preco_fechamento'].rolling(5).mean()
    df['trend_diff'] = ma5 / ma20.replace(0, np.nan)
    
    # Força da tendência
    df['trend_strength'] = (df['preco_fechamento'] - ma50) / ma50.replace(0, np.nan)

    df['dist_max_20'] = df['preco_fechamento'] / df['preco_fechamento'].rolling(20).max().replace(0, np.nan)
    df['dist_min_20'] = df['preco_fechamento'] / df['preco_fechamento'].rolling(20).min().replace(0, np.nan)

    return df

# =================================================
# 6. SEQUÊNCIA DE ALTA/BAIXA
# =================================================
def criar_features_sequencia(df):
    df['up_day'] = (df['retorno'] > 0).astype(int)
    grupo = (df['up_day'] != df['up_day'].shift()).cumsum()
    df['streak_up'] = df['up_day'] * (df['up_day'].groupby(grupo).cumcount() + 1)
    return df

# =================================================
# 7. FEATURES SETORIAIS (100% DINÂMICAS)
# =================================================
def criar_features_setoriais(df):
    colunas_setor = [c for c in df.columns if 'setor_' in c and '_close' in c]

    for col in colunas_setor:
        prefix = col.replace('setor_', '').replace('_close', '')

        # Retorno do indicador
        df[f'{prefix}_ret'] = df[col].pct_change()

        # Spread (ação vs indicador)
        df[f'spread_{prefix}'] = df['retorno'] - df[f'{prefix}_ret']

        # Correlações
        df[f'corr_{prefix}'] = df['preco_fechamento'].rolling(10).corr(df[col])
        df[f'corr_10_{prefix}'] = df['preco_fechamento'].rolling(10).corr(df[col])

    # Força Relativa Universal (Acha o índice de mercado principal e compara)
    indices_mercado = ['setor_bvsp_close', 'setor_ifix_close', 'setor_spx_close']
    for idx in indices_mercado:
        if idx in df.columns:
            nome_idx = idx.replace('setor_', '').replace('_close', '')
            df[f'rs_{nome_idx}'] = df['preco_fechamento'] / df[idx].replace(0, np.nan)
            df[f'rs_{nome_idx}_mom'] = df[f'rs_{nome_idx}'].pct_change(5)

    return df

# =================================================
# 8. PIPELINE FINAL DE FEATURES
# =================================================
def gerar_features(df):
    df = criar_features_lag(df)
    df = criar_features_momentum(df)
    df = criar_features_volatilidade(df)
    df = criar_features_volume(df)
    df = criar_features_tendencia(df)
    df = criar_features_sequencia(df)
    df = criar_features_setoriais(df)

    return df