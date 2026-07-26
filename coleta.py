import os
import yfinance as yf
import pandas as pd
from conexao_supabase import supabase

from datetime import datetime, timedelta
import time


#=================================================
# Buscar no banco a lista de tickers que precisa ser monitorado
def ativos_para_atualizar():
    response = supabase.table("cad_ativos").select("id, ticker").execute()
    return response.data

#=================================================
# Define se baixa os dados desde 2016 ou apenas o que falta
def buscar_data_inicio(tabela_precos, coluna_id, id_valor):
    res = supabase.table(tabela_precos) \
        .select("data") \
        .eq(coluna_id, id_valor) \
        .order("data", desc=True) \
        .limit(1).execute()

    if res.data:
        # Retorna o dia seguinte ao último registro
        return datetime.strptime(res.data[0]['data'], '%Y-%m-%d').date() + timedelta(days=1)
    
    # Se a tabela estiver vazia, começa em 2016
    return datetime(2016, 1, 1).date()

#=================================================
# Salvar no Supabase
def salvar_no_banco(tabela_precos, coluna_id, id_valor, df):
    payload = []
    
    # Garante que não há fuso horário no índice para evitar erros na conversão de string
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    for data_index, row in df.iterrows():
        # Tratamento para garantir que pegamos um valor escalar (float)
        def limpar_valor(val):
            if isinstance(val, pd.Series):
                return float(val.iloc[0])
            return float(val)

        item = {
            coluna_id: id_valor,
            "data": data_index.strftime('%Y-%m-%d'),
            "preco_fechamento": limpar_valor(row['Close'])
        }
        
        # Salva o volume se a coluna existir
        if 'Volume' in row:
            item["volume"] = limpar_valor(row['Volume'])
            
        payload.append(item)
    
    if payload:
        # Upsert em lote (batch) para ser mais rápido
        supabase.table(tabela_precos).upsert(payload, on_conflict="data, " + coluna_id).execute()

#=================================================
# Baixa os dados do Yahoo Finance
def executar():
    configuracoes = [
        {
            "descricao": "ATIVOS (Ações)",
            "tab_cad": "cad_ativos",
            "tab_precos": "precos_diarios",
            "col_id": "ativo_id"
        },
        {
            "descricao": "INDICADORES SETORIAIS (Macro)",
            "tab_cad": "cad_indicadores",
            "tab_precos": "precos_indicadores",
            "col_id": "indicador_id"
        }
    ]

    for conf in configuracoes:
        print(f"\n{'='*40}")
        print(f"PROCESSANDO: {conf['descricao']}")
        print(f"{'='*40}")

        itens = supabase.table(conf['tab_cad']).select("id, ticker").execute().data

        for item in itens:
            ticker = item['ticker']
            id_banco = item['id']

            data_start = buscar_data_inicio(conf['tab_precos'], conf['col_id'], id_banco)
            hoje = datetime.now().date()
            amanha = hoje + timedelta(days=1) # CORREÇÃO: O Yahoo é exclusivo, precisa buscar até 'amanhã'

            if data_start > hoje:
                print(f"[-] {ticker}: Já está atualizado.")
                continue

            print(f"[+] {ticker}: Baixando de {data_start} até {hoje}...")
            # O parâmetro end recebe 'amanha' para incluir o dia de 'hoje'
            df = yf.download(ticker, start=data_start, end=amanha)

            if not df.empty:
                salvar_no_banco(conf['tab_precos'], conf['col_id'], id_banco, df)
                print(f"[*] {ticker}: Sucesso. {len(df)} novos dias salvos.")
                time.sleep(2) 
            else:
                print(f"[!] {ticker}: Nenhum dado encontrado.")

#=================================================
if __name__ == "__main__":
    executar()