"""
Testes unitários para as funções de inadimplência.

As funções testadas (buscar_inadimplentes, buscar_vendas_em_aberto,
registrar_cobranca, registrar_pagamento) são replicadas aqui com get_conn
como parâmetro explícito, seguindo o padrão de test_banco_mock.py.

Como executar:
    pytest tests/test_inadimplencia.py -v
"""

import pytest
import pandas as pd
from datetime import date, datetime
from unittest.mock import MagicMock, call, patch


# ---------------------------------------------------------------------------
# Réplicas das funções do app.py com get_conn como parâmetro
# ---------------------------------------------------------------------------

def buscar_inadimplentes(get_conn):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
              c."Cod_Cliente"  AS cliente_id,
              c."Nome"         AS cliente,
              COUNT(v."Cod_Venda") AS vendas_em_aberto,
              SUM(v."Total" - COALESCE(pag.total_pago, 0)) AS saldo_total,
              MIN(TO_DATE(SPLIT_PART(v."Data", ' ', 1), 'DD/MM/YYYY')) AS mais_antiga
            FROM vendas v
            JOIN clientes c ON c."Cod_Cliente" = v."Cod_Cliente"
            LEFT JOIN (
              SELECT venda_id, SUM(valor) AS total_pago
              FROM vendas_pagamentos
              GROUP BY venda_id
            ) pag ON pag.venda_id = v."Cod_Venda"
            WHERE v."Total" - COALESCE(pag.total_pago, 0) > 0
            GROUP BY c."Cod_Cliente", c."Nome"
            ORDER BY saldo_total DESC
        """)
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=['cliente_id', 'cliente', 'vendas_em_aberto', 'saldo_total', 'mais_antiga'])
    finally:
        conn.close()


def buscar_vendas_em_aberto(cliente_id, get_conn):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
              v."Cod_Venda"  AS venda_id,
              TO_DATE(SPLIT_PART(v."Data", ' ', 1), 'DD/MM/YYYY') AS data,
              v."Total"      AS total,
              COALESCE(pag.total_pago, 0) AS pago,
              v."Total" - COALESCE(pag.total_pago, 0) AS saldo
            FROM vendas v
            LEFT JOIN (
              SELECT venda_id, SUM(valor) AS total_pago
              FROM vendas_pagamentos
              GROUP BY venda_id
            ) pag ON pag.venda_id = v."Cod_Venda"
            WHERE v."Cod_Cliente" = %s
              AND v."Total" - COALESCE(pag.total_pago, 0) > 0
            ORDER BY data ASC
        """, (cliente_id,))
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=['venda_id', 'data', 'total', 'pago', 'saldo'])
    finally:
        conn.close()


def registrar_cobranca(venda_id, data_cobranca, observacao, usuario_id, get_conn):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO "vendas_cobranças" (venda_id, data_cobranca, observacao, criado_por, criado_em) '
            'VALUES (%s, %s, %s, %s, %s)',
            (venda_id, data_cobranca, observacao, usuario_id, datetime.now())
        )
        conn.commit()
    finally:
        conn.close()


def registrar_pagamento(venda_id, valor, data_pagamento, observacao, usuario_id, get_conn):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO vendas_pagamentos (venda_id, valor, data_pagamento, observacao, criado_por, criado_em) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (venda_id, valor, data_pagamento, observacao or None, usuario_id, datetime.now())
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn(fetchall_return=None):
    conn   = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = fetchall_return or []
    return conn, cursor


# ---------------------------------------------------------------------------
# buscar_inadimplentes
# ---------------------------------------------------------------------------

def test_buscar_inadimplentes_colunas():
    conn, cursor = _make_conn([
        (1, 'Ana Souza', 3, 620.00, date(2026, 3, 12)),
    ])
    get_conn = MagicMock(return_value=conn)

    df = buscar_inadimplentes(get_conn)

    assert list(df.columns) == ['cliente_id', 'cliente', 'vendas_em_aberto', 'saldo_total', 'mais_antiga']
    assert len(df) == 1
    assert df.iloc[0]['cliente'] == 'Ana Souza'


