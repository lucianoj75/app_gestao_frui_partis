"""
Testes unitários para calcular_faturamento_mensal, calcular_top10_produtos,
calcular_metricas_dashboard, calcular_top3_mes e calcular_top3_ano.

Como executar (da raiz do projeto):
    pytest tests/test_relatorios.py -v
"""

import pandas as pd
import pytest


# =============================================================================
# Helpers (réplicas do app.py)
# =============================================================================

def formatar_df(valor):
    """Para uso em st.dataframe — texto puro, sem escape de $."""
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return valor


# =============================================================================
# Replicação das funções puras extraídas do app.py
# =============================================================================

def calcular_faturamento_mensal(df_vendas, ano):
    import calendar
    todos_meses = pd.DataFrame([
        {'Ano': ano, 'Mes': m, 'Mes_Nome': calendar.month_name[m]}
        for m in range(1, 13)
    ])
    df = df_vendas.copy()
    df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df['Ano'] = df['Data_dt'].dt.year
    df['Mes'] = df['Data_dt'].dt.month
    df = df[df['Ano'] == ano]
    agrup = df.groupby('Mes').agg(
        Qtd_Vendas=('Cod_Venda', 'count'),
        Faturamento=('Total', 'sum')
    ).reset_index()
    resultado = todos_meses.merge(agrup, on='Mes', how='left').fillna(0)
    resultado['Ticket_Medio'] = resultado.apply(
        lambda r: r['Faturamento'] / r['Qtd_Vendas'] if r['Qtd_Vendas'] > 0 else 0, axis=1
    )
    return resultado


def calcular_top10_produtos(df_itens, df_produtos=None):
    df = df_itens.copy()
    df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df['Ano_Mes'] = df['Data_dt'].dt.to_period('M')
    por_mes = df.groupby(['Produto', 'Ano_Mes']).agg(
        Qtd=('Qtd', 'sum'),
        Valor=('Total_Item', 'sum')
    ).reset_index()
    media_mensal = por_mes.groupby('Produto').agg(
        Qtd_Media=('Qtd', 'mean'),
        Valor_Medio=('Valor', 'mean'),
        Meses_Ativos=('Ano_Mes', 'count')
    ).reset_index()
    top10 = media_mensal.sort_values('Qtd_Media', ascending=False).head(10).reset_index(drop=True)
    top10.index += 1

    if df_produtos is not None and not df_produtos.empty and 'custo' in df_produtos.columns:
        df_custo = df_produtos[['Nome', 'custo']].drop_duplicates('Nome')
        top10 = top10.merge(df_custo, left_on='Produto', right_on='Nome', how='left').drop(columns='Nome')

        def _margem_pct(row):
            c, vm = row['custo'], row['Valor_Medio']
            if pd.isna(c) or c == 0 or vm == 0:
                return "Custo não cadastrado"
            pct = round(((vm - c) / vm) * 100, 1)
            return f"{pct:.1f}%".replace('.', ',')

        def _margem_r(row):
            c, vm = row['custo'], row['Valor_Medio']
            if pd.isna(c) or c == 0:
                return "Custo não cadastrado"
            return formatar_df(vm - c)

        top10['Margem_%']  = top10.apply(_margem_pct, axis=1)
        top10['Margem_R$'] = top10.apply(_margem_r,   axis=1)
        top10 = top10.drop(columns='custo')
    else:
        top10['Margem_%']  = "Custo não cadastrado"
        top10['Margem_R$'] = "Custo não cadastrado"

    return top10


def calcular_metricas_dashboard(df_vendas, mes, ano):
    df = df_vendas.copy()
    df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')

    mask_atual = (df['Data_dt'].dt.month == mes) & (df['Data_dt'].dt.year == ano)
    mes_ant, ano_ant = (12, ano - 1) if mes == 1 else (mes - 1, ano)
    mask_ant = (df['Data_dt'].dt.month == mes_ant) & (df['Data_dt'].dt.year == ano_ant)

    df_atual = df[mask_atual]
    df_ant   = df[mask_ant]

    fat_atual = float(df_atual['Total'].sum())
    qtd_atual = int(len(df_atual))
    tk_atual  = fat_atual / qtd_atual if qtd_atual > 0 else 0.0

    fat_ant   = float(df_ant['Total'].sum())
    qtd_ant   = int(len(df_ant))
    tk_ant    = fat_ant / qtd_ant if qtd_ant > 0 else 0.0

    tem_atual = qtd_atual > 0
    return {
        'faturamento':  fat_atual,
        'qtd_vendas':   qtd_atual,
        'ticket_medio': tk_atual,
        'delta_fat':    fat_atual - fat_ant if tem_atual else None,
        'delta_qtd':    qtd_atual - qtd_ant if tem_atual else None,
        'delta_ticket': tk_atual  - tk_ant  if tem_atual else None,
    }


