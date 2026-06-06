"""
Testes com mock para as funções que dependem do banco de dados.

As funções testadas (verificar_login, ativar_por_token, gerar_token_ativacao,
gerar_token_senha, processar_salvamento) fazem chamadas ao PostgreSQL via
get_conn(). Nos testes, essa conexão é substituída por um objeto simulado
(MagicMock), de forma que nenhum banco real é necessário.

Após a refatoração do app.py:
  - `converter` foi movida para o escopo de módulo → testada diretamente
    em test_funcoes_puras.py, sem necessidade de replicação aqui.
  - `processar_salvamento` agora recebe `usuario_logado` como parâmetro
    explícito → não depende mais de estado global do Streamlit.

Como executar:
    pytest tests/test_banco_mock.py -v

Dependências:
    pip install pytest bcrypt pandas numpy
"""

from unittest.mock import MagicMock
from datetime import datetime, timedelta
import bcrypt
import pandas as pd
import numpy as np
import pytest
import sys
import os

# ---------------------------------------------------------------------------
# Importação das funções diretamente do app.py
# O app.py executa código Streamlit no nível de módulo (st.set_page_config,
# st.query_params, st.session_state etc.), o que impede um import direto.
# Por isso replicamos aqui apenas as funções que serão testadas, mantendo
# assinaturas e lógica idênticas às do app.py refatorado.
# ---------------------------------------------------------------------------

def verificar_login(email, senha, get_conn):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, senha_hash, ativo, admin FROM usuarios WHERE email = %s",
        (email,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None, "E-mail não cadastrado.", None
    uid, nome, senha_hash, ativo, admin = row
    if not bcrypt.checkpw(senha.encode(), senha_hash.encode()):
        return None, "Senha incorreta.", None
    if not ativo:
        return None, "inativo", {"id": uid, "nome": nome, "email": email}
    return {"id": uid, "nome": nome, "email": email, "admin": bool(admin)}, None, None


def ativar_por_token(token, get_conn):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, token_expira FROM usuarios WHERE token_ativacao = %s",
        (token,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "Token inválido."
    uid, nome, expira_str = row
    expira = datetime.strptime(expira_str, '%d/%m/%Y %H:%M:%S')
    if datetime.now() > expira:
        conn.close()
        return False, "Link de ativação expirado. Solicite um novo cadastro."
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE usuarios SET ativo = 1, token_ativacao = NULL, token_expira = NULL WHERE id = %s",
        (uid,)
    )
    conn.commit()
    conn.close()
    return True, nome


def gerar_token_ativacao(usuario_id, get_conn):
    import uuid
    token  = str(uuid.uuid4())
    expira = (datetime.now() + timedelta(hours=24)).strftime('%d/%m/%Y %H:%M:%S')
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET token_ativacao = %s, token_expira = %s WHERE id = %s",
        (token, expira, usuario_id)
    )
    conn.commit()
    conn.close()
    return token


def gerar_token_senha(usuario_id, get_conn):
    import uuid
    token  = str(uuid.uuid4())
    expira = (datetime.now() + timedelta(hours=24)).strftime('%d/%m/%Y %H:%M:%S')
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET token_senha = %s, token_senha_expira = %s WHERE id = %s",
        (token, expira, usuario_id)
    )
    conn.commit()
    conn.close()
    return token


def converter(v):
    """Idêntica à versão do escopo de módulo do app.py refatorado."""
    if isinstance(v, np.integer):  return int(v)
    if isinstance(v, np.floating): return float(v)
    if isinstance(v, np.bool_):    return bool(v)
    if v != v:                     return None
    return v


