"""
Análise de Carteira BNDES - Saneamento
Credit Scoring Model — NPL Portfolio Analysis (v4.2)
"""

import pandas as pd
import numpy as np
import os


# ============================================================================
# CONFIGURAÇÃO DO MODELO - PESOS (V4.1)
# ============================================================================

PESOS = {
    'penhoras_ativas': 0.10,              # 10%
    'endividamento': 0.15,                # 15%
    'situacao_cnpj': 0.15,               # 15%
    'devedores_solidarios': 0.10,         # 10%
    'multiplo_crescimento': 0.10,         # 10%
    'rj_falencia': 0.15,                 # 15%
    'uf': 0.10,                          # 10%
    'bens': 0.05,                        # 5%
    'acoes_ativas': 0.05,                # 5%
    'imoveis_rurais': 0.05,             # 5%
}

REGIOES_FAVORAVEIS = {'SP', 'RJ', 'MG', 'ES', 'PR', 'SC', 'RS', 'GO', 'MT', 'MS', 'DF'}

TAXA_RECUPERACAO = {
    'Excelente (8.0-10.0)': 0.70,
    'Muito Bom (7.0-8.0)': 0.50,
    'Bom (6.0-7.0)': 0.30,
    'Regular (5.0-6.0)': 0.15,
    'Baixo (0.0-5.0)': 0.05
}

COL_SALDO = 'Saldo contábil'
COL_VALOR_CAUSA = 'Valor da Causa'
COL_VALOR_ATUALIZADO = 'Valor atualizado - 24/02/2026'
COL_PGFN = 'Pgfn'
COL_DEVEDOR = 'DEVEDOR PRINCIPAL'
COL_CNPJ = 'CNPJ'
COL_ID = 'ID'


# ============================================================================
# MERGE DAS BASES
# ============================================================================

def carregar_e_mesclar(arquivo_score, arquivo_saneamento):
    """
    Carrega Base_para_score e complementa com:
    - Aba 'Base': dados qualitativos (CNPJ, UF, RJ, penhoras, etc.)
    - Aba 'Imóveis': contagem de bens
    - Aba 'DSOs': contagem de devedores solidários
    """
    # 1. Base principal
    df_score = pd.read_excel(arquivo_score)
    df_score.columns = df_score.columns.str.strip()
    print(f"   Base Score: {len(df_score)} devedores")
    
    # 2. Aba Base (dados qualitativos)
    df_san = pd.read_excel(arquivo_saneamento, sheet_name='Base')
    df_san.columns = df_san.columns.str.strip()
    
    colunas_san = {
        'ID': 'ID',
        'Situação cadastral CNPJ': 'Situacao_CNPJ',
        'UF processos': 'UF',
        'RJ/Falência': 'RJ_Falencia',
        '#Penhoras ativas': 'Num_Penhoras_Ativas',
        '#Imóveis rurais': 'Num_Imoveis_Rurais',
        '#Processos ativos': 'Processos_Ativos',
    }
    df_san_sel = df_san[[c for c in colunas_san.keys() if c in df_san.columns]].copy()
    df_san_sel = df_san_sel.rename(columns=colunas_san)
    
    # 3. Aba Imóveis (contagem de bens)
    try:
        df_imoveis = pd.read_excel(arquivo_saneamento, sheet_name='Imóveis')
        df_imoveis.columns = df_imoveis.columns.str.strip()
        bens_count = df_imoveis.groupby('ID').size().reset_index(name='Quantidade_Bens')
        print(f"   Aba Imóveis: {len(bens_count)} devedores com bens")
    except:
        bens_count = pd.DataFrame(columns=['ID', 'Quantidade_Bens'])
    
    # 4. Aba DSOs (Devedores Solidários)
    try:
        df_dsos = pd.read_excel(arquivo_saneamento, sheet_name='DSOs')
        df_dsos.columns = df_dsos.columns.str.strip()
        
        # Contar todos os DSOs por devedor
        # Idealmente filtraríamos apenas PF vivas e PJ ativas,
        # mas a base não tem status de vida/atividade dos DSOs.
        # Contamos todos; quando o dado for enriquecido, basta filtrar aqui.
        dso_count = df_dsos.groupby('ID_Devedor').size().reset_index(name='Num_DSOs')
        dso_count = dso_count.rename(columns={'ID_Devedor': 'ID'})
        print(f"   Aba DSOs: {len(dso_count)} devedores com solidários ({df_dsos.shape[0]} DSOs total)")
    except:
        dso_count = pd.DataFrame(columns=['ID', 'Num_DSOs'])
        print("   ⚠️ Aba DSOs não encontrada")
    
    # 5. Merge
    df = df_score.merge(df_san_sel, on='ID', how='left')
    df = df.merge(bens_count, on='ID', how='left')
    df = df.merge(dso_count, on='ID', how='left')
    df['Quantidade_Bens'] = df['Quantidade_Bens'].fillna(0).astype(int)
    df['Num_DSOs'] = df['Num_DSOs'].fillna(0).astype(int)
    
    # Log
    for col in ['Situacao_CNPJ', 'UF', 'RJ_Falencia', 'Num_Penhoras_Ativas', 
                'Num_Imoveis_Rurais', 'Quantidade_Bens', 'Num_DSOs', 'Processos_Ativos']:
        if col in df.columns:
            print(f"   ✓ {col}: {df[col].notna().sum()}/{len(df)} preenchidos")
    
    return df