def calcular_top3_mes(df_vendas, df_itens, mes, ano):
    df_v = df_vendas.copy()
    df_v['Data_dt'] = pd.to_datetime(df_v['Data'], dayfirst=True, errors='coerce')
    mask = (df_v['Data_dt'].dt.month == mes) & (df_v['Data_dt'].dt.year == ano)
    ids_mes = set(df_v[mask]['Cod_Venda'])

    if not ids_mes:
        return pd.DataFrame(columns=['Produto', 'Qtd. Vendida'])

    itens_mes = df_itens[df_itens['Cod_Venda'].isin(ids_mes)]
    agrup = itens_mes.groupby('Produto')['Qtd'].sum().reset_index()
    agrup.columns = ['Produto', 'Qtd. Vendida']
    return agrup.sort_values('Qtd. Vendida', ascending=False).head(3).reset_index(drop=True)


def calcular_top3_ano(df_vendas, df_itens, ano):
    df_v = df_vendas.copy()
    df_v['Data_dt'] = pd.to_datetime(df_v['Data'], dayfirst=True, errors='coerce')
    mask = df_v['Data_dt'].dt.year == ano
    ids_ano = set(df_v[mask]['Cod_Venda'])

    if not ids_ano:
        return pd.DataFrame(columns=['Produto', 'Qtd. Vendida'])

    itens_ano = df_itens[df_itens['Cod_Venda'].isin(ids_ano)]
    agrup = itens_ano.groupby('Produto')['Qtd'].sum().reset_index()
    agrup.columns = ['Produto', 'Qtd. Vendida']
    return agrup.sort_values('Qtd. Vendida', ascending=False).head(3).reset_index(drop=True)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def vendas_simples():
    return pd.DataFrame([
        {'Cod_Venda': 1, 'Data': '01/01/2025', 'Total': 100.0},
        {'Cod_Venda': 2, 'Data': '15/01/2025', 'Total': 200.0},
        {'Cod_Venda': 3, 'Data': '10/03/2025', 'Total': 150.0},
    ])


@pytest.fixture
def itens_simples():
    return pd.DataFrame([
        {'Produto': 'Maçã',  'Data': '01/01/2025', 'Qtd': 10, 'Total_Item': 50.0},
        {'Produto': 'Maçã',  'Data': '01/02/2025', 'Qtd': 20, 'Total_Item': 100.0},
        {'Produto': 'Pera',  'Data': '01/01/2025', 'Qtd': 5,  'Total_Item': 25.0},
        {'Produto': 'Uva',   'Data': '01/01/2025', 'Qtd': 3,  'Total_Item': 15.0},
    ])


@pytest.fixture
def produtos_com_custo():
    return pd.DataFrame([
        {'Nome': 'Maçã', 'custo': 3.0},
        {'Nome': 'Pera', 'custo': None},
        {'Nome': 'Uva',  'custo': 0.0},
    ])


@pytest.fixture
def dados_top3():
    df_v = pd.DataFrame([
        {'Cod_Venda': 1, 'Data': '01/06/2026', 'Total': 100.0},
        {'Cod_Venda': 2, 'Data': '15/06/2026', 'Total': 200.0},
    ])
    df_i = pd.DataFrame([
        {'Cod_Venda': 1, 'Produto': 'Maçã',   'Qtd': 10},
        {'Cod_Venda': 1, 'Produto': 'Pera',   'Qtd': 5},
        {'Cod_Venda': 2, 'Produto': 'Maçã',   'Qtd': 15},
        {'Cod_Venda': 2, 'Produto': 'Banana', 'Qtd': 3},
        {'Cod_Venda': 2, 'Produto': 'Uva',    'Qtd': 8},
    ])
    return df_v, df_i


