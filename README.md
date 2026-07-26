# 📊 Painel Inteligente de Investimentos

> Terminal quantitativo de análise preditiva e monitoramento setorial automatizado por Inteligência Artificial e Machine Learning.

---

## Sobre o Projeto
O **Painel Inteligente de Investimentos** é uma plataforma desenvolvida para auxiliar investidores e analistas no acompanhamento de ativos da B3 (como Energia, Mineração e Tecnologia). Utilizando modelos estatísticos e aprendizado de máquina (*Random Forest* e *XGBoost*), o sistema processa indicadores macroeconômicos e técnicos para antecipar tendências de mercado, oferecendo recomendações claras de forma automatizada tanto via web quanto por um bot no Telegram.

---

## Estrutura de Páginas e Arquitetura do Sistema

O projeto foi estruturado para ser modular, dinâmico e escalável através de um banco de dados relacional (Supabase):

* **`dashboard.py` (Interface Web - Streamlit):**
  * **Cabeçalho e Filtros Dinâmicos:** Seleção automatizada de setores e empresas direto da base de dados.
  * **Aba 1 (Histórico e Sinais):** Gráficos interativos (Plotly) cruzando a linha de preço com os momentos exatos em que a I.A. identificou oportunidades.
  * **Aba 2 (Histórico de Desempenho & Manual):** Auditoria dos últimos sinais com uma tabela de backtest e um **manual explicativo detalhado** esclarecendo os conceitos de *Acerto*, *Erro*, *Proteção*, *Oportunidade* e a *Exigência Mínima (Threshold)*.
  * **Aba 3 (Raio-X da I.A.):** Estatísticas gerais de precisão, controle de risco e eficácia dos robôs (Conservador vs. Agressivo).
  * **Central de Alertas:** Inscrição e cancelamento instantâneo de notificações via Telegram utilizando o ChatID do usuário.

* **Scripts de Backend e Inteligência:**
  * **`coleta.py`:** Coleta automatizada de dados históricos de ativos, moedas e commodities.
  * **`treina_modelo.py`:** Esteira de machine learning que treina comitês preditivos adaptativos por setor e define limiares de corte dinâmicos.
  * **`robo_telegram.py`:** Robô autônomo responsável por disparar relatórios setoriais formatados diretamente para o celular dos usuários cadastrados.

---

## 🖼️ Demonstração da Plataforma

![Print do Dashboard](img/dashboard_1.png)
<!-- Exemplo: ![Print do Dashboard](img/dashboard_1.png) -->

![Print do Dashboard](img/dashboard_2.png)

![Auditoria dos Últimos Sinais Gerados](img/desempenho.png)

![Avaliação de Desempenho Geral dos modelos](img/avaliacao.png)
---

## Tecnologias Utilizadas
* **Python** (Linguagem principal)
* **Streamlit** (Interface gráfica web)
* **Scikit-Learn & XGBoost** (Modelos preditivos de Machine Learning)
* **Plotly** (Visualização avançada de dados)
* **Supabase** (Banco de dados em nuvem)
* **API do Telegram** (Canal de notificações automatizadas)
* **GitHub Actions** (Automação de rotinas e pipelines)