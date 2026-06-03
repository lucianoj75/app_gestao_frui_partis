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
        'SELECT v."Cod_Venda", v."Data", v."Cod_Cliente", v."Tema", v."Total", v."Vlr_Pago", '
        'vi."Cod_Item", vi."Cod_Produto", vi."Qtd", vi."Vlr_Unitario", vi."Desconto", vi."Total_Item", vi."Observacoes" '
        'FROM vendas v '
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
                    "INSERT INTO vendas (\"Cod_Venda\", \"Data\", \"Cod_Cliente\", \"Tema\", \"Total\", \"Vlr_Pago\", criado_por, criado_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (cv, dt, int(dados['cod_cli']) if dados['cod_cli'] else None, dados['tema'], float(dados['total']), float(vlr_pago), usuario_logado['id'], dt)
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


def processar_salvamento(df_editado, tabela, pk_col):
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

        def converter(v):
            """Converte tipos numpy para tipos nativos Python compatíveis com PostgreSQL."""
            import numpy as np
            if isinstance(v, (np.integer,)):  return int(v)
            if isinstance(v, (np.floating,)): return float(v)
            if isinstance(v, (np.bool_,)):    return bool(v)
            if v != v:                         return None  # NaN
            return v

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

# --- CARREGAMENTO INICIAL ---
df_p = carregar_estoque()
df_c = carregar_clientes()
df_v = carregar_vendas()

# --- AUXILIARES ---
def formatar_br(valor):
    try: return f"R\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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

    if st.session_state.pagamento_pendente is not None:
        popup_pagamento()

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
                "Estoque Atual": st.column_config.NumberColumn("Estoque Atual", format="%d"),
                **colunas_ocultar
            })

        if not df_p.equals(res_p.reset_index(drop=True)):
            st.session_state.p_alterado = True

        if salvar_p:
            if processar_salvamento(res_p, "produtos", "Cod_Produto"):
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
            if processar_salvamento(res_c, "clientes", "Cod_Cliente"):
                st.session_state.c_key += 1
                st.rerun()

# --- ABA 4: RELATÓRIOS ---
with aba_relatorio:
    st.subheader("📈 Histórico e Relatórios")
    st.download_button("📥 Baixar Banco de Dados", data=preparar_download_dados(), file_name="backup_fruipartis.zip")

    sub_vendas, sub_mensal, sub_top = st.tabs(["🧾 Vendas", "📅 Faturamento Mensal", "🏆 Top 10 Produtos"])

    if df_v is not None and not df_v.empty:
        df_rep = df_v.merge(df_c[['Cod_Cliente', 'Nome']], on='Cod_Cliente', how='left').rename(columns={'Nome': 'Cliente'})
        df_rep = df_rep.merge(df_p[['Cod_Produto', 'Nome']], on='Cod_Produto', how='left').rename(columns={'Nome': 'Produto'})

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

    with sub_mensal:
        if df_v is None or df_v.empty:
            st.info("Nenhuma venda registrada ainda.")
        else:
            import calendar

            ano_atual = datetime.now().year
            mes_atual = datetime.now().month

            todos_meses = pd.DataFrame([
                {'Ano': ano_atual, 'Mes': m, 'Mes_Nome': calendar.month_name[m]}
                for m in range(1, mes_atual + 1)
            ])

            vendas_cab_m = df_rep.drop_duplicates(subset='Cod_Venda')[['Cod_Venda', 'Data', 'Total']].copy()
            vendas_cab_m['Data_dt'] = pd.to_datetime(vendas_cab_m['Data'], dayfirst=True, errors='coerce')
            vendas_cab_m['Ano']     = vendas_cab_m['Data_dt'].dt.year
            vendas_cab_m['Mes']     = vendas_cab_m['Data_dt'].dt.month
            vendas_cab_m = vendas_cab_m[vendas_cab_m['Ano'] == ano_atual]

            agrup = vendas_cab_m.groupby('Mes').agg(
                Qtd_Vendas=('Cod_Venda', 'count'),
                Faturamento=('Total', 'sum')
            ).reset_index()

            df_mensal = todos_meses.merge(agrup, on='Mes', how='left').fillna(0)
            df_mensal['Ticket Médio'] = df_mensal.apply(
                lambda r: r['Faturamento'] / r['Qtd_Vendas'] if r['Qtd_Vendas'] > 0 else 0, axis=1
            )

            meses_opcoes = df_mensal['Mes_Nome'].tolist()
            filtro_mes   = st.selectbox("Filtrar por mês (opcional)", ["Todos"] + meses_opcoes)

            df_exibir = df_mensal.copy()
            if filtro_mes != "Todos":
                df_exibir = df_exibir[df_exibir['Mes_Nome'] == filtro_mes]

            total_fat = df_exibir['Faturamento'].sum()
            total_qtd = int(df_exibir['Qtd_Vendas'].sum())
            ticket_geral = total_fat / total_qtd if total_qtd > 0 else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("Faturamento",    formatar_br(total_fat))
            m2.metric("Total de Vendas", str(total_qtd))
            m3.metric("Ticket Médio",   formatar_br(ticket_geral))

            df_tabela = df_exibir[['Mes_Nome', 'Qtd_Vendas', 'Faturamento', 'Ticket Médio']].copy()
            df_tabela.columns = ['Mês', 'Qtd. Vendas', 'Faturamento (R$)', 'Ticket Médio (R$)']
            df_tabela['Qtd. Vendas']        = df_tabela['Qtd. Vendas'].astype(int)
            df_tabela['Faturamento (R$)']   = df_tabela['Faturamento (R$)'].apply(formatar_br)
            df_tabela['Ticket Médio (R$)']  = df_tabela['Ticket Médio (R$)'].apply(formatar_br)
            st.dataframe(df_tabela, hide_index=True, width="stretch")

    with sub_top:
        if df_v is None or df_v.empty:
            st.info("Nenhuma venda registrada ainda.")
        else:
            df_itens = df_rep.copy()
            df_itens['Data_dt'] = pd.to_datetime(df_itens['Data'], dayfirst=True, errors='coerce')
            df_itens['Ano_Mes'] = df_itens['Data_dt'].dt.to_period('M')

            por_mes = df_itens.groupby(['Produto', 'Ano_Mes']).agg(
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
            top10.columns = ['Produto', 'Qtd. Média/Mês', 'Valor Médio/Mês (R$)', 'Meses c/ Venda']
            top10['Qtd. Média/Mês']        = top10['Qtd. Média/Mês'].round(1)
            top10['Valor Médio/Mês (R$)']  = top10['Valor Médio/Mês (R$)'].apply(formatar_br)
            top10['Meses c/ Venda']        = top10['Meses c/ Venda'].astype(int)

            st.caption("Top 10 produtos por média de unidades vendidas por mês.")
            st.dataframe(top10, width="stretch")