# ============================================================================
# FUNÇÕES DE CÁLCULO
# ============================================================================

def nota_penhoras(valor):
    if pd.isna(valor): return 5.0
    v = int(valor)
    if v == 0: return 0.0
    elif v == 1: return 3.0
    elif v == 2: return 5.0
    elif v == 3: return 6.5
    elif v == 4: return 8.0
    else: return 10.0

def nota_imoveis_rurais(valor):
    if pd.isna(valor): return 5.0
    return 10.0 if valor > 0 else 0.0

def nota_multiplo_crescimento(valor_atualizado, valor_causa):
    if pd.isna(valor_atualizado) or pd.isna(valor_causa): return 5.0
    if valor_causa == 0 or valor_atualizado == 0: return 5.0
    m = valor_atualizado / valor_causa
    if m <= 3.0: return 10.0
    elif m <= 6.0: return 8.0
    elif m <= 10.0: return 6.5
    elif m <= 15.0: return 5.0
    elif m <= 25.0: return 3.0
    elif m <= 50.0: return 1.5
    else: return 0.0

def nota_situacao_cnpj(situacao):
    if pd.isna(situacao): return 5.0
    s = str(situacao).upper()
    if 'ATIVA' in s: return 10.0
    elif any(x in s for x in ['INAPTA', 'BAIXADA', 'CANCELADA']): return 0.0
    return 5.0

def nota_rj_falencia(valor):
    if pd.isna(valor): return 5.0
    v = str(valor).upper().strip()
    if v in ['NÃO', 'NAO', 'N', '-', '_', '']: return 10.0
    if any(x in v for x in ['SIM', 'RJ', 'FALÊNCIA', 'FALENCIA', 'CONCORDATA']): return 0.0
    return 5.0

def nota_endividamento(pgfn, valor_causa):
    if pd.isna(pgfn) or pd.isna(valor_causa): return 5.0
    if valor_causa == 0: return 10.0 if pgfn == 0 else 0.0
    if pgfn > 1e12: return 0.0
    if pgfn == 0: return 10.0
    m = pgfn / valor_causa
    if m <= 0.01: return 10.0
    elif m <= 0.1: return 8.0
    elif m <= 0.5: return 6.5
    elif m <= 1.0: return 5.0
    elif m <= 5.0: return 3.0
    elif m <= 50.0: return 1.5
    else: return 0.0

def nota_acoes_ativas(valor):
    if pd.isna(valor): return 5.0
    v = int(valor)
    if v == 0: return 0.0
    elif v == 1: return 3.0
    elif v == 2: return 5.0
    elif v == 3: return 6.5
    elif v == 4: return 8.0
    else: return 10.0

def nota_uf(uf):
    if pd.isna(uf): return 5.0
    u = str(uf).upper().strip()
    if u in ['-', '_', '', 'NAN']: return 5.0
    if u in REGIOES_FAVORAVEIS: return 10.0
    return 0.0

def nota_bens(valor):
    if pd.isna(valor) or valor == 0: return 0.0
    elif valor == 1: return 4.0
    elif valor == 2: return 6.0
    elif valor <= 4: return 8.0
    else: return 10.0

def nota_devedores_solidarios(num_dsos):
    """
    NOVO CRITÉRIO: Devedores Solidários
    Quantidade de devedores solidários (empresas ativas ou PF vivas).
    Quanto mais, maior a chance de recuperação (mais patrimônio executável).
    Nota de 0 a 10, distribuição gradual.
    
    Calibrado para a base real (mediana 3, P75 4, max 16):
    """
    if pd.isna(num_dsos) or num_dsos == 0:
        return 0.0
    elif num_dsos == 1:
        return 3.0
    elif num_dsos == 2:
        return 5.0
    elif num_dsos == 3:
        return 6.0
    elif num_dsos == 4:
        return 7.0
    elif num_dsos <= 6:
        return 8.0
    elif num_dsos <= 8:
        return 9.0
    else:
        return 10.0


# ============================================================================
# CALCULAR SCORE
# ============================================================================