def processar_salvamento(df_editado, tabela, pk_col, get_conn, usuario_logado):
    """Assinatura idêntica ao app.py refatorado (usuario_logado explícito)."""
    df_final = df_editado.copy()
    if 'Nome' in df_final.columns:
        df_final = df_final[df_final['Nome'].fillna('').str.strip() != ""]

    conn   = get_conn()
    cursor = conn.cursor()
    try:
        agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        if 'Status' in df_final.columns:
            df_final['Status'] = df_final['Status'].astype(int)

        audit_cols = {'criado_por', 'criado_em', 'alterado_por', 'alterado_em'}
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (tabela,)
        )
        todas_cols = [c[0] for c in cursor.fetchall()]
        edit_cols  = [c for c in df_final.columns if c in todas_cols and c != pk_col and c not in audit_cols]

        for _, row in df_final.iterrows():
            set_clause  = ", ".join([f'"{c}" = %s' for c in edit_cols])
            set_clause += ", alterado_por = %s, alterado_em = %s"
            valores = [converter(row[c]) for c in edit_cols] + [usuario_logado['id'], agora, converter(row[pk_col])]
            cursor.execute(f'UPDATE "{tabela}" SET {set_clause} WHERE "{pk_col}" = %s', valores)

        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


# =============================================================================
# Helpers
# =============================================================================

def _senha_hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def _mock_conn(fetchone_return=None, fetchall_return=None):
    """Monta um get_conn() falso com cursor configurável."""
    cursor = MagicMock()
    cursor.fetchone.return_value  = fetchone_return
    cursor.fetchall.return_value  = fetchall_return or []
    conn = MagicMock()
    conn.cursor.return_value = cursor
    get_conn = MagicMock(return_value=conn)
    return get_conn, conn, cursor


# =============================================================================
# Testes: verificar_login
# =============================================================================

class TestVerificarLogin:

    def test_email_nao_cadastrado(self):
        get_conn, _, _ = _mock_conn(fetchone_return=None)
        usuario, erro, inativo = verificar_login("inexistente@x.com", "Senha1", get_conn)
        assert usuario is None
        assert erro == "E-mail não cadastrado."
        assert inativo is None

    def test_senha_incorreta(self):
        hash_correto = _senha_hash("Senha1")
        get_conn, _, _ = _mock_conn(fetchone_return=(1, "João", hash_correto, 1, 0))
        usuario, erro, inativo = verificar_login("joao@x.com", "ErradA1", get_conn)
        assert usuario is None
        assert erro == "Senha incorreta."

    def test_usuario_inativo(self):
        hash_correto = _senha_hash("Senha1")
        get_conn, _, _ = _mock_conn(fetchone_return=(2, "Maria", hash_correto, 0, 0))
        usuario, erro, inativo = verificar_login("maria@x.com", "Senha1", get_conn)
        assert usuario is None
        assert erro == "inativo"
        assert inativo["id"] == 2
        assert inativo["nome"] == "Maria"

    def test_login_valido_usuario_comum(self):
        hash_correto = _senha_hash("Senha1")
        get_conn, _, _ = _mock_conn(fetchone_return=(3, "Carlos", hash_correto, 1, 0))
        usuario, erro, inativo = verificar_login("carlos@x.com", "Senha1", get_conn)
        assert erro is None
        assert inativo is None
        assert usuario["nome"] == "Carlos"
        assert usuario["admin"] is False

    def test_login_valido_admin(self):
        hash_correto = _senha_hash("Admin1!")
        get_conn, _, _ = _mock_conn(fetchone_return=(4, "Admin", hash_correto, 1, 1))
        usuario, erro, _ = verificar_login("admin@x.com", "Admin1!", get_conn)
        assert usuario["admin"] is True

    def test_conexao_fechada_apos_consulta(self):
        get_conn, conn, _ = _mock_conn(fetchone_return=None)
        verificar_login("x@x.com", "Senha1", get_conn)
        conn.close.assert_called_once()


# =============================================================================
# Testes: ativar_por_token
# =============================================================================

