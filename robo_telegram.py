# Faz previsões e envia alertas via Telegram para os usuários cadastrados no banco de dados.

import sys
import os
import joblib
import warnings
import requests


# Carrega as chaves e a conexão com o banco
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
warnings.filterwarnings('ignore')
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from processa_dados import processa_dados_completa
from conexao_supabase import supabase

TOKEN = os.getenv("TELEGRAM_TOKEN")

def enviar_mensagem_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": str(chat_id),  # Garante que o ID vá como texto
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        resposta = requests.post(url, json=payload)
        if resposta.status_code == 200:
            pass 
        else:
            print(f"❌ O Telegram bloqueou a mensagem para o ID {chat_id}.")
            print(f"🔍 Motivo oficial do Telegram: {resposta.text}")
    except Exception as e:
        print(f"❌ Erro de internet ao tentar enviar para {chat_id}: {e}")

def gerar_alerta_setorial(ticker):
    # 1. Consulta dinâmica no Supabase para descobrir o Setor e o Nome da Empresa
    res_ativo = supabase.table("cad_ativos").select("nome, setor").eq("ticker", ticker).execute()
    
    if not res_ativo.data:
        return f"⚠️ Erro: O ativo {ticker} não foi encontrado no cadastro do banco de dados."
        
    info_ativo = res_ativo.data[0]
    nome_empresa = info_ativo['nome']
    setor_bd = info_ativo['setor'] # Ex: "Energia", "Mineração"

    # Verificação para saber se os arquivos .pkl existe
    caminho_rf = os.path.join(diretorio_base, pasta_modelos, f"rf_modelo_{ticker.replace('.', '_')}.pkl")
    caminho_xgb = os.path.join(diretorio_base, pasta_modelos, f"xgb_modelo_{ticker.replace('.', '_')}.pkl")

    # REDE DE SEGURANÇA: Se o modelo não existir na nuvem, treina na hora para não quebrar
    if not os.path.exists(caminho_rf) or not os.path.exists(caminho_xgb):
        print(f"⚠️ Modelos não encontrados para {ticker}. Iniciando treinamento de emergência...")
        from treina_modelo import treinar_comite_ativo
        treinar_comite_ativo(ticker, margem=3.0, pasta_destino=pasta_modelos)
    
    # Define a pasta dinamicamente baseada no setor cadastrado
    pasta_modelos = f"Setor_{setor_bd.replace(' ', '_')}"

    # 2. Puxa os dados recentes da ação
    df = processa_dados_completa(ticker, modo="previsao")
    if df is None or df.empty:
        return f"⚠️ Erro: Sem dados recentes para {ticker}."
        
    diretorio_base = os.path.dirname(__file__)
    try:
        # Carrega os modelos da pasta correta do setor
        caminho_rf = os.path.join(diretorio_base, pasta_modelos, f"rf_modelo_{ticker.replace('.', '_')}.pkl")
        caminho_xgb = os.path.join(diretorio_base, pasta_modelos, f"xgb_modelo_{ticker.replace('.', '_')}.pkl")
        
        pacote_rf = joblib.load(caminho_rf)
        pacote_xgb = joblib.load(caminho_xgb)
        
        linha_hoje = df.iloc[-1]
        data_str = df.index[-1].strftime("%d/%m/%Y")
        
        X_rf = linha_hoje[pacote_rf['features']].to_frame().T.astype(float).values
        X_xgb = linha_hoje[pacote_xgb['features']].to_frame().T.astype(float).values
        
        prob_rf = pacote_rf['modelo'].predict_proba(X_rf)[0][1]
        prob_xgb = pacote_xgb['modelo'].predict_proba(X_xgb)[0][1]
        
        thresh_rf = pacote_rf['threshold_otimizado']
        thresh_xgb = pacote_xgb['threshold_otimizado']
        
        # ========================================================
        # Tradução da Matemática para uma Linguagem Formal e Clara
        # ========================================================
        if prob_rf >= thresh_rf and prob_xgb >= thresh_xgb:
            veredito = "🟢 *RECOMENDAÇÃO: COMPRAR*"
            resumo = "Nossos sistemas identificaram um cenário altamente favorável."
            motivo = "Ambos os algoritmos confirmam que há uma forte tendência de alta. As condições são ideais para o investimento."
        elif prob_rf < thresh_rf and prob_xgb < thresh_xgb:
            veredito = "🔴 *RECOMENDAÇÃO: NÃO COMPRAR (OU VENDER)*"
            resumo = "O cenário atual apresenta um nível de risco muito elevado."
            motivo = "A probabilidade de desvalorização é expressiva. Recomendamos proteger seu capital e evitar a compra neste momento."
        else:
            veredito = "⚪ *RECOMENDAÇÃO: AGUARDAR*"
            resumo = "O mercado encontra-se em um momento de indefinição."
            motivo = "Os indicadores apresentam sinais divergentes. A atitude mais prudente é aguardar um cenário claro antes de arriscar seu patrimônio."
        
        # ========================================================
        # Montagem do Layout Visual em Markdown
        # ========================================================
        texto = f"📊 *RELATÓRIO DE INTELIGÊNCIA ARTIFICIAL*\n"
        texto += f"🏢 *Ativo:* {ticker} — {nome_empresa}\n"
        texto += f"📅 Data de Referência: {data_str}\n"
        texto += f"💰 Preço de Fechamento: R$ {linha_hoje['preco_fechamento']:.2f}\n\n"
        
        texto += f"👉 *SÍNTESE DA ANÁLISE:* {veredito}\n\n"
        
        texto += f"💡 *Fundamentação da IA:*\n"
        texto += f"_{resumo}_\n"
        texto += f"• {motivo}\n\n"
        
        texto += f"⚙️ *Detalhamento Técnico (Como a IA toma essa decisão?)*\n"
        texto += f"_Para recomendar uma compra, o 'Nível de Confiança' calculado pela Inteligência Artificial precisa atingir a 'Exigência Mínima' de segurança do sistema._\n\n"
        
        texto += f"🛡️ *Robô Conservador (Foco em Segurança):*\n"
        texto += f"• Nível de Confiança: *{prob_rf*100:.1f}%*\n"
        texto += f"• Exigência Mínima: *{thresh_rf*100:.1f}%*\n"
        texto += f"• Veredito do Robô: {'✅ Aprovado' if prob_rf >= thresh_rf else '❌ Reprovado'}\n\n"
        
        texto += f"⚡ *Robô Agressivo (Foco em Oportunidade):*\n"
        texto += f"• Nível de Confiança: *{prob_xgb*100:.1f}%*\n"
        texto += f"• Exigência Mínima: *{thresh_xgb*100:.1f}%*\n"
        texto += f"• Veredito do Robô: {'✅ Aprovado' if prob_xgb >= thresh_xgb else '❌ Reprovado'}\n"
        
        return texto
    except FileNotFoundError:
        return f"⚠️ Modelos preditivos não encontrados para {ticker} na pasta '{pasta_modelos}'."