def calcular_score(df):
    r = df.copy()
    
    # Múltiplos de referência
    r['multiplo_crescimento'] = (r[COL_VALOR_ATUALIZADO] / r[COL_VALOR_CAUSA]).round(2)
    r['ratio_pgfn_causa'] = r.apply(
        lambda row: round(row[COL_PGFN] / row[COL_VALOR_CAUSA], 4) 
        if row[COL_VALOR_CAUSA] > 0 else np.nan, axis=1)
    
    # Notas individuais
    r['nota_penhoras'] = r['Num_Penhoras_Ativas'].apply(nota_penhoras)
    r['nota_imoveis'] = r['Num_Imoveis_Rurais'].apply(nota_imoveis_rurais)
    r['nota_multiplo_crescimento'] = r.apply(
        lambda row: nota_multiplo_crescimento(row[COL_VALOR_ATUALIZADO], row[COL_VALOR_CAUSA]), axis=1)
    r['nota_situacao_cnpj'] = r['Situacao_CNPJ'].apply(nota_situacao_cnpj)
    r['nota_rj_falencia'] = r['RJ_Falencia'].apply(nota_rj_falencia)
    r['nota_endividamento'] = r.apply(
        lambda row: nota_endividamento(row[COL_PGFN], row[COL_VALOR_CAUSA]), axis=1)
    r['nota_acoes_ativas'] = r['Processos_Ativos'].apply(nota_acoes_ativas) if 'Processos_Ativos' in r.columns else 5.0
    r['nota_uf'] = r['UF'].apply(nota_uf) if 'UF' in r.columns else 5.0
    r['nota_bens'] = r['Quantidade_Bens'].apply(nota_bens)
    r['nota_devedores_solidarios'] = r['Num_DSOs'].apply(nota_devedores_solidarios)
    
    # Nota final ponderada
    r['nota_final'] = (
        PESOS['penhoras_ativas']       * r['nota_penhoras'] +
        PESOS['endividamento']         * r['nota_endividamento'] +
        PESOS['situacao_cnpj']         * r['nota_situacao_cnpj'] +
        PESOS['devedores_solidarios']  * r['nota_devedores_solidarios'] +
        PESOS['multiplo_crescimento']  * r['nota_multiplo_crescimento'] +
        PESOS['rj_falencia']           * r['nota_rj_falencia'] +
        PESOS['uf']                    * r['nota_uf'] +
        PESOS['bens']                  * r['nota_bens'] +
        PESOS['acoes_ativas']          * r['nota_acoes_ativas'] +
        PESOS['imoveis_rurais']        * r['nota_imoveis']
    ).round(2)
    
    # Faixas e ranking
    def classificar(nota):
        if nota >= 8.0: return 'Excelente (8.0-10.0)'
        elif nota >= 7.0: return 'Muito Bom (7.0-8.0)'
        elif nota >= 6.0: return 'Bom (6.0-7.0)'
        elif nota >= 5.0: return 'Regular (5.0-6.0)'
        else: return 'Baixo (0.0-5.0)'
    
    r['faixa'] = r['nota_final'].apply(classificar)
    r = r.sort_values('nota_final', ascending=False).reset_index(drop=True)
    r['ranking'] = range(1, len(r) + 1)
    
    return r


# ============================================================================
# ANÁLISE E EXPORTAÇÃO
# ============================================================================