@pytest.fixture
def dados_top3_ano():
    """Vendas distribuídas em dois meses do mesmo ano, com 4 produtos distintos."""
    df_v = pd.DataFrame([
        {'Cod_Venda': 1, 'Data': '05/01/2026', 'Total': 100.0},
        {'Cod_Venda': 2, 'Data': '10/02/2026', 'Total': 200.0},
        {'Cod_Venda': 3, 'Data': '15/02/2026', 'Total': 150.0},
    ])
    df_i = pd.DataFrame([
        {'Cod_Venda': 1, 'Produto': 'Maçã',   'Qtd': 10},
        {'Cod_Venda': 1, 'Produto': 'Pera',   'Qtd': 4},
        {'Cod_Venda': 2, 'Produto': 'Maçã',   'Qtd': 15},
        {'Cod_Venda': 2, 'Produto': 'Banana', 'Qtd': 6},
        {'Cod_Venda': 3, 'Produto': 'Uva',    'Qtd': 2},
        {'Cod_Venda': 3, 'Produto': 'Banana', 'Qtd': 9},
    ])
    return df_v, df_i


# =============================================================================
# Testes: calcular_faturamento_mensal
# =============================================================================

class TestCalcularFaturamentoMensal:

    def test_retorna_12_meses(self, vendas_simples):
        resultado = calcular_faturamento_mensal(vendas_simples, 2025)
        assert len(resultado) == 12

    def test_colunas_obrigatorias(self, vendas_simples):
        resultado = calcular_faturamento_mensal(vendas_simples, 2025)
        assert {'Mes', 'Mes_Nome', 'Qtd_Vendas', 'Faturamento', 'Ticket_Medio'}.issubset(resultado.columns)

    def test_faturamento_janeiro(self, vendas_simples):
        resultado = calcular_faturamento_mensal(vendas_simples, 2025)
        jan = resultado[resultado['Mes'] == 1].iloc[0]
        assert jan['Faturamento'] == pytest.approx(300.0)
        assert jan['Qtd_Vendas'] == 2

    def test_ticket_medio_janeiro(self, vendas_simples):
        resultado = calcular_faturamento_mensal(vendas_simples, 2025)
        jan = resultado[resultado['Mes'] == 1].iloc[0]
        assert jan['Ticket_Medio'] == pytest.approx(150.0)

    def test_mes_sem_vendas_retorna_zero(self, vendas_simples):
        resultado = calcular_faturamento_mensal(vendas_simples, 2025)
        fev = resultado[resultado['Mes'] == 2].iloc[0]
        assert fev['Faturamento'] == 0
        assert fev['Qtd_Vendas'] == 0
        assert fev['Ticket_Medio'] == 0

    def test_ano_diferente_retorna_tudo_zero(self, vendas_simples):
        resultado = calcular_faturamento_mensal(vendas_simples, 2020)
        assert resultado['Faturamento'].sum() == 0
        assert resultado['Qtd_Vendas'].sum() == 0

    def test_dataframe_vazio(self):
        df_vazio = pd.DataFrame(columns=['Cod_Venda', 'Data', 'Total'])
        resultado = calcular_faturamento_mensal(df_vazio, 2025)
        assert len(resultado) == 12
        assert resultado['Faturamento'].sum() == 0

    def test_venda_unica(self):
        df = pd.DataFrame([{'Cod_Venda': 1, 'Data': '05/06/2025', 'Total': 999.0}])
        resultado = calcular_faturamento_mensal(df, 2025)
        jun = resultado[resultado['Mes'] == 6].iloc[0]
        assert jun['Faturamento'] == pytest.approx(999.0)
        assert jun['Ticket_Medio'] == pytest.approx(999.0)

    def test_ticket_medio_zero_quando_sem_vendas(self, vendas_simples):
        resultado = calcular_faturamento_mensal(vendas_simples, 2025)
        meses_vazios = resultado[resultado['Qtd_Vendas'] == 0]
        assert (meses_vazios['Ticket_Medio'] == 0).all()

    def test_multiplas_vendas_mesmo_mes(self):
        df = pd.DataFrame([
            {'Cod_Venda': i, 'Data': '10/04/2025', 'Total': 50.0}
            for i in range(1, 5)
        ])
        resultado = calcular_faturamento_mensal(df, 2025)
        abr = resultado[resultado['Mes'] == 4].iloc[0]
        assert abr['Qtd_Vendas'] == 4
        assert abr['Faturamento'] == pytest.approx(200.0)
        assert abr['Ticket_Medio'] == pytest.approx(50.0)


# =============================================================================
# Testes: calcular_top10_produtos
# =============================================================================

