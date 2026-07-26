import streamlit as st
import sys
import os
import joblib
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import warnings
import unicodedata

warnings.filterwarnings('ignore')
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from processa_dados import processa_dados_completa
    from conexao_supabase import supabase
except ImportError:
    st.error("Erro ao importar módulos essenciais do sistema.")

st.set_page_config(page_title="Terminal Quantitativo", page_icon="📊", layout="wide")


def normalizar_nome_pasta(texto):
    # Remove acentos (ex: "Mineração" vira "Mineracao") e formata o padrão da pasta
    nfkd_form = unicodedata.normalize('NFKD', texto)
    texto_sem_acento = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return f"Setor_{texto_sem_acento.strip().replace(' ', '_')}"

# ==========================================
# CABEÇALHO 
# ==========================================
st.title("📊 Painel Inteligente de Investimentos")
st.markdown("""
Bem-vindo ao nosso terminal de análise preditiva. Aqui, utilizamos inteligência artificial para examinar o histórico das empresas, 
o comportamento da economia e antecipar tendências de mercado de forma totalmente automatizada. 
Escolha um setor e uma empresa abaixo para visualizar as recomendações do dia.
""")

# ==========================================
# 1. LEITURA DINÂMICA DO BANCO DE DADOS (SUPABASE)
# ==========================================
@st.cache_data(ttl=60)
def carregar_ativos_do_banco():
    try:
        res = supabase.table("cad_ativos").select("ticker, nome, setor").execute()
        return res.data if res.data else []
    except Exception as e:
        return []

dados_ativos = carregar_ativos_do_banco()

if not dados_ativos:
    st.error("⚠️ Não foi possível carregar os ativos cadastrados no banco de dados. Verifique a conexão.")
    st.stop()

df_cadastros = pd.DataFrame(dados_ativos)

# ==========================================
# FILTROS DINÂMICOS NA TELA
# ==========================================
col_setor, col_ativo, col_vazia = st.columns([1, 1, 2])

setores_disponiveis = sorted(df_cadastros['setor'].unique().tolist())

with col_setor:
    setor_escolhido = st.selectbox("1. Selecione o Setor de Atuação", setores_disponiveis)

# Filtra dinamicamente os ativos do setor selecionado
ativos_do_setor = df_cadastros[df_cadastros['setor'] == setor_escolhido]
opcoes_ativos = {f"{row['ticker']} — {row['nome']}": row['ticker'] for _, row in ativos_do_setor.iterrows()}

with col_ativo:
    ativo_rotulo_escolhido = st.selectbox("2. Selecione a Empresa", list(opcoes_ativos.keys()))
    ticker_escolhido = opcoes_ativos[ativo_rotulo_escolhido]

# Define o nome da pasta dinamicamente e sem erro de acentuação
pasta_modelos = normalizar_nome_pasta(setor_escolhido)

st.divider()

