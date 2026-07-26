import sys
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import confusion_matrix
from conexao_supabase import supabase

# Adiciona a pasta principal (raiz) ao sistema 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processa_dados import processa_dados_completa

def treinar_comite_ativo(ticker, margem=3.0, pasta_destino="Modelos_Treinados"):
    print(f"\n=============================================")
    print(f"🌲🔥 TREINANDO COMITÊ PREDITIVO: {ticker}")
    print(f"=============================================")
    
    # 1. Carrega os dados processados e filtrados
    df = processa_dados_completa(ticker, margem=margem, modo="treino")
    if df is None or df.empty:
        print(f"❌ Erro ao processar dados para {ticker}.")
        return

    # 2. Separa Features (X) e Target (y) - SEM VAZAMENTO DE PREÇOS
    features_excluidas = ['target', 'retorno_3d', 'data']
    colunas_proibidas = [c for c in df.columns if 'close' in c.lower() or 'volume' in c.lower() or c == 'preco_fechamento']
    features = [col for col in df.columns if col not in features_excluidas and col not in colunas_proibidas]
    
    X = df[features]
    y = df['target']

    # 3. Divisão Treino/Teste (Temporal)
    tamanho_treino = int(len(df) * 0.8)
    X_treino, X_teste = X.iloc[:tamanho_treino], X.iloc[tamanho_treino:]
    y_treino, y_teste = y.iloc[:tamanho_treino], y.iloc[tamanho_treino:]

    X_treino_clean = X_treino.astype(float).values
    X_teste_clean = X_teste.astype(float).values

    # ========================================================
    # CÉREBRO 1: RANDOM FOREST (Perfil Conservador)
    # ========================================================
    print("\n🌲 Treinando Random Forest (Conservador)...")
    rf = RandomForestClassifier(n_estimators=200, max_depth=5, random_state=42, class_weight="balanced")
    rf.fit(X_treino_clean, y_treino)
    
    # Threshold Dinâmico RF
    probabilidades_rf = rf.predict_proba(X_teste_clean)[:, 1]
    threshold_rf = 0.50
    for t in np.arange(0.50, 0.70, 0.01):
        preds = (probabilidades_rf >= t).astype(int)
        cm = confusion_matrix(y_teste, preds)
        if cm.shape == (2, 2) and cm[1, 1] / (cm[1, 1] + cm[1, 0] + 1e-9) > 0.20:
            threshold_rf = t
    
    # ========================================================
    # CÉREBRO 2: XGBOOST (Perfil Dinâmico/Agressivo)
    # ========================================================
    print("🔥 Treinando XGBoost (Dinâmico)...")
    xgb = XGBClassifier(n_estimators=200, learning_rate=0.05, max_depth=4, subsample=0.8, colsample_bytree=0.8, random_state=42, eval_metric='logloss')
    xgb.fit(X_treino_clean, y_treino)
    
    # Threshold Dinâmico XGB
    probabilidades_xgb = xgb.predict_proba(X_teste_clean)[:, 1]
    threshold_xgb = 0.50
    for t in np.arange(0.50, 0.70, 0.01):
        preds = (probabilidades_xgb >= t).astype(int)
        cm = confusion_matrix(y_teste, preds)
        if cm.shape == (2, 2) and cm[1, 1] / (cm[1, 1] + cm[1, 0] + 1e-9) > 0.20:
            threshold_xgb = t

    # ========================================================
    # SALVANDO O COMITÊ NA PASTA ESPECÍFICA
    # ========================================================
    diretorio_atual = os.path.dirname(__file__)
    caminho_pasta = os.path.join(diretorio_atual, pasta_destino)
    os.makedirs(caminho_pasta, exist_ok=True)
    
    pacote_rf = {'modelo': rf, 'features': features, 'threshold_otimizado': threshold_rf}
    caminho_rf = os.path.join(caminho_pasta, f"rf_modelo_{ticker.replace('.', '_')}.pkl")
    joblib.dump(pacote_rf, caminho_rf)
    
    pacote_xgb = {'modelo': xgb, 'features': features, 'threshold_otimizado': threshold_xgb}
    caminho_xgb = os.path.join(caminho_pasta, f"xgb_modelo_{ticker.replace('.', '_')}.pkl")
    joblib.dump(pacote_xgb, caminho_xgb)

    print("\n✅ COMITÊ TREINADO E SALVO COM SUCESSO!")
    print(f"📂 Destino: {caminho_pasta}")
    print(f"   - {os.path.basename(caminho_rf)} (Corte: {threshold_rf:.2f})")
    print(f"   - {os.path.basename(caminho_xgb)} (Corte: {threshold_xgb:.2f})")

if __name__ == "__main__":
    print("🔄 Buscando ativos cadastrados no banco de dados...")
    
    # 1. Puxa todos os ativos ativos e seus respectivos setores do Supabase
    res = supabase.table("cad_ativos").select("ticker, setor").execute()
    ativos_cadastrados = res.data
    
    if not ativos_cadastrados:
        print("❌ Nenhum ativo encontrado no banco de dados.")
    else:
        for item in ativos_cadastrados:
            ticker = item['ticker']
            setor = item['setor'] # Ex: "Energia", "Mineração", "Bancos"
            
            # Formata o nome da pasta com base no setor (ex: "Setor_Energia")
            nome_pasta_setor = f"Setor_{setor.replace(' ', '_')}"
            
            # Roda a esteira de machine learning para o ativo
            try:
                treinar_comite_ativo(ticker, margem=3.0, pasta_destino=nome_pasta_setor)
            except Exception as e:
                print(f"❌ Erro ao treinar o ativo {ticker}: {e}")
                
        print("\n🚀 Processo de treinamento em lote finalizado para todos os setores!")