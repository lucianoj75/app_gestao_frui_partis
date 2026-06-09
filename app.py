import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import io
import zipfile
import sqlite3
import bcrypt
import smtplib
import uuid
import re
import numpy as np
import plotly.graph_objects as go
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAÇÕES DE ARQUITETURA ---

# --- CONFIGURAÇÕES DE E-MAIL (preencha com suas credenciais) ---
SMTP_HOST    = 'smtp.gmail.com'
SMTP_PORT    = 587
SMTP_USER    = st.secrets.get("SMTP_USER",    "")
SMTP_PASS    = st.secrets.get("SMTP_PASS",    "")
APP_BASE_URL = st.secrets.get("APP_BASE_URL", "http://localhost:8501")

# --- CONFIGURAÇÕES DO SUPABASE ---
DB_HOST = st.secrets.get("DB_HOST", "")
DB_PORT = int(st.secrets.get("DB_PORT", 6543))
DB_NAME = st.secrets.get("DB_NAME", "postgres")
DB_USER = st.secrets.get("DB_USER", "")
DB_PASS = st.secrets.get("DB_PASS", "")

st.set_page_config(page_title="Gestão de Vendas Frui Partis", layout="wide")



# --- FUNÇÃO AUXILIAR DE CONEXÃO ---
def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS, sslmode="require"
    )

@st.cache_resource
def get_engine():
    url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    return create_engine(url)

def executar_query(query, params=None, commit=False):
    if commit:
        conn = get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Erro no banco de dados: {e}")
            return None
        finally:
            conn.close()
    else:
        try:
            engine = get_engine()
            with engine.connect() as conn:
                if params:
                    return pd.read_sql(text(query), conn, params=params)
                else:
                    return pd.read_sql(text(query), conn)
        except Exception as e:
            st.error(f"Erro no banco de dados: {e}")
            return None

# ═══════════════════════════════════════════════════════════════════════════
#  AUTENTICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════

def verificar_login(email, senha):
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

def validar_senha(senha):
    if len(senha) < 6 or len(senha) > 10:
        return "A senha deve ter entre 6 e 10 caracteres."
    if not any(c.isupper() for c in senha):
        return "A senha deve ter pelo menos uma letra maiúscula."
    if not any(c.isdigit() for c in senha):
        return "A senha deve ter pelo menos um número."
    return None

def validar_cpf_formato(cpf):
    return re.sub(r'\D', '', cpf)

def enviar_email_ativacao(email_dest, nome, token):
    if not SMTP_PASS:
        st.warning("⚠️ E-mail de ativação não enviado: SMTP_PASS não configurado. Configure a Senha de App do Gmail no topo do app.py.")
        return False
    link = f"{APP_BASE_URL}/?token={token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Ative seu cadastro — Frui Partis"
    msg["From"]    = SMTP_USER
    msg["To"]      = email_dest
    corpo_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#b45309">Frui Partis</h2>
      <p>Olá, <strong>{nome}</strong>!</p>
      <p>Clique no botão abaixo para ativar seu acesso ao sistema:</p>
      <a href="{link}" style="display:inline-block;padding:12px 24px;background:#b45309;
         color:#fff;border-radius:6px;text-decoration:none;font-weight:bold">
        Ativar meu cadastro
      </a>
      <p style="margin-top:20px;color:#6b7280;font-size:12px">
        Este link expira em 24 horas.<br>
        Se não solicitou este cadastro, ignore este e-mail.
      </p>
    </div>
    """
    msg.attach(MIMEText(corpo_html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email_dest, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False


def enviar_email_redefinicao(email_dest, nome, token):
    if not SMTP_PASS:
        st.warning("⚠️ E-mail de redefinição não enviado: SMTP_PASS não configurado.")
        return False
    link = f"{APP_BASE_URL}/?reset_token={token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Redefinição de senha — Frui Partis"
    msg["From"]    = SMTP_USER
    msg["To"]      = email_dest
    corpo_html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#b45309">Frui Partis</h2>
      <p>Olá, <strong>{nome}</strong>!</p>
      <p>Recebemos uma solicitação para redefinir sua senha. Clique no botão abaixo:</p>
      <a href="{link}" style="display:inline-block;padding:12px 24px;background:#b45309;
         color:#fff;border-radius:6px;text-decoration:none;font-weight:bold">
        Redefinir minha senha
      </a>
      <p style="margin-top:20px;color:#6b7280;font-size:12px">
        Este link expira em 24 horas.<br>
        Se você não solicitou a redefinição, ignore este e-mail.
      </p>
    </div>
    """
    msg.attach(MIMEText(corpo_html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email_dest, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Erro ao enviar e-mail: {e}")
        return False

def gerar_token_ativacao(usuario_id):
    token   = str(uuid.uuid4())
    expira  = (datetime.now() + timedelta(hours=24)).strftime('%d/%m/%Y %H:%M:%S')
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET token_ativacao = %s, token_expira = %s WHERE id = %s",
        (token, expira, usuario_id)
    )
    conn.commit()
    conn.close()
    return token


def gerar_token_senha(usuario_id):
    token  = str(uuid.uuid4())
    expira = (datetime.now() + timedelta(hours=24)).strftime('%d/%m/%Y %H:%M:%S')
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET token_senha = %s, token_senha_expira = %s WHERE id = %s",
        (token, expira, usuario_id)
    )
    conn.commit()
    conn.close()
    return token

def ativar_por_token(token):
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

# --- VERIFICAR TOKEN NA URL (ativação por link) ---
params = st.query_params
if "token" in params:
    token_url = params["token"]
    ok, msg = ativar_por_token(token_url)
    if ok:
        st.success(f"✅ Cadastro de **{msg}** ativado com sucesso! Faça login abaixo.")
    else:
        st.error(f"❌ {msg}")
    st.query_params.clear()


# --- VERIFICAR RESET_TOKEN NA URL (redefinição de senha) ---
if "reset_token" in params:
    st.session_state.tela       = 'redefinir_senha'
    st.session_state.reset_token_val = params["reset_token"]
    st.query_params.clear()