class TestAtivarPorToken:

    def test_token_invalido(self):
        get_conn, _, _ = _mock_conn(fetchone_return=None)
        ok, msg = ativar_por_token("token-inexistente", get_conn)
        assert ok is False
        assert msg == "Token inválido."

    def test_token_expirado(self):
        expira = (datetime.now() - timedelta(hours=1)).strftime('%d/%m/%Y %H:%M:%S')
        get_conn, _, _ = _mock_conn(fetchone_return=(1, "Ana", expira))
        ok, msg = ativar_por_token("token-expirado", get_conn)
        assert ok is False
        assert "expirado" in msg.lower()

    def test_token_valido_ativa_usuario(self):
        expira = (datetime.now() + timedelta(hours=23)).strftime('%d/%m/%Y %H:%M:%S')
        get_conn, _, _ = _mock_conn(fetchone_return=(5, "Pedro", expira))
        ok, nome = ativar_por_token("token-valido", get_conn)
        assert ok is True
        assert nome == "Pedro"

    def test_token_valido_chama_commit(self):
        expira = (datetime.now() + timedelta(hours=23)).strftime('%d/%m/%Y %H:%M:%S')
        get_conn, conn, _ = _mock_conn(fetchone_return=(5, "Pedro", expira))
        ativar_por_token("token-valido", get_conn)
        conn.commit.assert_called_once()

    def test_token_valido_fecha_conexao(self):
        expira = (datetime.now() + timedelta(hours=23)).strftime('%d/%m/%Y %H:%M:%S')
        get_conn, conn, _ = _mock_conn(fetchone_return=(5, "Pedro", expira))
        ativar_por_token("token-valido", get_conn)
        conn.close.assert_called()


# =============================================================================
# Testes: gerar_token_ativacao
# =============================================================================

class TestGerarTokenAtivacao:

    def test_retorna_string_uuid(self):
        get_conn, _, _ = _mock_conn()
        token = gerar_token_ativacao(1, get_conn)
        assert isinstance(token, str)
        assert len(token) == 36

    def test_tokens_diferentes_a_cada_chamada(self):
        get_conn, _, _ = _mock_conn()
        t1 = gerar_token_ativacao(1, get_conn)
        t2 = gerar_token_ativacao(1, get_conn)
        assert t1 != t2

    def test_executa_update_no_banco(self):
        get_conn, _, cursor = _mock_conn()
        gerar_token_ativacao(7, get_conn)
        sql_chamado = cursor.execute.call_args[0][0]
        assert "UPDATE usuarios" in sql_chamado
        assert "token_ativacao" in sql_chamado

    def test_chama_commit(self):
        get_conn, conn, _ = _mock_conn()
        gerar_token_ativacao(7, get_conn)
        conn.commit.assert_called_once()

    def test_fecha_conexao(self):
        get_conn, conn, _ = _mock_conn()
        gerar_token_ativacao(7, get_conn)
        conn.close.assert_called_once()

    def test_expira_em_24h(self):
        get_conn, _, cursor = _mock_conn()
        antes = datetime.now()
        gerar_token_ativacao(1, get_conn)
        args = cursor.execute.call_args[0][1]
        expira = datetime.strptime(args[1], '%d/%m/%Y %H:%M:%S')
        diff = expira - antes
        assert timedelta(hours=23, minutes=59) <= diff <= timedelta(hours=24, minutes=1)


# =============================================================================
# Testes: gerar_token_senha
# =============================================================================

class TestGerarTokenSenha:

    def test_retorna_string_uuid(self):
        get_conn, _, _ = _mock_conn()
        token = gerar_token_senha(1, get_conn)
        assert isinstance(token, str)
        assert len(token) == 36

    def test_tokens_diferentes_a_cada_chamada(self):
        get_conn, _, _ = _mock_conn()
        t1 = gerar_token_senha(1, get_conn)
        t2 = gerar_token_senha(1, get_conn)
        assert t1 != t2

    def test_executa_update_no_banco(self):
        get_conn, _, cursor = _mock_conn()
        gerar_token_senha(3, get_conn)
        sql_chamado = cursor.execute.call_args[0][0]
        assert "UPDATE usuarios" in sql_chamado
        assert "token_senha" in sql_chamado

    def test_chama_commit(self):
        get_conn, conn, _ = _mock_conn()
        gerar_token_senha(3, get_conn)
        conn.commit.assert_called_once()

    def test_fecha_conexao(self):
        get_conn, conn, _ = _mock_conn()
        gerar_token_senha(3, get_conn)
        conn.close.assert_called_once()


