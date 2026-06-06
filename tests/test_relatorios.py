"""
Testes unitários para calcular_faturamento_mensal e calcular_top10_produtos.

Como executar (da raiz do projeto):
    pytest tests/test_relatorios.py -v
"""

import pandas as pd
import pytest


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


def calcular_top10_produtos(df_itens):
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
    return top10


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
        assert list(resultado.columns) == ['Produto', 'Qtd_Media', 'Valor_Medio', 'Meses_Ativos']

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