class TestCalcularTop10Produtos:

    def test_colunas_obrigatorias(self, itens_simples):
        resultado = calcular_top10_produtos(itens_simples)
        assert {'Produto', 'Qtd_Media', 'Valor_Medio', 'Meses_Ativos',
                'Margem_%', 'Margem_R$'}.issubset(resultado.columns)

    def test_ordenado_por_qtd_media_decrescente(self, itens_simples):
        resultado = calcular_top10_produtos(itens_simples)
        qtds = resultado['Qtd_Media'].tolist()
        assert qtds == sorted(qtds, reverse=True)

    def test_indice_comeca_em_1(self, itens_simples):
        resultado = calcular_top10_produtos(itens_simples)
        assert resultado.index[0] == 1

    def test_maca_lidera_ranking(self, itens_simples):
        resultado = calcular_top10_produtos(itens_simples)
        assert resultado.iloc[0]['Produto'] == 'Maçã'

    def test_maximo_10_produtos(self):
        linhas = []
        for i in range(1, 16):
            linhas.append({'Produto': f'Prod{i}', 'Data': '01/01/2025', 'Qtd': i, 'Total_Item': float(i * 10)})
        df = pd.DataFrame(linhas)
        resultado = calcular_top10_produtos(df)
        assert len(resultado) <= 10

    def test_dataframe_vazio(self):
        df_vazio = pd.DataFrame(columns=['Produto', 'Data', 'Qtd', 'Total_Item'])
        resultado = calcular_top10_produtos(df_vazio)
        assert len(resultado) == 0

    def test_produto_unico(self):
        df = pd.DataFrame([{'Produto': 'Laranja', 'Data': '01/03/2025', 'Qtd': 7, 'Total_Item': 35.0}])
        resultado = calcular_top10_produtos(df)
        assert len(resultado) == 1
        assert resultado.iloc[0]['Produto'] == 'Laranja'
        assert resultado.iloc[0]['Qtd_Media'] == pytest.approx(7.0)

    def test_qtd_media_calculada_por_mes(self):
        df = pd.DataFrame([
            {'Produto': 'Banana', 'Data': '01/01/2025', 'Qtd': 10, 'Total_Item': 50.0},
            {'Produto': 'Banana', 'Data': '01/02/2025', 'Qtd': 20, 'Total_Item': 100.0},
        ])
        resultado = calcular_top10_produtos(df)
        banana = resultado[resultado['Produto'] == 'Banana'].iloc[0]
        assert banana['Qtd_Media'] == pytest.approx(15.0)
        assert banana['Meses_Ativos'] == 2

    def test_meses_ativos_corretos(self, itens_simples):
        resultado = calcular_top10_produtos(itens_simples)
        maca = resultado[resultado['Produto'] == 'Maçã'].iloc[0]
        assert maca['Meses_Ativos'] == 2

    def test_top10_colunas_com_margem(self, itens_simples, produtos_com_custo):
        resultado = calcular_top10_produtos(itens_simples, produtos_com_custo)
        assert 'Margem_%'  in resultado.columns
        assert 'Margem_R$' in resultado.columns

    def test_top10_margem_calculada(self, itens_simples, produtos_com_custo):
        # Maçã: Valor_Medio = (50 + 100) / 2 = 75.0; custo = 3.0
        # Margem% = (75 - 3) / 75 * 100 = 96.0%   Margem_R$ = 72.0
        resultado = calcular_top10_produtos(itens_simples, produtos_com_custo)
        maca = resultado[resultado['Produto'] == 'Maçã'].iloc[0]
        assert maca['Margem_%']  == '96,0%'
        assert maca['Margem_R$'] == formatar_df(72.0)

    def test_top10_sem_custo(self, itens_simples, produtos_com_custo):
        # Pera tem custo = None
        resultado = calcular_top10_produtos(itens_simples, produtos_com_custo)
        pera = resultado[resultado['Produto'] == 'Pera'].iloc[0]
        assert pera['Margem_%']  == 'Custo não cadastrado'
        assert pera['Margem_R$'] == 'Custo não cadastrado'

    def test_top10_custo_zero(self, itens_simples, produtos_com_custo):
        # Uva tem custo = 0
        resultado = calcular_top10_produtos(itens_simples, produtos_com_custo)
        uva = resultado[resultado['Produto'] == 'Uva'].iloc[0]
        assert uva['Margem_%']  == 'Custo não cadastrado'
        assert uva['Margem_R$'] == 'Custo não cadastrado'


# =============================================================================
# Testes: calcular_metricas_dashboard
# =============================================================================