def analisar_e_exportar(df, arquivo_output):
    total = len(df)
    saldo_total = df[COL_SALDO].sum()
    
    print(f"\n{'='*80}")
    print(f"📊 ANÁLISE DA CARTEIRA - v4.2")
    print(f"{'='*80}")
    print(f"\n   Devedores: {total}")
    print(f"   Saldo total: R$ {saldo_total:,.2f}")
    print(f"   Nota mín/média/mediana/máx: {df['nota_final'].min():.2f} / "
          f"{df['nota_final'].mean():.2f} / {df['nota_final'].median():.2f} / "
          f"{df['nota_final'].max():.2f}")
    
    # Distribuição
    print(f"\n   DISTRIBUIÇÃO POR FAIXA:")
    resumo_faixas = []
    for faixa in ['Excelente (8.0-10.0)', 'Muito Bom (7.0-8.0)', 'Bom (6.0-7.0)', 
                  'Regular (5.0-6.0)', 'Baixo (0.0-5.0)']:
        filtro = df['faixa'] == faixa
        qtd = filtro.sum()
        saldo = df[filtro][COL_SALDO].sum()
        taxa = TAXA_RECUPERACAO[faixa]
        valor_esp = saldo * taxa
        resumo_faixas.append({
            'Faixa': faixa, 'Quantidade': qtd, '% Qtd': round(qtd/total*100, 1),
            'Saldo Total': saldo, '% Saldo': round(saldo/saldo_total*100, 1),
            'Taxa Recuperação': taxa, 'Valor Esperado': valor_esp
        })
        print(f"   {faixa}: {qtd} ({qtd/total*100:.1f}%) | R$ {saldo:,.0f} ({saldo/saldo_total*100:.1f}%)")
    
    valor_total_esp = sum(f['Valor Esperado'] for f in resumo_faixas)
    taxa_global = valor_total_esp / saldo_total * 100
    print(f"\n   Recuperação esperada: R$ {valor_total_esp:,.2f} ({taxa_global:.1f}%)")
    
    # Cenários
    cenarios = []
    print(f"\n   CENÁRIOS:")
    for desagio in range(95, 25, -5):
        vc = saldo_total * (1 - desagio/100)
        lucro = valor_total_esp - vc
        roi = lucro / vc * 100 if vc > 0 else 0
        s = "✓" if lucro > 0 else "✗"
        cenarios.append({'Deságio': f"{desagio}%", 'Valor Compra': vc,
                        'Recuperação': valor_total_esp, 'Resultado': lucro, 'ROI': roi})
        print(f"   {desagio}% → R$ {vc:,.0f} | Resultado: R$ {lucro:,.0f} | ROI: {roi:.1f}% {s}")
    
    # Exportar
    print(f"\n💾 Exportando: {arquivo_output}")
    with pd.ExcelWriter(arquivo_output, engine='openpyxl') as writer:
        
        pd.DataFrame([{'Critério': k, 'Peso': f"{v*100:.0f}%"} for k, v in PESOS.items()] + 
                     [{'Critério': 'TOTAL', 'Peso': '100%'}]
        ).to_excel(writer, sheet_name='Pesos', index=False)
        
        pd.DataFrame([
            {'Métrica': 'Total de Devedores', 'Valor': total},
            {'Métrica': 'Saldo Contábil Total', 'Valor': f"R$ {saldo_total:,.2f}"},
            {'Métrica': 'Valor Esperado Recuperação', 'Valor': f"R$ {valor_total_esp:,.2f}"},
            {'Métrica': 'Taxa Recuperação', 'Valor': f"{taxa_global:.1f}%"},
        ]).to_excel(writer, sheet_name='Resumo', index=False)
        
        pd.DataFrame(resumo_faixas).to_excel(writer, sheet_name='Faixas', index=False)
        pd.DataFrame(cenarios).to_excel(writer, sheet_name='Cenários', index=False)
        
        colunas_output = [
            COL_ID, COL_DEVEDOR, COL_CNPJ, COL_SALDO, COL_VALOR_CAUSA,
            COL_VALOR_ATUALIZADO, COL_PGFN,
            'Situacao_CNPJ', 'UF', 'RJ_Falencia',
            'Num_Penhoras_Ativas', 'Num_Imoveis_Rurais', 'Quantidade_Bens',
            'Num_DSOs', 'Processos_Ativos',
            'multiplo_crescimento', 'ratio_pgfn_causa',
            'nota_penhoras', 'nota_imoveis', 'nota_multiplo_crescimento',
            'nota_situacao_cnpj', 'nota_rj_falencia', 'nota_endividamento',
            'nota_acoes_ativas', 'nota_uf', 'nota_bens', 'nota_devedores_solidarios',
            'nota_final', 'faixa', 'ranking'
        ]
        cols_exist = [c for c in colunas_output if c in df.columns]
        df[cols_exist].to_excel(writer, sheet_name='Ranking Completo', index=False)
        df[cols_exist].head(20).to_excel(writer, sheet_name='Top 20', index=False)
    
    print("✅ Relatório salvo!")


# ============================================================================
# EXECUÇÃO PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    print("="*80)
    print("ANÁLISE DE CARTEIRA BNDES - SANEAMENTO")
    print("VERSÃO 4.1 - Com Devedores Solidários")
    print("="*80)
    
    ARQUIVO_SCORE = "Base_para_score.xlsx"
    ARQUIVO_SANEAMENTO = "Saneamento_BNDES.xlsx"
    ARQUIVO_OUTPUT = "analise_carteira_RESULTADO_V4.1.xlsx"
    
    print(f"\n📂 Carregando e mesclando bases...")
    df = carregar_e_mesclar(ARQUIVO_SCORE, ARQUIVO_SANEAMENTO)
    print(f"\n✅ Base mesclada: {len(df)} devedores")
    
    print(f"\n⏳ Calculando scores...")
    resultado = calcular_score(df)
    print(f"✅ Score calculado!")
    
    analisar_e_exportar(resultado, ARQUIVO_OUTPUT)
    
    print(f"\n{'='*80}")
    print("✅ ANÁLISE CONCLUÍDA!")
    print("="*80)