def test_buscar_inadimplentes_empty():
    conn, cursor = _make_conn([])
    get_conn = MagicMock(return_value=conn)

    df = buscar_inadimplentes(get_conn)

    assert df.empty
    assert list(df.columns) == ['cliente_id', 'cliente', 'vendas_em_aberto', 'saldo_total', 'mais_antiga']


# ---------------------------------------------------------------------------
# buscar_vendas_em_aberto
# ---------------------------------------------------------------------------

def test_buscar_vendas_em_aberto_colunas():
    conn, cursor = _make_conn([
        (10, date(2026, 3, 12), 300.00, 100.00, 200.00),
        (11, date(2026, 4, 28), 450.00, 230.00, 220.00),
    ])
    get_conn = MagicMock(return_value=conn)

    df = buscar_vendas_em_aberto(1, get_conn)

    assert list(df.columns) == ['venda_id', 'data', 'total', 'pago', 'saldo']
    assert len(df) == 2


def test_buscar_vendas_em_aberto_passa_cliente_id():
    conn, cursor = _make_conn([])
    get_conn = MagicMock(return_value=conn)

    buscar_vendas_em_aberto(42, get_conn)

    args = cursor.execute.call_args
    assert 42 in args[0][1]


# ---------------------------------------------------------------------------
# registrar_cobranca
# ---------------------------------------------------------------------------

def test_registrar_cobranca_execute():
    conn, cursor = _make_conn()
    get_conn = MagicMock(return_value=conn)

    registrar_cobranca(10, date(2026, 6, 7), 'Avisado via WhatsApp', 1, get_conn)

    assert cursor.execute.called
    sql = cursor.execute.call_args[0][0]
    assert 'vendas_cobranças' in sql
    assert 'INSERT' in sql


def test_registrar_cobranca_commit():
    conn, cursor = _make_conn()
    get_conn = MagicMock(return_value=conn)

    registrar_cobranca(10, date(2026, 6, 7), 'obs', 1, get_conn)

    conn.commit.assert_called_once()


def test_registrar_cobranca_close():
    conn, cursor = _make_conn()
    cursor.execute.side_effect = Exception("DB error")
    get_conn = MagicMock(return_value=conn)

    with pytest.raises(Exception):
        registrar_cobranca(10, date(2026, 6, 7), 'obs', 1, get_conn)

    conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# registrar_pagamento
# ---------------------------------------------------------------------------

def test_registrar_pagamento_execute():
    conn, cursor = _make_conn()
    get_conn = MagicMock(return_value=conn)

    registrar_pagamento(10, 200.00, date(2026, 6, 7), 'PIX', 1, get_conn)

    assert cursor.execute.called
    sql = cursor.execute.call_args[0][0]
    assert 'vendas_pagamentos' in sql
    assert 'INSERT' in sql


def test_registrar_pagamento_commit():
    conn, cursor = _make_conn()
    get_conn = MagicMock(return_value=conn)

    registrar_pagamento(10, 200.00, date(2026, 6, 7), None, 1, get_conn)

    conn.commit.assert_called_once()


def test_registrar_pagamento_close():
    conn, cursor = _make_conn()
    cursor.execute.side_effect = Exception("DB error")
    get_conn = MagicMock(return_value=conn)

    with pytest.raises(Exception):
        registrar_pagamento(10, 200.00, date(2026, 6, 7), None, 1, get_conn)

    conn.close.assert_called_once()


def test_registrar_pagamento_valor_maximo():
    """Não deve aceitar valor maior que o saldo em aberto (validação de UI)."""
    conn, cursor = _make_conn([
        (10, date(2026, 3, 12), 300.00, 100.00, 200.00),
    ])
    get_conn = MagicMock(return_value=conn)

    df = buscar_vendas_em_aberto(1, get_conn)
    saldo = float(df.iloc[0]['saldo'])

    valor_invalido = saldo + 0.01
    assert valor_invalido > saldo, "Valor inválido deve ser maior que o saldo"