class TestCalcularMetricasDashboard:

    def test_metricas_mes_com_vendas(self):
        df = pd.DataFrame([
            {'Cod_Venda': 1, 'Data': '01/06/2026', 'Total': 300.0},
            {'Cod_Venda': 2, 'Data': '15/06/2026', 'Total': 200.0},
        ])
        result = calcular_metricas_dashboard(df, 6, 2026)
        assert result['faturamento']  == pytest.approx(500.0)
        assert result['qtd_vendas']   == 2
        assert result['ticket_medio'] == pytest.approx(250.0)

    def test_metricas_mes_sem_vendas(self):
        df = pd.DataFrame([
            {'Cod_Venda': 1, 'Data': '01/01/2026', 'Total': 100.0},
        ])
        result = calcular_metricas_dashboard(df, 6, 2026)
        assert result['faturamento']  == 0
        assert result['qtd_vendas']   == 0
        assert result['delta_fat']    is None
        assert result['delta_qtd']    is None

    def test_metricas_ticket_zero_sem_vendas(self):
        df = pd.DataFrame(columns=['Cod_Venda', 'Data', 'Total'])
        result = calcular_metricas_dashboard(df, 6, 2026)
        assert result['ticket_medio'] == 0


# =============================================================================
# Testes: calcular_top3_mes
# =============================================================================

class TestCalcularTop3Mes:

    def test_top3_maximo_3_produtos(self, dados_top3):
        df_v, df_i = dados_top3
        resultado = calcular_top3_mes(df_v, df_i, 6, 2026)
        assert len(resultado) <= 3

    def test_top3_ordenacao(self, dados_top3):
        df_v, df_i = dados_top3
        resultado = calcular_top3_mes(df_v, df_i, 6, 2026)
        qtds = resultado['Qtd. Vendida'].tolist()
        assert qtds == sorted(qtds, reverse=True)

    def test_top3_mes_sem_vendas(self, dados_top3):
        df_v, df_i = dados_top3
        resultado = calcular_top3_mes(df_v, df_i, 1, 2026)
        assert resultado.empty
        assert list(resultado.columns) == ['Produto', 'Qtd. Vendida']

    def test_top3_produto_lider(self, dados_top3):
        df_v, df_i = dados_top3
        # Maçã: Cod_Venda 1 (qtd=10) + Cod_Venda 2 (qtd=15) = 25
        resultado = calcular_top3_mes(df_v, df_i, 6, 2026)
        assert resultado.iloc[0]['Produto'] == 'Maçã'
        assert resultado.iloc[0]['Qtd. Vendida'] == 25


# =============================================================================
# Testes: calcular_top3_ano
# =============================================================================

class TestCalcularTop3Ano:

    def test_top3_ano_maximo_3(self, dados_top3_ano):
        """Nunca retorna mais de 3 linhas mesmo com 4 produtos distintos."""
        df_v, df_i = dados_top3_ano
        resultado = calcular_top3_ano(df_v, df_i, 2026)
        assert len(resultado) <= 3

    def test_top3_ano_ordenacao(self, dados_top3_ano):
        """Produto com maior quantidade aparece primeiro."""
        df_v, df_i = dados_top3_ano
        resultado = calcular_top3_ano(df_v, df_i, 2026)
        qtds = resultado['Qtd. Vendida'].tolist()
        assert qtds == sorted(qtds, reverse=True)

    def test_top3_ano_sem_vendas(self, dados_top3_ano):
        """Retorna DataFrame vazio sem erro quando o ano não tem vendas."""
        df_v, df_i = dados_top3_ano
        resultado = calcular_top3_ano(df_v, df_i, 2020)
        assert resultado.empty
        assert list(resultado.columns) == ['Produto', 'Qtd. Vendida']

    def test_top3_ano_produto_lider(self, dados_top3_ano):
        """Maçã soma 25 (10+15) e deve aparecer em primeiro lugar."""
        df_v, df_i = dados_top3_ano
        resultado = calcular_top3_ano(df_v, df_i, 2026)
        assert resultado.iloc[0]['Produto'] == 'Maçã'
        assert resultado.iloc[0]['Qtd. Vendida'] == 25

    def test_top3_ano_soma_correta(self, dados_top3_ano):
        """Banana acumula qtd de dois meses distintos: 6 + 9 = 15."""
        df_v, df_i = dados_top3_ano
        resultado = calcular_top3_ano(df_v, df_i, 2026)
        banana = resultado[resultado['Produto'] == 'Banana']
        assert not banana.empty
        assert banana.iloc[0]['Qtd. Vendida'] == 15