def orquestrar_disparos():
    print("Iniciando varredura de usuários e geração de alertas...")
    
    # 1. Busca todos os usuários ativos no banco
    res = supabase.table("inscricoes_telegram").select("*").eq("ativo", True).execute()
    inscricoes = res.data
    
    if not inscricoes:
        print("Nenhum usuário inscrito no momento.")
        return

    # 2. Descobre quais ativos precisamos analisar hoje
    tickers_necessarios = set([inscricao['ticker'] for inscricao in inscricoes])
    relatorios_gerados = {}
    
    for ticker in tickers_necessarios:
        print(f"Gerando inteligência para {ticker}...")
        # Agora o próprio gerador busca o setor no banco, sem listas manuais aqui!
        relatorios_gerados[ticker] = gerar_alerta_setorial(ticker)
        
    # 3. Dispara as mensagens personalizadas para cada usuário
    print("Disparando mensagens para os usuários...")
    for inscricao in inscricoes:
        chat_id = inscricao['chat_id']
        ticker = inscricao['ticker']
        mensagem = relatorios_gerados[ticker]
        
        enviar_mensagem_telegram(chat_id, mensagem)
        print(f"✅ Alerta de {ticker} enviado para ID {chat_id}")

if __name__ == "__main__":
    orquestrar_disparos()
    print("Processo finalizado com sucesso.")