# =============================================================================
# Testes: processar_salvamento
# =============================================================================

USUARIO_TESTE = {"id": 1, "nome": "Teste", "email": "teste@x.com"}


class TestProcessarSalvamento:

    def _df_produtos(self):
        return pd.DataFrame([
            {"Cod_Produto": 1, "Nome": "Produto A", "Preco": 10.0},
            {"Cod_Produto": 2, "Nome": "Produto B", "Preco": 20.0},
        ])

    def _get_conn_com_colunas(self, colunas):
        cursor = MagicMock()
        cursor.fetchall.return_value = [(c,) for c in colunas]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return MagicMock(return_value=conn), conn, cursor

    def test_retorna_true_em_sucesso(self):
        get_conn, _, _ = self._get_conn_com_colunas(["Cod_Produto", "Nome", "Preco"])
        resultado = processar_salvamento(self._df_produtos(), "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        assert resultado is True

    def test_chama_update_para_cada_linha(self):
        get_conn, _, cursor = self._get_conn_com_colunas(["Cod_Produto", "Nome", "Preco"])
        processar_salvamento(self._df_produtos(), "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        # 1 SELECT das colunas + 2 UPDATEs (um por linha)
        assert cursor.execute.call_count == 3

    def test_chama_commit(self):
        get_conn, conn, _ = self._get_conn_com_colunas(["Cod_Produto", "Nome", "Preco"])
        processar_salvamento(self._df_produtos(), "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        conn.commit.assert_called_once()

    def test_fecha_conexao_em_sucesso(self):
        get_conn, conn, _ = self._get_conn_com_colunas(["Cod_Produto", "Nome", "Preco"])
        processar_salvamento(self._df_produtos(), "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        conn.close.assert_called_once()

    def test_remove_linhas_com_nome_vazio(self):
        df = pd.DataFrame([
            {"Cod_Produto": 1, "Nome": "Produto A", "Preco": 10.0},
            {"Cod_Produto": 2, "Nome": "",           "Preco": 20.0},
            {"Cod_Produto": 3, "Nome": "   ",        "Preco": 30.0},
        ])
        get_conn, _, cursor = self._get_conn_com_colunas(["Cod_Produto", "Nome", "Preco"])
        processar_salvamento(df, "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        # 1 SELECT + 1 UPDATE (só a linha com nome válido)
        assert cursor.execute.call_count == 2

    def test_nao_sobrescreve_colunas_de_auditoria(self):
        df = pd.DataFrame([
            {"Cod_Produto": 1, "Nome": "X", "Preco": 5.0,
             "criado_por": 99, "criado_em": "01/01/2024 00:00:00"}
        ])
        get_conn, _, cursor = self._get_conn_com_colunas(
            ["Cod_Produto", "Nome", "Preco", "criado_por", "criado_em"]
        )
        processar_salvamento(df, "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        sql_update = cursor.execute.call_args_list[-1][0][0]
        assert "criado_por" not in sql_update
        assert "criado_em" not in sql_update

    def test_retorna_false_em_excecao(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("Cod_Produto",), ("Nome",), ("Preco",)]
        cursor.execute.side_effect = [None, Exception("Erro simulado")]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        get_conn = MagicMock(return_value=conn)
        resultado = processar_salvamento(self._df_produtos(), "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        assert resultado is False

    def test_fecha_conexao_mesmo_em_excecao(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("Cod_Produto",), ("Nome",)]
        cursor.execute.side_effect = [None, Exception("Erro simulado")]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        get_conn = MagicMock(return_value=conn)
        processar_salvamento(self._df_produtos(), "produtos", "Cod_Produto", get_conn, USUARIO_TESTE)
        conn.close.assert_called_once()