# ── Tela de cadastro de novo usuário ───────────────────────────────────────
def tela_cadastro():
    st.title("📝 Novo Cadastro")
    st.caption("Preencha todos os campos para criar seu acesso.")

    with st.form("form_cadastro"):
        nome     = st.text_input("Nome Completo")
        cpf      = st.text_input("CPF")
        email    = st.text_input("E-mail (será seu login)")
        senha    = st.text_input("Senha", type="password",
                                 help="6 a 10 caracteres, pelo menos 1 maiúscula e 1 número")
        senha2   = st.text_input("Repita a Senha", type="password")
        enviado  = st.form_submit_button("Cadastrar", type="primary")

    if enviado:
        # Validações
        erros = []
        if not nome.strip():   erros.append("Nome é obrigatório.")
        if not cpf.strip():    erros.append("CPF é obrigatório.")
        if not email.strip():  erros.append("E-mail é obrigatório.")
        if not senha:          erros.append("Senha é obrigatória.")
        if senha != senha2:    erros.append("As senhas não coincidem.")
        err_senha = validar_senha(senha) if senha else None
        if err_senha:          erros.append(err_senha)

        if erros:
            for e in erros:
                st.error(e)
            return

        cpf_limpo = validar_cpf_formato(cpf)

        # Verificar se e-mail já existe
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ativo FROM usuarios WHERE email = %s", (email.strip().lower(),))
        existente = cursor.fetchone()
        conn.close()

        if existente:
            uid_ex, ativo_ex = existente
            if ativo_ex:
                st.error("Este e-mail já está cadastrado e ativo. Faça login normalmente.")
            else:
                st.warning("Este e-mail já está cadastrado, mas o acesso está inativo.")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔁 Sim, reativar e enviar novo link", type="primary"):
                        token = gerar_token_ativacao(uid_ex)
                        conn2 = get_conn()
                        cursor2 = conn2.cursor()
                        cursor2.execute("SELECT nome FROM usuarios WHERE id = %s", (uid_ex,))
                        nome_ex = cursor2.fetchone()[0]
                        conn2.close()
                        if enviar_email_ativacao(email.strip().lower(), nome_ex, token):
                            st.success("Link de ativação reenviado! Verifique seu e-mail.")
                        st.session_state.tela = 'login'
                        st.rerun()
                with col2:
                    if st.button("↩️ Voltar"):
                        st.session_state.tela = 'login'
                        st.rerun()
        else:
            # Novo cadastro
            senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
            agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usuarios (nome, cpf, email, senha_hash, ativo, admin, criado_em)
                VALUES (%s, %s, %s, %s, 0, 0, %s)
            """, (nome.strip(), cpf_limpo, email.strip().lower(), senha_hash, agora))
            novo_id = cursor.fetchone()[0]
            conn.commit()
            conn.close()

            token = gerar_token_ativacao(novo_id)
            if enviar_email_ativacao(email.strip().lower(), nome.strip(), token):
                st.success("✅ Cadastro realizado! Verifique seu e-mail para ativar o acesso.")
            else:
                st.info("Cadastro criado. Configure o e-mail no sistema para receber o link de ativação.")

            if st.button("← Voltar ao Login"):
                st.session_state.tela = 'login'
                st.rerun()


# ── Tela "Esqueci minha senha" ─────────────────────────────────────────────
def tela_esqueci_senha():
    st.title("🔑 Esqueci minha senha")
    st.caption("Informe seu e-mail cadastrado para receber o link de redefinição.")

    with st.form("form_esqueci"):
        email   = st.text_input("E-mail")
        enviado = st.form_submit_button("Enviar", type="primary")

    if enviado:
        if not email.strip():
            st.error("Informe seu e-mail.")
            return
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM usuarios WHERE email = %s", (email.strip().lower(),))
        row = cursor.fetchone()
        conn.close()
        if not row:
            st.error("E-mail não encontrado. Verifique e tente novamente.")
            st.session_state.tela = 'login'
            st.rerun()
        else:
            uid, nome = row
            token = gerar_token_senha(uid)
            if enviar_email_redefinicao(email.strip().lower(), nome, token):
                st.success("✅ Enviamos um link de redefinição para o seu e-mail. Verifique sua caixa de entrada.")
            else:
                st.info("Solicitação registrada. Configure o e-mail no sistema para receber o link.")

    st.divider()
    if st.button("← Voltar ao Login"):
        st.session_state.tela = 'login'
        st.rerun()


# ── Tela de redefinição de senha (acessada via link) ──────────────────────
def tela_redefinir_senha(token):
    st.title("🔒 Redefinir Senha")

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, token_senha_expira FROM usuarios WHERE token_senha = %s",
        (token,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        st.error("❌ Link inválido. Solicite uma nova redefinição de senha.")
        if st.button("← Voltar ao Login"):
            st.session_state.tela = 'login'
            st.rerun()
        return

    uid, nome, expira_str = row
    expira = datetime.strptime(expira_str, '%d/%m/%Y %H:%M:%S')
    if datetime.now() > expira:
        st.error("❌ Este link expirou. Solicite uma nova redefinição de senha.")
        if st.button("← Voltar ao Login"):
            st.session_state.tela = 'login'
            st.rerun()
        return

    st.caption(f"Olá, **{nome}**! Defina sua nova senha abaixo.")

    with st.form("form_nova_senha"):
        senha  = st.text_input("Nova Senha", type="password",
                               help="6 a 10 caracteres, pelo menos 1 maiúscula e 1 número")
        senha2 = st.text_input("Repita a Nova Senha", type="password")
        salvar = st.form_submit_button("Salvar Nova Senha", type="primary")

    if salvar:
        erros = []
        if not senha:          erros.append("A senha é obrigatória.")
        if senha != senha2:    erros.append("As senhas não coincidem.")
        err = validar_senha(senha) if senha else None
        if err:                erros.append(err)

        if erros:
            for e in erros:
                st.error(e)
            return

        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE usuarios SET senha_hash = %s, token_senha = NULL, token_senha_expira = NULL WHERE id = %s",
            (senha_hash, uid)
        )
        conn.commit()
        conn.close()
        st.success("✅ Senha redefinida com sucesso! Faça login com sua nova senha.")
        st.session_state.tela = 'login'
        if 'reset_token_val' in st.session_state:
            del st.session_state.reset_token_val
        st.rerun()

# ── Tela de login ──────────────────────────────────────────────────────────
def tela_login():
    st.title("🔐 Frui Partis")
    st.caption("Sistema de Gestão de Vendas")

    with st.form("form_login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
        with col2:
            st.form_submit_button("Novo Cadastro", on_click=lambda: st.session_state.update(tela='cadastro'), width='stretch')
        with col3:
            st.form_submit_button("Esqueci minha senha", on_click=lambda: st.session_state.update(tela='esqueci_senha'), width='stretch')

    if entrar:
        usuario, erro, inativo = verificar_login(email.strip().lower(), senha)
        if erro == "inativo":
            token = gerar_token_ativacao(inativo['id'])
            if enviar_email_ativacao(inativo['email'], inativo['nome'], token):
                st.warning("\u26a0\ufe0f Seu cadastro ainda n\u00e3o foi ativado. Enviamos um novo link de ativa\u00e7\u00e3o para o seu e-mail.")
            else:
                st.warning("\u26a0\ufe0f Seu cadastro ainda n\u00e3o foi ativado. Configure o envio de e-mail no sistema para receber o link de ativa\u00e7\u00e3o.")
        elif erro:
            st.error(erro)
        else:
            st.session_state.autenticado  = True
            st.session_state.usuario      = usuario
            st.session_state.tela         = 'app'
            st.rerun()

# ── Controle de fluxo de telas ────────────────────────────────────────────
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'tela' not in st.session_state:
    st.session_state.tela = 'login'
if 'reset_token_val' not in st.session_state:
    st.session_state.reset_token_val = ''

if not st.session_state.autenticado:
    if st.session_state.tela == 'cadastro':
        tela_cadastro()
        st.divider()
        if st.button("← Voltar ao Login"):
            st.session_state.tela = 'login'
            st.rerun()
    elif st.session_state.tela == 'esqueci_senha':
        tela_esqueci_senha()
    elif st.session_state.tela == 'redefinir_senha':
        token_val = st.session_state.get('reset_token_val', '')
        tela_redefinir_senha(token_val)
    else:
        tela_login()
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
#  APP PRINCIPAL (só chega aqui se autenticado)
# ═══════════════════════════════════════════════════════════════════════════

usuario_logado = st.session_state.usuario

with st.sidebar:
    st.markdown(f"👤 **{usuario_logado['nome']}**")
    st.caption(usuario_logado['email'])
    if st.button("Sair", width="stretch"):
        st.session_state.autenticado = False
        st.session_state.usuario     = None
        st.session_state.tela        = 'login'
        st.rerun()

# --- 1. INICIALIZAÇÃO DO ESTADO ---
if 'p_key' not in st.session_state: st.session_state.p_key = 0
if 'c_key' not in st.session_state: st.session_state.c_key = 0
if 'carrinho' not in st.session_state: st.session_state.carrinho = []
if 'reset_venda_key' not in st.session_state: st.session_state.reset_venda_key = 0
if 'reset_prod_sel_key' not in st.session_state: st.session_state.reset_prod_sel_key = 0
if 'item_pendente' not in st.session_state: st.session_state.item_pendente = None
if 'p_alterado' not in st.session_state: st.session_state.p_alterado = False
if 'pagamento_pendente' not in st.session_state: st.session_state.pagamento_pendente = None
if 'filtros_aplicados' not in st.session_state: st.session_state.filtros_aplicados = False
if 'filtro_cliente_val' not in st.session_state: st.session_state.filtro_cliente_val = 'Todos'
if 'filtro_data_val' not in st.session_state: st.session_state.filtro_data_val = None
if 'filtro_pendente_val' not in st.session_state: st.session_state.filtro_pendente_val = False
if 'modal_cobranca_dados' not in st.session_state: st.session_state.modal_cobranca_dados = None
if 'modal_pagamento_dados' not in st.session_state: st.session_state.modal_pagamento_dados = None

# --- FUNÇÕES DE CARREGAMENTO ---
@st.cache_data(ttl=600)
def carregar_estoque():
    df = executar_query('SELECT * FROM produtos')
    if df is not None and 'Status' in df.columns:
        df['Status'] = df['Status'].map({1: True, 0: False, 'True': True, 'False': False, True: True, False: False}).fillna(True)
    return df

@st.cache_data(ttl=600)
def carregar_clientes():
    return executar_query("SELECT * FROM clientes")

def carregar_vendas():
    query = (
        'SELECT v."Cod_Venda", v."Data", v."Cod_Cliente", v."Tema", v."Total", '
        'COALESCE(pag.total_pago, 0) AS "Vlr_Pago", '
        'vi."Cod_Item", vi."Cod_Produto", vi."Qtd", vi."Vlr_Unitario", vi."Desconto", vi."Total_Item", vi."Observacoes" '
        'FROM vendas v '
        'LEFT JOIN (SELECT venda_id, SUM(valor) AS total_pago FROM vendas_pagamentos GROUP BY venda_id) pag '
        '  ON pag.venda_id = v."Cod_Venda" '
        'LEFT JOIN vendas_itens vi ON v."Cod_Venda" = vi."Cod_Venda" '
        'ORDER BY v."Cod_Venda" DESC'
    )
    return executar_query(query)

# --- JANELAS POP-UP (DIALOGS) ---

@st.dialog("Cadastrar Novo Produto")
def popup_novo_produto():
    with st.form("form_novo_prod", clear_on_submit=True):
        nome        = st.text_input("Nome do Produto")
        preco       = st.number_input("Preço", min_value=0.0, step=0.1)
        estoque     = st.number_input("Estoque Inicial", min_value=0, step=1)
        observacoes = st.text_area("Observações")

        if st.form_submit_button("Salvar"):
            if nome:
                conn   = get_conn()
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT MAX(\"Cod_Produto\") FROM produtos")
                    res    = cursor.fetchone()[0]
                    novo_id = int(res) + 1 if res is not None else 1
                    agora  = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    cursor.execute(
                        "INSERT INTO produtos (\"Cod_Produto\", \"Nome\", \"Preco\", \"Estoque Atual\", \"Observacoes\", \"Status\", criado_por, criado_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (novo_id, nome, preco, estoque, observacoes, 1, usuario_logado['id'], agora)
                    )
                    conn.commit()
                    st.success("Produto cadastrado com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
                finally:
                    conn.close()
            else:
                st.error("O campo 'Nome' é obrigatório.")

@st.dialog("Cadastrar Novo Cliente")
def popup_novo_cliente():
    with st.form("form_novo_cli", clear_on_submit=True):
        nome     = st.text_input("Nome Completo")
        tipo     = st.selectbox("Tipo", ["PF", "PJ"])
        sexo     = st.selectbox("Sexo", ["M", "F", "O", "NA"])
        email    = st.text_input("Email")
        telefone = st.text_input("Telefone")

        if st.form_submit_button("Salvar"):
            if nome:
                conn   = get_conn()
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT MAX(\"Cod_Cliente\") FROM clientes")
                    res    = cursor.fetchone()[0]
                    novo_id = int(res) + 1 if res is not None else 1
                    agora  = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    cursor.execute(
                        "INSERT INTO clientes (\"Cod_Cliente\", \"Nome\", \"Tipo_Pessoa\", \"Sexo\", \"Email\", \"Telefone\", criado_por, criado_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (novo_id, nome, tipo, sexo, email, telefone, usuario_logado['id'], agora)
                    )
                    conn.commit()
                    st.success("Cliente cadastrado com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
                finally:
                    conn.close()
            else:
                st.error("O campo 'Nome' é obrigatório.")

@st.dialog("Produto sem Estoque")
def popup_confirmar_sem_estoque():
    item = st.session_state.item_pendente
    st.warning(f"O produto **{item['Produto']}** está sem estoque. Deseja seguir com a venda?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Sim", type="primary", width='stretch'):
            st.session_state.carrinho.append(item)
            st.session_state.item_pendente    = None
            st.session_state.reset_prod_sel_key += 1
            st.rerun()
    with c2:
        if st.button("❌ Não", width='stretch'):
            st.session_state.item_pendente = None
            st.rerun()

@st.dialog("💳 Pagamento")
def popup_pagamento():
    dados   = st.session_state.pagamento_pendente
    total   = dados['total']
    st.markdown(f"**Total da Venda:** {dados['total_fmt']}")
    vlr_pago = st.number_input("Valor Pago pelo Cliente (R$)", min_value=0.0, max_value=float(total), value=float(total), step=0.01, format="%.2f")
    pendente = vlr_pago - total
    if pendente >= 0:
        st.success(f"Pendente: R$ {pendente:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    else:
        st.info(f"Valor restante: R$ {abs(pendente):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Confirmar Venda", type="primary", width='stretch'):
            conn   = get_conn()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT MAX(\"Cod_Venda\") FROM vendas")
                res = cursor.fetchone()[0]
                cv  = int(res) + 1 if res is not None else 1
                dt  = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                cursor.execute(
                    "INSERT INTO vendas (\"Cod_Venda\", \"Data\", \"Cod_Cliente\", \"Tema\", \"Total\", criado_por, criado_em) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (cv, dt, int(dados['cod_cli']) if dados['cod_cli'] else None, dados['tema'], float(dados['total']), usuario_logado['id'], dt)
                )
                if vlr_pago > 0:
                    data_pag = datetime.strptime(dt, '%d/%m/%Y %H:%M:%S').date()
                    cursor.execute(
                        "INSERT INTO vendas_pagamentos (venda_id, valor, data_pagamento, observacao, criado_por, criado_em) VALUES (%s, %s, %s, %s, %s, %s)",
                        (cv, float(vlr_pago), data_pag, 'Pagamento no ato da venda', usuario_logado['id'], datetime.now())
                    )
                for item in dados['itens']:
                    cursor.execute("UPDATE produtos SET \"Estoque Atual\" = \"Estoque Atual\" - %s WHERE \"Cod_Produto\" = %s", (item['Qtd'], item['Cod_Produto']))
                    cursor.execute(
                        "INSERT INTO vendas_itens (\"Cod_Venda\", \"Cod_Produto\", \"Qtd\", \"Vlr_Unitario\", \"Desconto\", \"Total_Item\", \"Observacoes\", criado_por, criado_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (cv, int(item['Cod_Produto']), int(item['Qtd']), float(item['Preço Un.']), float(item['Desconto %']), float(item['Total']), item['Observacoes'], usuario_logado['id'], dt)
                    )
                conn.commit()
                st.session_state.carrinho          = []
                st.session_state.pagamento_pendente = None
                st.session_state.reset_venda_key   += 1
                st.session_state.selected_cliente  = "-- Selecione --"
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
            finally:
                conn.close()
    with c2:
        if st.button("↩️ Cancelar", width='stretch'):
            st.session_state.pagamento_pendente = None
            st.rerun()


def converter(v):
    """Converte tipos numpy para tipos nativos Python compatíveis com PostgreSQL."""
    if isinstance(v, np.integer):  return int(v)
    if isinstance(v, np.floating): return float(v)
    if isinstance(v, np.bool_):    return bool(v)
    if v != v:                     return None  # NaN
    return v


def calcular_faturamento_mensal(df_vendas, ano):
    """Retorna DataFrame com faturamento, qtd de vendas e ticket médio por mês do ano informado."""
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
    """Retorna DataFrame com os top 10 produtos por média de unidades vendidas por mês.
    Se df_produtos (com colunas Nome e custo) for fornecido, inclui colunas Margem_% e Margem_R$."""
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

    # Colunas de margem
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
    """Retorna dict com faturamento, qtd_vendas e ticket_medio para o mês/ano informado,
    mais deltas vs mês anterior. Retorna zeros se não houver vendas no período."""
    df = df_vendas.copy()
    df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')

    mask_atual = (df['Data_dt'].dt.month == mes) & (df['Data_dt'].dt.year == ano)
    mes_ant, ano_ant = (12, ano - 1) if mes == 1 else (mes - 1, ano)
    mask_ant  = (df['Data_dt'].dt.month == mes_ant) & (df['Data_dt'].dt.year == ano_ant)

    df_atual = df[mask_atual]
    df_ant   = df[mask_ant]

    fat_atual = float(df_atual['Total'].sum())
    qtd_atual = int(len(df_atual))
    tk_atual  = fat_atual / qtd_atual if qtd_atual > 0 else 0.0

    fat_ant   = float(df_ant['Total'].sum())
    qtd_ant   = int(len(df_ant))
    tk_ant    = fat_ant / qtd_ant if qtd_ant > 0 else 0.0

    # Delta só é exibido quando há vendas no mês atual
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
    """Retorna DataFrame com Produto e Qtd. Vendida (top 3, decrescente) para o mês/ano informado.
    Retorna DataFrame vazio se não houver vendas no período."""
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
    """Agrupa todos os itens de vendas do ano informado, soma quantidade por produto
    e retorna DataFrame com colunas Produto e Qtd. Vendida (top 3, decrescente).
    Retorna DataFrame vazio se não houver vendas no período.
    Usar quando o filtro de mês estiver em 'Todos'."""
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


def processar_salvamento(df_editado, tabela, pk_col, usuario_logado):
    """Salva edições linha a linha, preservando campos de auditoria."""
    df_final = df_editado.copy()
    if 'Nome' in df_final.columns:
        df_final = df_final[df_final['Nome'].fillna('').str.strip() != ""]

    conn   = get_conn()
    cursor = conn.cursor()
    try:
        agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        if 'Status' in df_final.columns:
            df_final['Status'] = df_final['Status'].astype(int)

        # Colunas de auditoria que NÃO devem ser sobrescritas pelo editor
        audit_cols = {'criado_por', 'criado_em', 'alterado_por', 'alterado_em'}

        # Colunas editáveis (sem PK e sem auditoria)
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = %s", (tabela,))
        todas_cols = [c[0] for c in cursor.fetchall()]
        edit_cols  = [c for c in df_final.columns if c in todas_cols and c != pk_col and c not in audit_cols]

        for _, row in df_final.iterrows():
            set_clause = ", ".join([f'"{c}" = %s' for c in edit_cols])
            set_clause += ", alterado_por = %s, alterado_em = %s"
            valores = [converter(row[c]) for c in edit_cols] + [usuario_logado['id'], agora, converter(row[pk_col])]
            cursor.execute(f'UPDATE "{tabela}" SET {set_clause} WHERE "{pk_col}" = %s', valores)

        conn.commit()
        st.cache_data.clear()
        st.success("Alterações salvas com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════════════════════
#  FUNÇÕES DE INADIMPLÊNCIA
# ═══════════════════════════════════════════════════════════════════════════

def buscar_inadimplentes():
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


def buscar_vendas_em_aberto(cliente_id):
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


def registrar_cobranca(venda_id, data_cobranca, observacao, usuario_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO vendas_cobrancas (venda_id, data_cobranca, observacao, criado_por, criado_em) '
            'VALUES (%s, %s, %s, %s, %s)',
            (venda_id, data_cobranca, observacao, usuario_id, datetime.now())
        )
        conn.commit()
    finally:
        conn.close()


def registrar_pagamento(venda_id, valor, data_pagamento, observacao, usuario_id):
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


@st.dialog("📣 Registrar aviso de cobrança")
def popup_registrar_cobranca():
    d = st.session_state.modal_cobranca_dados
    venda_id     = d['venda_id']
    cliente_nome = d['cliente_nome']
    data_venda   = d['data_venda']
    saldo        = d['saldo']

    st.caption(f"{cliente_nome} — venda de {data_venda}")
    with st.container(border=True):
        col_l, col_r = st.columns(2)
        col_l.markdown("Saldo em aberto")
        col_r.markdown(f"<span style='color:#dc2626;float:right'><b>{formatar_df(saldo)}</b></span>", unsafe_allow_html=True)

    data_cob = st.date_input("Data da cobrança", value=datetime.now().date())
    obs = st.text_area("Observação", placeholder="Ex: cliente avisado por WhatsApp, prometeu pagar até dia 15...")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", width='stretch'):
            st.session_state.modal_cobranca_dados = None
            st.rerun()
    with c2:
        if st.button("Salvar", type="primary", width='stretch'):
            if not obs.strip():
                st.error("Observação é obrigatória.")
            else:
                registrar_cobranca(venda_id, data_cob, obs.strip(), usuario_logado['id'])
                st.session_state.modal_cobranca_dados = None
                st.success("Aviso de cobrança registrado!")
                st.rerun()


@st.dialog("💲 Receber pagamento")
def popup_receber_pagamento():
    d = st.session_state.modal_pagamento_dados
    venda_id     = d['venda_id']
    cliente_nome = d['cliente_nome']
    data_venda   = d['data_venda']
    saldo        = float(d['saldo'])

    st.caption(f"{cliente_nome} — venda de {data_venda}")
    with st.container(border=True):
        col_l, col_r = st.columns(2)
        col_l.markdown("Saldo em aberto")
        col_r.markdown(f"<span style='color:#dc2626;float:right'><b>{formatar_df(saldo)}</b></span>", unsafe_allow_html=True)

    valor   = st.number_input("Valor recebido", min_value=0.01, max_value=saldo, value=saldo, step=0.01, format="%.2f")
    data_rec = st.date_input("Data do recebimento", value=datetime.now().date())
    obs     = st.text_input("Observação (opcional)", placeholder="Ex: pago via PIX")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Cancelar", width='stretch'):
            st.session_state.modal_pagamento_dados = None
            st.rerun()
    with c2:
        if st.button("Confirmar recebimento", type="primary", width='stretch'):
            registrar_pagamento(venda_id, valor, data_rec, obs.strip() or None, usuario_logado['id'])
            st.session_state.modal_pagamento_dados = None
            st.cache_data.clear()
            st.rerun()


# --- CARREGAMENTO INICIAL ---
df_p = carregar_estoque()
df_c = carregar_clientes()
df_v = carregar_vendas()

# --- AUXILIARES ---
def formatar_br(valor):
    """Para uso em st.markdown, st.metric e st.table — escapa o $ para evitar LaTeX."""
    try: return f"R\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return valor

def formatar_df(valor):
    """Para uso em st.dataframe — texto puro, sem escape de $."""
    try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return valor

def formatar_markdown_br(valor):
    try: return f"R\\\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return valor

def preparar_download_dados():
    buf = io.BytesIO()
    # Backup não disponível para banco em nuvem
    return buf.getvalue()

# --- INTERFACE ---
aba_venda, aba_relatorio, aba_gestao_c, aba_gestao_p = st.tabs([
    "🛒 Registrar Venda", "📈 Relatórios", "👥 Gestão de Clientes", "📋 Gestão de Produtos"
])

# --- ABA 1: REGISTRAR VENDA ---
with aba_venda:
    st.subheader("Nova Venda")

    venda_em_curso = len(st.session_state.carrinho) > 0
    PLACEHOLDER    = "-- Selecione --"

    if df_c is not None and not df_c.empty and df_p is not None and not df_p.empty:
        c_v1, c_v2 = st.columns(2)
        with c_v1:
            options_cli = [PLACEHOLDER] + sorted(df_c['Nome'].unique())
            if 'selected_cliente' not in st.session_state or st.session_state.selected_cliente not in options_cli:
                st.session_state.selected_cliente = PLACEHOLDER
            index_cli  = options_cli.index(st.session_state.selected_cliente)
            nome_cli   = st.selectbox("Cliente", options_cli, index=index_cli,
                                      key=f"cli_{st.session_state.reset_venda_key}", disabled=venda_em_curso)
            st.session_state.selected_cliente = nome_cli
            cod_cli = int(df_c[df_c['Nome'] == nome_cli]['Cod_Cliente'].values[0]) if nome_cli != PLACEHOLDER else None
        with c_v2:
            tema_v = st.text_input("Tema da Venda", key=f"tema_{st.session_state.reset_venda_key}", disabled=venda_em_curso)

        st.divider()
        df_p_ativos = df_p[df_p['Status'] == True].copy()

        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                options_prod = [PLACEHOLDER] + sorted(df_p_ativos['Nome'].unique())
                nome_p = st.selectbox("Selecione o Produto", options_prod, key=f"p_s_{st.session_state.reset_prod_sel_key}")

            if nome_p != PLACEHOLDER:
                with col1:
                    d_p   = df_p_ativos[df_p_ativos['Nome'] == nome_p].iloc[0]
                    disp  = float(d_p['Estoque Atual']) - sum(i['Qtd'] for i in st.session_state.carrinho if i['Cod_Produto'] == d_p['Cod_Produto'])
                    p_venda_base = float(d_p.get('Preco_Promocional', 0)) if float(d_p.get('Preco_Promocional', 0)) > 0 else float(d_p.get('Preco', 0))
                    st.markdown(f"**Estoque Disponível:** {int(disp)}")
                with col2:
                    qtd_v = st.number_input("Qtd", min_value=1, key=f"q_{st.session_state.reset_prod_sel_key}")
                p_venda = st.number_input("Valor de Venda (R$)", min_value=0.01, value=p_venda_base, step=0.01, format="%.2f", key=f"preco_{st.session_state.reset_prod_sel_key}")
                obs_v   = st.text_area("Observações do Item", key=f"obs_{st.session_state.reset_prod_sel_key}", height=70)

                if st.button("➕ Adicionar ao Carrinho", width='stretch'):
                    if nome_cli == PLACEHOLDER:
                        st.error("Selecione um cliente antes de adicionar produtos ao carrinho.")
                    else:
                        item_novo = {
                            'Cod_Produto': d_p['Cod_Produto'], 'Produto': nome_p, 'Qtd': qtd_v,
                            'Preço Un.': p_venda, 'Desconto %': 0.0, 'Total': qtd_v * p_venda, 'Observacoes': obs_v
                        }
                        if disp <= 0:
                            st.session_state.item_pendente = item_novo
                            st.rerun()
                        else:
                            st.session_state.carrinho.append(item_novo)
                            st.session_state.reset_prod_sel_key += 1
                            st.rerun()

    if st.session_state.item_pendente is not None:
        popup_confirmar_sem_estoque()

    if st.session_state.carrinho:
        st.markdown("### 🛒 Carrinho")
        df_cart = pd.DataFrame(st.session_state.carrinho)
        ed_cart = st.data_editor(df_cart, hide_index=True, width='stretch', column_config={
            "Cod_Produto":  None,
            "Preço Un.":    st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
            "Desconto %":   st.column_config.NumberColumn(format="%.1f%%", min_value=0.0, max_value=100.0),
            "Total":        st.column_config.NumberColumn(format="R$ %.2f", disabled=True)
        }, key=f"ed_cart_{st.session_state.reset_venda_key}")

        ed_cart['Total'] = (ed_cart['Qtd'] * ed_cart['Preço Un.']) * (1 - ed_cart['Desconto %'] / 100)
        total_final = ed_cart['Total'].sum()
        st.metric("Total Líquido", formatar_br(total_final))

        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if st.button("❌ Limpar Carrinho", width='stretch'):
                st.session_state.carrinho        = []
                st.session_state.reset_venda_key += 1
                st.rerun()
        with c_b2:
            if st.button("✅ Finalizar Venda", type="primary", width='stretch'):
                st.session_state.pagamento_pendente = {
                    'itens':     ed_cart.to_dict('records'),
                    'total':     total_final,
                    'total_fmt': formatar_br(total_final),
                    'cod_cli':   cod_cli,
                    'tema':      tema_v
                }
                st.rerun()

# --- ABA 2: GESTÃO DE PRODUTOS ---
with aba_gestao_p:
    st.subheader("📋 Gestão de Produtos")

    if df_p is not None:
        col_np, col_sv = st.columns(2)
        with col_np:
            if st.button("➕ Novo Produto", width='stretch'):
                popup_novo_produto()
        with col_sv:
            salvar_p = st.button("💾 Salvar Edições de Produtos", width='stretch', type="primary")

        if st.session_state.p_alterado:
            st.warning("⚠️ Você tem alterações não salvas! Clique em **Salvar Edições de Produtos** para efetivá-las.")

        # Ocultar colunas de auditoria na visualização
        colunas_ocultar = {'criado_por': None, 'criado_em': None, 'alterado_por': None, 'alterado_em': None}
        res_p = st.data_editor(df_p, hide_index=True, num_rows="fixed", width='stretch', key=f"p_ed_{st.session_state.p_key}",
            column_config={
                "Cod_Produto":  st.column_config.NumberColumn("ID", disabled=True, format="%d"),
                "Status":       st.column_config.CheckboxColumn("Ativo", default=True),
                "Preco":        st.column_config.NumberColumn("Preço", format="%.2f", min_value=0.01),
                "custo":        st.column_config.NumberColumn("Custo (R$)", format="%.2f", min_value=0.0),
                "Estoque Atual": st.column_config.NumberColumn("Estoque Atual", format="%d"),
                **colunas_ocultar
            })

        if not df_p.equals(res_p.reset_index(drop=True)):
            st.session_state.p_alterado = True

        if salvar_p:
            if processar_salvamento(res_p, "produtos", "Cod_Produto", usuario_logado):
                st.session_state.p_alterado = False
                st.session_state.p_key     += 1
                st.rerun()

# --- ABA 3: GESTÃO DE CLIENTES ---
with aba_gestao_c:
    st.subheader("👥 Gestão de Clientes")
    if st.button("➕ Novo Cliente"):
        popup_novo_cliente()

    if df_c is not None:
        colunas_ocultar = {'criado_por': None, 'criado_em': None, 'alterado_por': None, 'alterado_em': None}
        res_c = st.data_editor(df_c, hide_index=True, num_rows="fixed", width='stretch', key=f"c_ed_{st.session_state.c_key}",
            column_config={
                "Cod_Cliente":  st.column_config.NumberColumn("ID", disabled=True, format="%d"),
                "Tipo_Pessoa":  st.column_config.SelectboxColumn("Tipo", options=["PF", "PJ"]),
                "Sexo":         st.column_config.SelectboxColumn("Sexo", options=["M", "F", "O", "NA", ""]),
                **colunas_ocultar
            })
        if st.button("💾 Salvar Edições de Clientes", width='stretch'):
            if processar_salvamento(res_c, "clientes", "Cod_Cliente", usuario_logado):
                st.session_state.c_key += 1
                st.rerun()

# --- ABA 4: RELATÓRIOS ---
with aba_relatorio:
    st.subheader("📈 Histórico e Relatórios")
    st.download_button("📥 Baixar Banco de Dados", data=preparar_download_dados(), file_name="backup_fruipartis.zip")

    sub_dash, sub_vendas, sub_top, sub_inadimplencia = st.tabs(["📊 Dashboard", "🧾 Vendas", "🏆 Top 10 Produtos", "⚠️ Inadimplência"])

    if df_v is not None and not df_v.empty:
        df_rep = df_v.merge(df_c[['Cod_Cliente', 'Nome']], on='Cod_Cliente', how='left').rename(columns={'Nome': 'Cliente'})
        df_rep = df_rep.merge(df_p[['Cod_Produto', 'Nome']], on='Cod_Produto', how='left').rename(columns={'Nome': 'Produto'})

    # --- SUB-ABA DASHBOARD (unificada) ---
    MESES_PT = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }

    with sub_dash:
        mes_agora = datetime.now().month
        ano_atual = datetime.now().year

        opcoes_meses = ["Todos"] + [MESES_PT[m] for m in range(1, mes_agora + 1)]
        filtro_mes_dash = st.selectbox("Mês", opcoes_meses, index=len(opcoes_meses) - 1, key="dash_mes")

        if df_v is None or df_v.empty:
            st.info("Nenhuma venda registrada ainda.")
        else:
            vendas_unique = df_v.drop_duplicates(subset='Cod_Venda')[['Cod_Venda', 'Data', 'Total']]

            def _fmt_delta_br(v):
                """Delta monetário: None=oculto, 0=None (indicador externo), ±=verde/vermelho."""
                if v is None or v == 0:
                    return None
                abs_fmt = formatar_br(abs(v))
                return f"-{abs_fmt}" if v < 0 else f"+{abs_fmt}"

            def _delta_int(v):
                """Delta inteiro: None=oculto, 0=None (indicador externo), ±=verde/vermelho."""
                if v is None or v == 0:
                    return None
                return v

            def _zero_badge(col, v):
                """Renderiza badge 'Sem variação' âmbar abaixo da métrica quando delta == 0."""
                if v == 0:
                    col.markdown(
                        '<span style="background:#f59e0b;color:#fff;padding:2px 8px;'
                        'border-radius:4px;font-size:13px">Sem variação</span>',
                        unsafe_allow_html=True
                    )

            # --- Bloco 1: Métricas ---
            mes_sel = None
            if filtro_mes_dash == "Todos":
                fat_total = float(vendas_unique['Total'].sum())
                qtd_total = int(len(vendas_unique))
                tk_total  = fat_total / qtd_total if qtd_total > 0 else 0.0
                d1, d2, d3 = st.columns(3)
                d1.metric("Faturamento do ano",  formatar_br(fat_total))
                d2.metric("Vendas no ano",        str(qtd_total))
                d3.metric("Ticket médio",         formatar_br(tk_total))
            else:
                mes_sel  = next(k for k, v in MESES_PT.items() if v == filtro_mes_dash)
                metricas = calcular_metricas_dashboard(vendas_unique, mes_sel, ano_atual)
                fat_d = metricas['delta_fat']
                qtd_d = metricas['delta_qtd']
                tk_d  = metricas['delta_ticket']
                d1, d2, d3 = st.columns(3)
                d1.metric("Faturamento do mês", formatar_br(metricas['faturamento']),
                          delta=_fmt_delta_br(fat_d), delta_color="normal")
                _zero_badge(d1, fat_d)
                d2.metric("Vendas no mês", str(metricas['qtd_vendas']),
                          delta=_delta_int(qtd_d), delta_color="normal")
                _zero_badge(d2, qtd_d)
                d3.metric("Ticket médio", formatar_br(metricas['ticket_medio']),
                          delta=_fmt_delta_br(tk_d), delta_color="normal")
                _zero_badge(d3, tk_d)

                mes_ant_num = mes_sel - 1 if mes_sel > 1 else 12
                mes_ant_nome = MESES_PT[mes_ant_num]
                ano_ant_caption = ano_atual if mes_sel > 1 else ano_atual - 1
                st.caption(
                    f"📅 **{filtro_mes_dash} de {ano_atual}** · "
                    f"Variação em relação a **{mes_ant_nome} de {ano_ant_caption}**"
                )

            st.divider()

            # --- Bloco 2: Gráfico de evolução mensal ---
            metrica_sel = st.selectbox("Métrica", ["Faturamento", "Qtd. Vendas", "Ticket Médio"], key="dash_metrica")

            df_fat = calcular_faturamento_mensal(vendas_unique, ano_atual)
            df_fat = df_fat[df_fat['Mes'] <= mes_agora].copy()
            df_fat['Mes_PT'] = df_fat['Mes'].map(MESES_PT)

            col_map = {"Faturamento": "Faturamento", "Qtd. Vendas": "Qtd_Vendas", "Ticket Médio": "Ticket_Medio"}
            col_y = col_map[metrica_sel]

            def _fmt_hover(val, metrica):
                if metrica in ("Faturamento", "Ticket Médio"):
                    s = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    return f"R$ {s}"
                return str(int(val))

            marker_colors = []
            marker_sizes  = []
            for m in df_fat['Mes'].tolist():
                if mes_sel and m == mes_sel:
                    marker_colors.append('#f59e0b')
                    marker_sizes.append(14)
                else:
                    marker_colors.append('#3b82f6')
                    marker_sizes.append(7)

            hover_texts = [_fmt_hover(v, metrica_sel) for v in df_fat[col_y]]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_fat['Mes_PT'],
                y=df_fat[col_y],
                mode='lines+markers',
                line=dict(color='#3b82f6', width=2),
                marker=dict(color=marker_colors, size=marker_sizes),
                text=hover_texts,
                hovertemplate='%{x}: %{text}<extra></extra>',
            ))

            if metrica_sel in ("Faturamento", "Ticket Médio"):
                yaxis_cfg = dict(tickprefix="R$ ", tickformat=",.2f")
            else:
                yaxis_cfg = dict(tickformat="d")

            fig.update_layout(
                xaxis_title=None,
                yaxis_title=metrica_sel,
                yaxis=yaxis_cfg,
                margin=dict(l=10, r=10, t=20, b=10),
                height=320,
                hovermode="x unified",
            )
            st.plotly_chart(fig, width='stretch')

            st.divider()

            # --- Bloco 3: Top 3 Produtos ---
            st.markdown("### 🏆 Top 3 Produtos")
            df_itens_dash = df_rep[['Cod_Venda', 'Produto', 'Qtd']].copy()
            if filtro_mes_dash == "Todos":
                top3 = calcular_top3_ano(vendas_unique, df_itens_dash, ano_atual)
            else:
                top3 = calcular_top3_mes(vendas_unique, df_itens_dash, mes_sel, ano_atual)
            if top3.empty:
                st.info("Nenhuma venda registrada neste período.")
            else:
                st.dataframe(top3, hide_index=True, width="stretch")

            st.divider()

            # --- Bloco 4: Estoque zerado ---
            st.markdown("### ⚠️ Produtos com Estoque Zerado")
            if df_p is not None and not df_p.empty:
                est_zero = df_p[
                    (df_p['Status'] == True) & (df_p['Estoque Atual'] == 0)
                ][['Nome', 'Estoque Atual']].copy()
                est_zero.columns = ['Produto', 'Estoque']
                if est_zero.empty:
                    st.success("Nenhum produto com estoque zerado.")
                else:
                    st.dataframe(est_zero, hide_index=True, width="stretch")

    with sub_vendas:
        if df_v is None or df_v.empty:
            st.info("Nenhuma venda registrada ainda.")
        else:
            vendas_cab = df_rep.drop_duplicates(subset='Cod_Venda')[['Cod_Venda', 'Data', 'Cliente', 'Tema', 'Total', 'Vlr_Pago']].sort_values('Cod_Venda', ascending=False)
            vendas_cab['Data_dt'] = pd.to_datetime(vendas_cab['Data'], dayfirst=True, errors='coerce')
            data_min = vendas_cab['Data_dt'].min().date()
            data_max = vendas_cab['Data_dt'].max().date()

            if st.session_state.filtro_data_val is None:
                st.session_state.filtro_data_val = (data_min, data_max)

            with st.expander("🔍 Filtros", expanded=False):
                f1, f2, f3 = st.columns(3)
                with f1:
                    clientes_opcoes = ["Todos"] + sorted(vendas_cab['Cliente'].dropna().unique().tolist())
                    idx_cli = clientes_opcoes.index(st.session_state.filtro_cliente_val) if st.session_state.filtro_cliente_val in clientes_opcoes else 0
                    filtro_cliente  = st.selectbox("Cliente", clientes_opcoes, index=idx_cli)
                with f2:
                    filtro_data     = st.date_input("Intervalo de Data", value=st.session_state.filtro_data_val)
                with f3:
                    filtro_pendente = st.checkbox("Somente com valor pendente", value=st.session_state.filtro_pendente_val)
                fb1, fb2 = st.columns(2)
                with fb1:
                    btn_filtrar = st.button("🔍 Filtrar", type="primary", width='stretch')
                with fb2:
                    btn_limpar  = st.button("🗑️ Limpar Filtros", width='stretch')

            if btn_limpar:
                st.session_state.filtro_cliente_val  = "Todos"
                st.session_state.filtro_data_val     = (data_min, data_max)
                st.session_state.filtro_pendente_val = False
                st.session_state.filtros_aplicados   = False
                st.rerun()

            if btn_filtrar:
                if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
                    diff = (filtro_data[1] - filtro_data[0]).days
                    if diff > 31:
                        st.error("O intervalo de datas não pode ser maior que 31 dias.")
                    else:
                        st.session_state.filtro_cliente_val  = filtro_cliente
                        st.session_state.filtro_data_val     = filtro_data
                        st.session_state.filtro_pendente_val = filtro_pendente
                        st.session_state.filtros_aplicados   = True
                        st.rerun()
                else:
                    st.error("Selecione um intervalo de datas válido (data inicial e data final).")

            vendas_filtradas = vendas_cab.copy()
            if st.session_state.filtros_aplicados:
                if st.session_state.filtro_cliente_val != "Todos":
                    vendas_filtradas = vendas_filtradas[vendas_filtradas['Cliente'] == st.session_state.filtro_cliente_val]
                if isinstance(st.session_state.filtro_data_val, tuple) and len(st.session_state.filtro_data_val) == 2:
                    d_ini = pd.Timestamp(st.session_state.filtro_data_val[0])
                    d_fim = pd.Timestamp(st.session_state.filtro_data_val[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                    vendas_filtradas = vendas_filtradas[(vendas_filtradas['Data_dt'] >= d_ini) & (vendas_filtradas['Data_dt'] <= d_fim)]
                if st.session_state.filtro_pendente_val:
                    vendas_filtradas = vendas_filtradas[(vendas_filtradas['Vlr_Pago'] - vendas_filtradas['Total']).abs() > 0.001]

            st.metric("Faturamento Total", formatar_br(vendas_filtradas['Total'].sum()))

            if vendas_filtradas.empty:
                st.info("Nenhuma venda encontrada com os filtros selecionados.")
            else:
                for _, row in vendas_filtradas.iterrows():
                    pendente = row['Vlr_Pago'] - row['Total']
                    with st.expander(f"Venda {row['Cod_Venda']} | {row['Data']} | {row['Cliente']} | {formatar_br(row['Total'])}"):
                        if row['Vlr_Pago'] > 0:
                            st.markdown(f"**Total:** {formatar_br(row['Total'])} | **Pago:** {formatar_br(row['Vlr_Pago'])} | **Pendente:** {formatar_br(pendente)}")
                            st.divider()
                        itens = df_rep[df_rep['Cod_Venda'] == row['Cod_Venda']].copy()
                        itens['Vlr. Unitário'] = itens['Vlr_Unitario'].apply(formatar_br)
                        itens['Vlr. Total']    = itens['Total_Item'].apply(formatar_br)
                        st.table(itens[['Produto', 'Qtd', 'Vlr. Unitário', 'Desconto', 'Vlr. Total', 'Observacoes']])

    with sub_top:
        if df_v is None or df_v.empty:
            st.info("Nenhuma venda registrada ainda.")
        else:
            top10 = calcular_top10_produtos(df_rep, df_p)
            top10.columns = ['Produto', 'Qtd. Média/Mês', 'Valor Médio/Mês (R$)', 'Meses c/ Venda', 'Margem %', 'Margem R$']
            top10['Qtd. Média/Mês']        = top10['Qtd. Média/Mês'].round(1)
            top10['Valor Médio/Mês (R$)']  = top10['Valor Médio/Mês (R$)'].apply(formatar_df)
            top10['Meses c/ Venda']        = top10['Meses c/ Venda'].astype(int)

            st.caption("Top 10 produtos por média de unidades vendidas por mês.")
            st.dataframe(top10, width="stretch")

    with sub_inadimplencia:
        df_inad = buscar_inadimplentes()

        if df_inad is None or df_inad.empty:
            st.info("Nenhum cliente com saldo em aberto.")
        else:
            total_aberto     = float(df_inad['saldo_total'].sum())
            clientes_deved   = int(df_inad['cliente_id'].nunique())
            divida_mais_ant  = df_inad['mais_antiga'].min()

            m1, m2, m3 = st.columns(3)
            m1.metric("Total em aberto",   formatar_br(total_aberto))
            m2.metric("Clientes devedores", str(clientes_deved))
            m3.metric("Dívida mais antiga", divida_mais_ant.strftime('%d/%m/%Y') if divida_mais_ant else "—")

            st.markdown("#### Clientes com saldo em aberto")

            for _, row_cli in df_inad.iterrows():
                n_vendas    = int(row_cli['vendas_em_aberto'])
                saldo_cli   = float(row_cli['saldo_total'])
                mais_antiga = row_cli['mais_antiga'].strftime('%d/%m/%Y') if row_cli['mais_antiga'] else "—"
                label_badge = f"{n_vendas} {'venda' if n_vendas == 1 else 'vendas'}"

                with st.expander(
                    f"**{row_cli['cliente']}** &nbsp;&nbsp; `{label_badge}` &nbsp;&nbsp; "
                    f"**{formatar_df(saldo_cli)}** &nbsp;&nbsp; {mais_antiga}"
                ):
                    df_ab = buscar_vendas_em_aberto(int(row_cli['cliente_id']))
                    if df_ab is None or df_ab.empty:
                        st.info("Nenhuma venda em aberto encontrada.")
                    else:
                        header_cols = st.columns([2, 2, 2, 2, 1, 1])
                        header_cols[0].markdown("**Data**")
                        header_cols[1].markdown("**Total**")
                        header_cols[2].markdown("**Pago**")
                        header_cols[3].markdown("**Saldo**")
                        header_cols[4].markdown("**Cobrança**")
                        header_cols[5].markdown("**Pagamento**")
                        st.divider()

                        for _, row_v in df_ab.iterrows():
                            vid         = int(row_v['venda_id'])
                            data_fmt    = row_v['data'].strftime('%d/%m/%Y') if row_v['data'] else "—"
                            saldo_v     = float(row_v['saldo'])
                            row_cols    = st.columns([2, 2, 2, 2, 1, 1])
                            row_cols[0].markdown(data_fmt)
                            row_cols[1].markdown(formatar_df(float(row_v['total'])))
                            row_cols[2].markdown(formatar_df(float(row_v['pago'])))
                            row_cols[3].markdown(
                                f"<span style='color:#dc2626'><b>{formatar_df(saldo_v)}</b></span>",
                                unsafe_allow_html=True
                            )
                            with row_cols[4]:
                                if st.button("📣", key=f"cob_{vid}", help="Registrar aviso de cobrança"):
                                    st.session_state.modal_cobranca_dados = {
                                        'venda_id':     vid,
                                        'cliente_nome': row_cli['cliente'],
                                        'data_venda':   data_fmt,
                                        'saldo':        saldo_v,
                                    }
                                    st.rerun()
                            with row_cols[5]:
                                if st.button("💲", key=f"pag_{vid}", help="Receber pagamento"):
                                    st.session_state.modal_pagamento_dados = {
                                        'venda_id':     vid,
                                        'cliente_nome': row_cli['cliente'],
                                        'data_venda':   data_fmt,
                                        'saldo':        saldo_v,
                                    }
                                    st.rerun()

# --- DIALOGS GLOBAIS (apenas um por ciclo de execução) ---
if st.session_state.pagamento_pendente is not None:
    popup_pagamento()
elif st.session_state.modal_cobranca_dados:
    popup_registrar_cobranca()
elif st.session_state.modal_pagamento_dados:
    popup_receber_pagamento()