# ==========================================
# MOTOR ANALÍTICO
# ==========================================
with st.spinner(f'Analisando os dados e calculando tendências para {ticker_escolhido}...'):
    df = processa_dados_completa(ticker_escolhido, modo="previsao")
    
    if df is not None and not df.empty:
        diretorio_base = os.path.dirname(__file__)
        caminho_rf = os.path.join(diretorio_base, pasta_modelos, f"rf_modelo_{ticker_escolhido.replace('.', '_')}.pkl")
        caminho_xgb = os.path.join(diretorio_base, pasta_modelos, f"xgb_modelo_{ticker_escolhido.replace('.', '_')}.pkl")

        # Verifica se os arquivos de modelo existem antes de tentar carregá-los
        # Bloco de segurança para treinar na hora se o modelo não existir
        if not os.path.exists(caminho_rf) or not os.path.exists(caminho_xgb):
            st.warning(f"⚠️ Modelos não encontrados para {ticker_escolhido}. Gerando inteligência de forma emergencial para a {ativo_rotulo_escolhido} (isso pode levar alguns segundos)...")
            try:
                from treina_modelo import treinar_comite_ativo
                # Extrai o setor formatado real para salvar na pasta correta
                treinar_comite_ativo(ticker_escolhido, margem=3.0, pasta_destino=pasta_modelos)
                st.success("✅ Modelos gerados com sucesso! Carregando painel...")
                st.rerun() # Recarrega a página automaticamente para exibir os dados
            except Exception as e:
                st.error(f"Erro ao gerar os modelos automaticamente: {e}")


        try:
            pacote_rf = joblib.load(caminho_rf)
            pacote_xgb = joblib.load(caminho_xgb)
            
            df_recente = df.tail(60).copy() 
            if 'preco_fechamento' in df_recente.columns:
                df_recente['preco_futuro_3d'] = df_recente['preco_fechamento'].shift(-3)
                df_recente['retorno_real'] = (df_recente['preco_futuro_3d'] / df_recente['preco_fechamento']) - 1
            
            historico_rf, historico_xgb = [], []
            sinais_rf, sinais_xgb = [], []
            
            for _, linha in df_recente.iterrows():
                X_rf = linha[pacote_rf['features']].to_frame().T.astype(float).values
                X_xgb = linha[pacote_xgb['features']].to_frame().T.astype(float).values
                
                prob_rf = pacote_rf['modelo'].predict_proba(X_rf)[0][1]
                prob_xgb = pacote_xgb['modelo'].predict_proba(X_xgb)[0][1]
                
                historico_rf.append(prob_rf)
                historico_xgb.append(prob_xgb)
                
                sinais_rf.append(linha['preco_fechamento'] if prob_rf >= pacote_rf['threshold_otimizado'] else np.nan)
                sinais_xgb.append(linha['preco_fechamento'] if prob_xgb >= pacote_xgb['threshold_otimizado'] else np.nan)
                    
            df_recente['Prob_RF'] = historico_rf
            df_recente['Prob_XGB'] = historico_xgb
            df_recente['Sinal_RF'] = sinais_rf
            df_recente['Sinal_XGB'] = sinais_xgb

            linha_hoje = df_recente.iloc[-1]
            data_str = df_recente.index[-1].strftime("%d/%m/%Y")
            
            prob_hoje_rf = linha_hoje['Prob_RF']
            decisao_hoje_rf = "🟢 COMPRAR" if prob_hoje_rf >= pacote_rf['threshold_otimizado'] else "⚪ AGUARDAR"
            
            prob_hoje_xgb = linha_hoje['Prob_XGB']
            decisao_hoje_xgb = "🟢 COMPRAR" if prob_hoje_xgb >= pacote_xgb['threshold_otimizado'] else "⚪ AGUARDAR"

            # ==========================================
            # DASHBOARD VISUAL (RESUMO EXECUTIVO)
            # ==========================================
            st.markdown(f"### 🎯 Recomendação para o Próximo Ciclo (Referência: {data_str})")
            
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Preço de Fechamento", f"R$ {linha_hoje['preco_fechamento']:.2f}")
            kpi2.metric("Robô Conservador", decisao_hoje_rf, f"Confiança: {prob_hoje_rf:.1%}")
            kpi3.metric("Robô Agressivo", decisao_hoje_xgb, f"Confiança: {prob_hoje_xgb:.1%}")
            kpi4.metric("Exigência Mínima (Corte)", f"{pacote_rf['threshold_otimizado']:.1%}")
            
            st.write("") 
            
            # ABAS DO PAINEL COM TEXTOS DIDÁTICOS
            aba1, aba2, aba3 = st.tabs(["📉 Histórico e Sinais", "📋 Histórico de Desempenho", "🧠 Raio-X da Inteligência Artificial"])
            
            with aba1:
                st.markdown("##### Como o preço se comportou frente aos sinais gerados")
                st.markdown("_O gráfico abaixo cruza a linha de valor da ação com os momentos em que nossos algoritmos identificaram oportunidades de compra._")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_recente.index, y=df_recente['preco_fechamento'], mode='lines', name='Preço da Ação (R$)', line=dict(color='#8c9eff', width=2)))
                fig.add_trace(go.Scatter(x=df_recente.index, y=df_recente['Sinal_RF'], mode='markers', name='Sinal de Compra (Conservador)', marker=dict(symbol='triangle-up', color='#00e676', size=14, line=dict(width=1, color='black'))))
                fig.add_trace(go.Scatter(x=df_recente.index, y=df_recente['Sinal_XGB'], mode='markers', name='Sinal de Compra (Agressivo)', marker=dict(symbol='triangle-up', color='#ff9100', size=10, line=dict(width=1, color='black'))))
                fig.update_layout(template="plotly_dark", height=400, margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)
                
            with aba2:
                st.markdown("##### Auditoria dos Últimos Sinais Gerados")
                st.markdown("_Acompanhe abaixo se as recomendações dadas nos ciclos anteriores resultaram em valorização ou se protegeram o capital de quedas._")
                
                # [MANUAL EXPLICATIVO COMPLETO COM A EXIGÊNCIA MÍNIMA]
                with st.expander("📖 Manual de Como Ler o Desempenho e as Recomendações", expanded=True):
                    st.markdown("""
                    Para ajudar você a compreender nossa auditoria, veja o significado de cada conceito e métrica do sistema:
                    
                    * **⚙️ Exigência Mínima (Limiar / Threshold de Corte):** 
                        * É o rigor de segurança do robô. Para que a inteligência artificial o recomende uma **Compra**, a probabilidade de alta calculada precisa atingir ou superar essa porcentagem mínima. Se a confiança ficar abaixo desse corte, o sistema prefere adotar a cautela.
                        
                    * **🟢 COMPRA:** O modelo atingiu a exigência mínima de confiança, identificando um cenário estatisticamente favorável.
                        * *Acerto:* O robô indicou compra e a ação realmente subiu nos 3 dias seguintes.
                        * *Erro:* O robô indicou compra, mas a ação acabou caindo (alarme falso).
                        
                    * **⚪ AGUARDAR:** O modelo ficou abaixo da exigência mínima de segurança devido a sinais divergentes ou risco elevado.
                        * *O que significa na prática:* **Para quem não tem a ação**, é um sinal para ficar de fora e não arriscar capital novo. **Para quem já possui a ação**, funciona como um "sinal amarelo", indicando perda de força de alta e sugerindo atenção redobrada ou proteção de lucros.
                        
                    * **O que significam as Avaliações quando o robô manda Aguardar:**
                        * **🛡️ Proteção:** O robô indicou aguardar e a ação caiu nos dias seguintes. Isso significa que **o sistema evitou que você perdesse dinheiro**, livrando-o da queda.
                        * **⚠️ Oportunidade:** O robô indicou aguardar por cautela, mas a ação acabou subindo. Significa que você não perdeu capital, mas **deixou de capturar aquela alta específica** (um custo de oportunidade por ter ficado de fora).
                    """)

                tabela = df_recente.copy().reset_index()
                tabela = tabela.dropna(subset=['retorno_real']).tail(15)
                
                tabela_rf = tabela[['data', 'preco_fechamento', 'Prob_RF', 'retorno_real']].copy()
                tabela_rf['Decisão'] = np.where(tabela_rf['Prob_RF'] >= pacote_rf['threshold_otimizado'], "COMPRA", "AGUARDAR")
                tabela_rf['Avaliação'] = np.where(
                    (tabela_rf['Decisão'] == "COMPRA") & (tabela_rf['retorno_real'] > 0), "✅ Acerto",
                    np.where((tabela_rf['Decisão'] == "COMPRA") & (tabela_rf['retorno_real'] <= 0), "❌ Erro",
                    np.where((tabela_rf['Decisão'] == "AGUARDAR") & (tabela_rf['retorno_real'] <= 0), "🛡️ Proteção", "⚠️ Oportunidade"))
                )
                
                tabela_xgb = tabela[['data', 'preco_fechamento', 'Prob_XGB', 'retorno_real']].copy()
                tabela_xgb['Decisão'] = np.where(tabela_xgb['Prob_XGB'] >= pacote_xgb['threshold_otimizado'], "COMPRA", "AGUARDAR")
                tabela_xgb['Avaliação'] = np.where(
                    (tabela_xgb['Decisão'] == "COMPRA") & (tabela_xgb['retorno_real'] > 0), "✅ Acerto",
                    np.where((tabela_xgb['Decisão'] == "COMPRA") & (tabela_xgb['retorno_real'] <= 0), "❌ Erro",
                    np.where((tabela_xgb['Decisão'] == "AGUARDAR") & (tabela_xgb['retorno_real'] <= 0), "🛡️ Proteção", "⚠️ Oportunidade"))
                )
                
                for tab in [tabela_rf, tabela_xgb]:
                    tab['retorno_real'] = (tab['retorno_real'] * 100).round(2).astype(str) + '%'
                    
                tabela_rf['Prob_RF'] = (tabela_rf['Prob_RF'] * 100).round(2).astype(str) + '%'
                tabela_xgb['Prob_XGB'] = (tabela_xgb['Prob_XGB'] * 100).round(2).astype(str) + '%'
                
                tabela_rf.columns = ['Data', 'Preço (R$)', 'Confiança', 'Retorno em 3 Dias', 'Decisão', 'Avaliação']
                tabela_xgb.columns = ['Data', 'Preço (R$)', 'Confiança', 'Retorno em 3 Dias', 'Decisão', 'Avaliação']
                
                col_tab1, col_tab2 = st.columns(2)
                with col_tab1:
                    st.markdown("**🌲 Modelo Conservador (Foco em Segurança)**")
                    st.dataframe(tabela_rf, use_container_width=True, hide_index=True)
                with col_tab2:
                    st.markdown("**🔥 Modelo Agressivo (Foco em Oportunidades)**")
                    st.dataframe(tabela_xgb, use_container_width=True, hide_index=True)
            with aba3:
                st.markdown("##### Avaliação de Desempenho Geral")
                st.markdown("_Resumo estatístico do comportamento da inteligência artificial nos últimos 60 ciclos._")
                
                tabela_raiox = df_recente.dropna(subset=['retorno_real']).copy()
                tabela_raiox['Decisao_RF'] = np.where(tabela_raiox['Prob_RF'] >= pacote_rf['threshold_otimizado'], "COMPRA", "AGUARDAR")
                tabela_raiox['Decisao_XGB'] = np.where(tabela_raiox['Prob_XGB'] >= pacote_xgb['threshold_otimizado'], "COMPRA", "AGUARDAR")
                
                def calcular_metricas(coluna_decisao):
                    compras = len(tabela_raiox[tabela_raiox[coluna_decisao] == "COMPRA"])
                    acertos = len(tabela_raiox[(tabela_raiox[coluna_decisao] == "COMPRA") & (tabela_raiox['retorno_real'] > 0)])
                    falsos = compras - acertos
                    
                    aguardos = len(tabela_raiox[tabela_raiox[coluna_decisao] == "AGUARDAR"])
                    quedas = len(tabela_raiox[(tabela_raiox[coluna_decisao] == "AGUARDAR") & (tabela_raiox['retorno_real'] <= 0)])
                    perdidas = aguardos - quedas
                    
                    return compras, acertos, falsos, aguardos, quedas, perdidas

                rf_comp, rf_acert, rf_falso, rf_ag, rf_quedas, rf_perd = calcular_metricas('Decisao_RF')
                xgb_comp, xgb_acert, xgb_falso, xgb_ag, xgb_quedas, xgb_perd = calcular_metricas('Decisao_XGB')

                col_rf, col_xgb = st.columns(2)
                
                with col_rf:
                    st.subheader("🌲 Modelo Conservador")
                    st.info(f"**Acertos de Compra:** Recomendou entrada {rf_comp} vezes, obtendo sucesso em **{rf_acert}** ocasiões e alarme falso em **{rf_falso}**.")
                    st.success(f"**Proteção de Patrimônio:** Manteve-se cauteloso {rf_ag} vezes, conseguindo evitar quedas em **{rf_quedas}** momentos.")
                    st.warning(f"**Oportunidades Não Aproveitadas:** Ficou de fora em dias que a ação acabou subindo (**{rf_perd}** ocasiões).")
                    
                with col_xgb:
                    st.subheader("🔥 Modelo Agressivo")
                    st.info(f"**Acertos de Compra:** Recomendou entrada {xgb_comp} vezes, obtendo sucesso em **{xgb_acert}** ocasiões e alarme falso em **{xgb_falso}**.")
                    st.success(f"**Proteção de Patrimônio:** Manteve-se cauteloso {xgb_ag} vezes, conseguindo evitar quedas em **{xgb_quedas}** momentos.")
                    st.warning(f"**Oportunidades Não Aproveitadas:** Ficou de fora em dias que a ação acabou subindo (**{xgb_perd}** ocasiões).")

            # ==========================================
            # INTEGRAÇÃO TELEGRAM (INSCRIÇÃO E CANCELAMENTO)
            # ==========================================
            st.divider()
            st.markdown("### 🔔 Central de Alertas via Telegram")
            st.markdown("Deseja receber avisos automáticos e detalhados diretamente no seu celular sempre que houver uma nova oportunidade?")
            
            with st.expander("❓ Como obter o seu número de identificação (ChatID)?", expanded=False):
                st.markdown("""
                1. Abra o aplicativo do Telegram e busque pelo contato **@userinfobot**.
                2. Envie o comando `/start` para ele. O bot vai te devolver uma sequência numérica (ex: `123456789`).
                3. Certifique-se também de iniciar uma conversa com o nosso robô oficial de alertas (`@ProjetoQuantBot`).
                4. Copie o seu número de ID, cole no campo abaixo e escolha se deseja ativar ou desativar os avisos.
                """)

            col_email, col_b1, col_b2 = st.columns([2, 1, 1])
            with col_email:
                chat_id_input = st.text_input("Informe seu ChatID do Telegram (Apenas números):", placeholder="Ex: 123456789")
            with col_b1:
                st.write("") 
                st.write("")
                btn_ativar = st.button("Ativar Alertas", type="primary", use_container_width=True)
            with col_b2:
                st.write("") 
                st.write("")
                btn_cancelar = st.button("Desativar Alertas", type="secondary", use_container_width=True)

            if btn_ativar or btn_cancelar:
                if chat_id_input.strip() == "":
                    st.warning("Por favor, preencha o campo com o seu ChatID.")
                elif not chat_id_input.strip().isdigit():
                    st.error("Formato inválido. Certifique-se de digitar apenas números.")
                else:
                    try:
                        cid = chat_id_input.strip()
                        if btn_ativar:
                            busca = supabase.table("inscricoes_telegram").select("*").eq("chat_id", cid).eq("ticker", ticker_escolhido).execute()
                            if not busca.data:
                                supabase.table("inscricoes_telegram").insert({
                                    "chat_id": cid,
                                    "ticker": ticker_escolhido,
                                    "ativo": True
                                }).execute()
                            else:
                                supabase.table("inscricoes_telegram").update({"ativo": True}).eq("chat_id", cid).eq("ticker", ticker_escolhido).execute()
                            st.success(f"✅ Seus alertas para o ativo {ticker_escolhido} foram ativados com sucesso!")
                        
                        elif btn_cancelar:
                            supabase.table("inscricoes_telegram").update({"ativo": False}).eq("chat_id", cid).eq("ticker", ticker_escolhido).execute()
                            st.info(f"🔕 Os alertas para o ativo {ticker_escolhido} foram desativados com sucesso.")
                    except Exception as e:
                        st.error("Ocorreu um erro ao atualizar o seu cadastro no banco de dados.")
                
        except FileNotFoundError:
            st.error(f"⚠️ Os arquivos de inteligência artificial necessários não foram encontrados para o ativo {ticker_escolhido} na pasta '{pasta_modelos}'.")