
from conexao_supabase import supabase

# Mapeamento estrito baseado nas regras e colunas exatas do seu banco de dados
ESTRUTURA_MERCADO = {
    "PETROLEO": {
        "indicadores": {"BZ=F": "Petróleo Brent", "USDBRL=X": "Dólar", "^BVSP": "Ibovespa"},
        "ativos": {
            "PETR4.SA": {"nome": "Petrobras", "classe": "Ação", "setor": "Energia"},
            "PRIO3.SA": {"nome": "Prio", "classe": "Ação", "setor": "Energia"}
        }
    },
    "MINERACAO": {
        "indicadores": {"TIO=F": "Minério de Ferro", "USDBRL=X": "Dólar", "^BVSP": "Ibovespa"},
        "ativos": {
            "VALE3.SA": {"nome": "Vale", "classe": "Ação", "setor": "Mineração"},
            "GGBR4.SA": {"nome": "Gerdau", "classe": "Ação", "setor": "Siderurgia"},
            "CSNA3.SA": {"nome": "Siderúrgica Nacional", "classe": "Ação", "setor": "Siderurgia"}
        }
    },
    "FINANCEIRO": {
        "indicadores": {"USDBRL=X": "Dólar", "^BVSP": "Ibovespa"},
        "ativos": {
            "ITUB4.SA": {"nome": "Itaú Unibanco", "classe": "Ação", "setor": "Bancos"},
            "BBDC4.SA": {"nome": "Bradesco", "classe": "Ação", "setor": "Bancos"},
            "BBAS3.SA": {"nome": "Banco do Brasil", "classe": "Ação", "setor": "Bancos"}
        }
    }
}

def vincular_base_conhecimento():
    print("🧠 Inicializando mapeamento de relacionamentos setoriais...")

    for setor, dados in ESTRUTURA_MERCADO.items():
        print(f"\n📂 Processando Setor: {setor}")
        
        # Garante que os indicadores existam na tabela cad_indicadores
        for ticker_ind, nome_ind in dados["indicadores"].items():
            res_ind = supabase.table("cad_indicadores").select("id").eq("ticker", ticker_ind).execute()
            if not res_ind.data:
                print(f"  ➕ Cadastrando novo indicador macro: {ticker_ind} ({nome_ind})")
                supabase.table("cad_indicadores").insert({
                    "ticker": ticker_ind,
                    "nome": nome_ind
                }).execute()

        for ticker_ativo, meta in dados["ativos"].items():
            # 1. Garante o cadastro na cad_ativos
            res_ativo = supabase.table("cad_ativos").select("id").eq("ticker", ticker_ativo).execute()
            
            if not res_ativo.data:
                print(f"  🏢 Cadastrando {ticker_ativo} ({meta['nome']}) em cad_ativos...")
                supabase.table("cad_ativos").insert({
                    "ticker": ticker_ativo, 
                    "nome": meta["nome"],
                    "classe": meta["classe"],
                    "setor": meta["setor"],
                    "moeda": "BRL"
                }).execute()
            else:
                print(f"  ✅ {ticker_ativo} já possui cadastro básico.")

            # 2. Amarra o texto do ativo ao ID do indicador correspondente
            for ticker_ind in dados["indicadores"].keys():
                res_ind = supabase.table("cad_indicadores").select("id").eq("ticker", ticker_ind).execute()
                
                if res_ind.data:
                    indicador_id = res_ind.data[0]['id']
                    
                    checa_vinculo = supabase.table("ativo_indicador_setorial")\
                        .select("ticker_ativo, indicador_id")\
                        .eq("ticker_ativo", ticker_ativo)\
                        .eq("indicador_id", indicador_id)\
                        .execute()
                    
                    if not checa_vinculo.data:
                        supabase.table("ativo_indicador_setorial").insert({
                            "ticker_ativo": ticker_ativo,
                            "indicador_id": indicador_id
                        }).execute()
                        print(f"    🔗 {ticker_ativo} vinculado ao driver {ticker_ind}")
                    else:
                        print(f"    🔗 Vínculo já existente para {ticker_ativo} e {ticker_ind}")

    print("\n🚀 Mapeamento concluído com sucesso e sem erros!")

if __name__ == "__main__":
    vincular_base_conhecimento()

