import streamlit as st
import pandas as pd
from datetime import datetime
import os
import io
import zipfile
import sqlite3

# --- CONFIGURAÇÕES DE ARQUITETURA ---
PASTA_DADOS = 'Dados'
DB_PATH = os.path.join(PASTA_DADOS, 'frui_partis.db')

st.set_page_config(page_title="Gestão de Vendas Frui Partis", layout="wide")

# --- FUNÇÃO AUXILIAR DE CONEXÃO ---
def executar_query(query, params=None, commit=False):
    conn = sqlite3.connect(DB_PATH)
    try:
        if commit:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return True
        else:
            return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Erro no banco de dados: {e}")
        return None
    finally:
        conn.close()

# --- 1. INICIALIZAÇÃO DO ESTADO ---
if 'p_key' not in st.session_state: st.session_state.p_key = 0
if 'c_key' not in st.session_state: st.session_state.c_key = 0
if 'carrinho' not in st.session_state: st.session_state.carrinho = []
if 'reset_venda_key' not in st.session_state: st.session_state.reset_venda_key = 0
if 'reset_prod_sel_key' not in st.session_state: st.session_state.reset_prod_sel_key = 0

# --- FUNÇÕES DE CARREGAMENTO ---
@st.cache_data(ttl=600)
def carregar_estoque():
    df = executar_query("SELECT * FROM produtos")
    if df is not None and 'Status' in df.columns:
        df['Status'] = df['Status'].map({1: True, 0: False, 'True': True, 'False': False, True: True, False: False}).fillna(True)
    return df

@st.cache_data(ttl=600)
def carregar_clientes():
    return executar_query("SELECT * FROM clientes")

def carregar_vendas():
    return executar_query("SELECT * FROM vendas")

# --- JANELAS POP-UP (DIALOGS) ---

@st.dialog("Cadastrar Novo Produto")
def popup_novo_produto():
    with st.form("form_novo_prod", clear_on_submit=True):
        nome = st.text_input("Nome do Produto")
        preco = st.number_input("Preço", min_value=0.0, step=0.1)
        estoque = st.number_input("Estoque Inicial", min_value=0, step=1)
        observacoes = st.text_area("Observações")
        
        if st.form_submit_button("Salvar"):
            if nome:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT MAX(Cod_Produto) FROM produtos")
                    res = cursor.fetchone()[0]
                    novo_id = int(res) + 1 if res is not None else 1
                    
                    cursor.execute(
                        "INSERT INTO produtos (Cod_Produto, Nome, Preco, [Estoque Atual], Observacoes, Status) VALUES (?, ?, ?, ?, ?, ?)",
                        (novo_id, nome, preco, estoque, observacoes, 1)
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
        nome = st.text_input("Nome Completo")
        tipo = st.selectbox("Tipo", ["PF", "PJ"])
        sexo = st.selectbox("Sexo", ["M", "F", "O", "NA"])
        email = st.text_input("Email")
        telefone = st.text_input("Telefone")
        
        if st.form_submit_button("Salvar"):
            if nome:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT MAX(Cod_Cliente) FROM clientes")
                    res = cursor.fetchone()[0]
                    novo_id = int(res) + 1 if res is not None else 1
                    
                    cursor.execute(
                        "INSERT INTO clientes (Cod_Cliente, Nome, Tipo_Pessoa, Sexo, Email, Telefone) VALUES (?, ?, ?, ?, ?, ?)",
                        (novo_id, nome, tipo, sexo, email, telefone)
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

# --- LÓGICA DE SALVAMENTO ---
def processar_salvamento(df_editado, tabela):
    df_final = df_editado.copy()
    if 'Nome' in df_final.columns:
        df_final = df_final[df_final['Nome'].fillna('').str.strip() != ""]

    conn = sqlite3.connect(DB_PATH)
    try:
        if 'Status' in df_final.columns:
            df_final['Status'] = df_final['Status'].astype(int)
        df_final.to_sql(tabela, conn, if_exists='replace', index=False)
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
    try: return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return valor

def formatar_markdown_br(valor):
    try: return f"R\\\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return valor

def preparar_download_dados():
    buf = io.BytesIO()
    if os.path.exists(DB_PATH):
        with zipfile.ZipFile(buf, "x") as db_zip:
            db_zip.write(DB_PATH, arcname=os.path.basename(DB_PATH))
    return buf.getvalue()

# --- INTERFACE ---
aba_venda, aba_gestao_p, aba_gestao_c, aba_relatorio = st.tabs([
    "🛒 Registrar Venda", "📋 Gestão de Produtos", "👥 Gestão de Clientes", "📈 Relatórios"
])

# --- ABA 1: REGISTRAR VENDA ---
with aba_venda:
    st.subheader("Nova Venda")
    
    # Verifica se há algo no carrinho para bloquear cabeçalho
    venda_em_curso = len(st.session_state.carrinho) > 0

    if df_c is not None and not df_c.empty and df_p is not None and not df_p.empty:
        c_v1, c_v2 = st.columns(2)
        with c_v1:
            options = sorted(df_c['Nome'].unique())
            if 'selected_cliente' not in st.session_state or st.session_state.selected_cliente not in options:
                st.session_state.selected_cliente = options[0] if options else None
            
            index = options.index(st.session_state.selected_cliente) if st.session_state.selected_cliente in options else 0
            
            # Campo desabilitado se houver itens no carrinho
            nome_cli = st.selectbox(
                "Cliente", 
                options, 
                index=index, 
                key=f"cli_{st.session_state.reset_venda_key}",
                disabled=venda_em_curso
            )
            st.session_state.selected_cliente = nome_cli
            cod_cli = int(df_c[df_c['Nome'] == nome_cli]['Cod_Cliente'].values[0]) if nome_cli else None
        
        with c_v2:
            # Campo desabilitado se houver itens no carrinho
            tema_v = st.text_input(
                "Tema da Venda", 
                key=f"tema_{st.session_state.reset_venda_key}",
                disabled=venda_em_curso
            )
        
        st.divider()
        df_p_ativos = df_p[df_p['Status'] == True].copy()
        
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                nome_p = st.selectbox("Selecione o Produto", sorted(df_p_ativos['Nome'].unique()), key=f"p_s_{st.session_state.reset_prod_sel_key}")
                d_p = df_p_ativos[df_p_ativos['Nome'] == nome_p].iloc[0]
                disp = float(d_p['Estoque Atual']) - sum(i['Qtd'] for i in st.session_state.carrinho if i['Cod_Produto'] == d_p['Cod_Produto'])
                p_venda = float(d_p.get('Preco_Promocional', 0)) if float(d_p.get('Preco_Promocional', 0)) > 0 else float(d_p.get('Preco', 0))
                st.markdown(f"**Preço:** {formatar_markdown_br(p_venda)} | **Estoque Disponível:** {int(disp)}")
            with col2:
                qtd_v = st.number_input("Qtd", min_value=1, max_value=int(disp) if disp > 0 else 1, key=f"q_{st.session_state.reset_prod_sel_key}")
            obs_v = st.text_area("Observações do Item", key=f"obs_{st.session_state.reset_prod_sel_key}", height=70)
            
            if st.button("➕ Adicionar ao Carrinho", width='stretch'):
                if disp >= qtd_v:
                    st.session_state.carrinho.append({
                        'Cod_Produto': d_p['Cod_Produto'], 'Produto': nome_p, 'Qtd': qtd_v,
                        'Preço Un.': p_venda, 'Desconto %': 0.0, 'Total': qtd_v * p_venda, 'Observacoes': obs_v
                    })
                    st.session_state.reset_prod_sel_key += 1
                    st.rerun()

    if st.session_state.carrinho:
        st.markdown("### 🛒 Carrinho")
        df_cart = pd.DataFrame(st.session_state.carrinho)
        ed_cart = st.data_editor(df_cart, hide_index=True, width='stretch', column_config={
            "Cod_Produto": None, "Preço Un.": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
            "Desconto %": st.column_config.NumberColumn(format="%.1f%%", min_value=0.0, max_value=100.0),
            "Total": st.column_config.NumberColumn(format="R$ %.2f", disabled=True)
        }, key=f"ed_cart_{st.session_state.reset_venda_key}")
        
        ed_cart['Total'] = (ed_cart['Qtd'] * ed_cart['Preço Un.']) * (1 - ed_cart['Desconto %'] / 100)
        total_final = ed_cart['Total'].sum()
        st.metric("Total Líquido", formatar_br(total_final))
        
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if st.button("❌ Limpar Carrinho", width='stretch'):
                st.session_state.carrinho = []
                st.session_state.reset_venda_key += 1 # Reseta campos de cliente/tema
                st.rerun()
                
        with c_b2:
            if st.button("✅ Finalizar Venda", type="primary", width='stretch'):
                conn = sqlite3.connect(DB_PATH); cursor = conn.cursor()
                try:
                    cursor.execute("SELECT MAX(`Cod.Venda`) FROM vendas")
                    res = cursor.fetchone()[0]; cv = int(res) + 1 if res is not None else 1
                    dt = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                    for _, item in ed_cart.iterrows():
                        cursor.execute("UPDATE produtos SET `Estoque Atual` = `Estoque Atual` - ? WHERE Cod_Produto = ?", (item['Qtd'], item['Cod_Produto']))
                        cursor.execute("INSERT INTO vendas (`Cod.Venda`, Data, Cod_Cliente, Tema, Cod_Produto, Qtd, Vlr_Unitario_Produto, Desconto_Item, Total, Observacoes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                       (cv, dt, cod_cli, tema_v, item['Cod_Produto'], item['Qtd'], item['Preço Un.'], item['Desconto %'], item['Total'], item['Observacoes']))
                    conn.commit()
                    st.session_state.carrinho = []
                    st.session_state.reset_venda_key += 1
                    st.cache_data.clear()
                    st.success("Venda registrada!")
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
                finally: conn.close()

# --- ABA 2: GESTÃO DE PRODUTOS ---
with aba_gestao_p:
    st.subheader("📋 Gestão de Produtos")
    if st.button("➕ Novo Produto"):
        popup_novo_produto()

    if df_p is not None:
        res_p = st.data_editor(df_p, hide_index=True, num_rows="fixed", width='stretch', key=f"p_ed_{st.session_state.p_key}",
            column_config={
                "Cod_Produto": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
                "Status": st.column_config.CheckboxColumn("Ativo", default=True),
                "Preco": st.column_config.NumberColumn("Preço", format="%.2f", min_value=0.01),
                "Estoque Atual": st.column_config.NumberColumn("Estoque Atual", format="%d")
            })
        if st.button("💾 Salvar Edições de Produtos", width='stretch'):
            if processar_salvamento(res_p, "produtos"):
                st.session_state.p_key += 1
                st.rerun()

# --- ABA 3: GESTÃO DE CLIENTES ---
with aba_gestao_c:
    st.subheader("👥 Gestão de Clientes")
    if st.button("➕ Novo Cliente"):
        popup_novo_cliente()

    if df_c is not None:
        res_c = st.data_editor(df_c, hide_index=True, num_rows="fixed", width='stretch', key=f"c_ed_{st.session_state.c_key}",
            column_config={
                "Cod_Cliente": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
                "Tipo_Pessoa": st.column_config.SelectboxColumn("Tipo", options=["PF", "PJ"]),
                "Sexo": st.column_config.SelectboxColumn("Sexo", options=["M", "F", "O", "NA", ""])
            })
        if st.button("💾 Salvar Edições de Clientes", width='stretch'):
            if processar_salvamento(res_c, "clientes"):
                st.session_state.c_key += 1
                st.rerun()

# --- ABA 4: RELATÓRIOS ---
with aba_relatorio:
    st.subheader("📈 Histórico e Relatórios")
    st.download_button("📥 Baixar Banco de Dados", data=preparar_download_dados(), file_name="backup_fruipartis.zip")
    if df_v is not None and not df_v.empty:
        df_rep = df_v.merge(df_c[['Cod_Cliente', 'Nome']], on='Cod_Cliente', how='left').rename(columns={'Nome': 'Cliente'})
        df_rep = df_rep.merge(df_p[['Cod_Produto', 'Nome']], on='Cod_Produto', how='left').rename(columns={'Nome': 'Produto'})
        st.metric("Faturamento Total", formatar_br(df_rep['Total'].sum()))
        
        col_cv = 'Cod.Venda' if 'Cod.Venda' in df_rep.columns else 'Cod_Venda'
        vendas_resumo = df_rep.groupby([col_cv, 'Data', 'Cliente', 'Tema'])['Total'].sum().reset_index().sort_values(col_cv, ascending=False)
        
        for _, row in vendas_resumo.iterrows():
            with st.expander(f"Venda {row[col_cv]} | {row['Data']} | {row['Cliente']} | {formatar_br(row['Total'])}"):
                itens = df_rep[df_rep[col_cv] == row[col_cv]].copy()
                itens['Vlr. Unitário'] = itens['Vlr_Unitario_Produto'].apply(formatar_br)
                itens['Vlr. Total'] = itens['Total'].apply(formatar_br)
                st.table(itens[['Produto', 'Qtd', 'Vlr. Unitário', 'Vlr. Total', 'Observacoes']])