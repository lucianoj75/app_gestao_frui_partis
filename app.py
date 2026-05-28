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

# --- MIGRAÇÃO DO BANCO DE DADOS ---
def migrar_banco():
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = [t[0] for t in cursor.fetchall()]
        # Criar tabela vendas normalizada se não existir
        if 'vendas' not in tabelas:
            cursor.execute("""
                CREATE TABLE vendas (
                    Cod_Venda   INTEGER PRIMARY KEY,
                    Data        TEXT,
                    Cod_Cliente INTEGER,
                    Tema        TEXT,
                    Total       REAL,
                    Vlr_Pago    REAL DEFAULT 0,
                    FOREIGN KEY (Cod_Cliente) REFERENCES clientes(Cod_Cliente)
                )
            """)
        # Criar tabela vendas_itens se não existir
        if 'vendas_itens' not in tabelas:
            cursor.execute("""
                CREATE TABLE vendas_itens (
                    Cod_Item     INTEGER PRIMARY KEY AUTOINCREMENT,
                    Cod_Venda    INTEGER,
                    Cod_Produto  INTEGER,
                    Qtd          INTEGER,
                    Vlr_Unitario REAL,
                    Desconto     REAL DEFAULT 0,
                    Total_Item   REAL,
                    Observacoes  TEXT,
                    FOREIGN KEY (Cod_Venda)  REFERENCES vendas(Cod_Venda),
                    FOREIGN KEY (Cod_Produto) REFERENCES produtos(Cod_Produto)
                )
            """)
        conn.commit()
    except Exception as e:
        st.error(f"Erro na migração do banco: {e}")
    finally:
        conn.close()

migrar_banco()

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
    df = executar_query("SELECT * FROM produtos")
    if df is not None and 'Status' in df.columns:
        df['Status'] = df['Status'].map({1: True, 0: False, 'True': True, 'False': False, True: True, False: False}).fillna(True)
    return df

@st.cache_data(ttl=600)
def carregar_clientes():
    return executar_query("SELECT * FROM clientes")

def carregar_vendas():
    query = (
        "SELECT v.Cod_Venda, v.Data, v.Cod_Cliente, v.Tema, v.Total, v.Vlr_Pago, "
        "vi.Cod_Item, vi.Cod_Produto, vi.Qtd, vi.Vlr_Unitario, vi.Desconto, vi.Total_Item, vi.Observacoes "
        "FROM vendas v "
        "LEFT JOIN vendas_itens vi ON v.Cod_Venda = vi.Cod_Venda "
        "ORDER BY v.Cod_Venda DESC"
    )
    return executar_query(query)

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

@st.dialog("Produto sem Estoque")
def popup_confirmar_sem_estoque():
    item = st.session_state.item_pendente
    st.warning(f"O produto **{item['Produto']}** está sem estoque. Deseja seguir com a venda?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Sim", type="primary", width='stretch'):
            st.session_state.carrinho.append(item)
            st.session_state.item_pendente = None
            st.session_state.reset_prod_sel_key += 1
            st.rerun()
    with c2:
        if st.button("❌ Não", width='stretch'):
            st.session_state.item_pendente = None
            st.rerun()


@st.dialog("💳 Pagamento")
def popup_pagamento():
    dados = st.session_state.pagamento_pendente
    total = dados['total']
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
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT MAX(Cod_Venda) FROM vendas")
                res = cursor.fetchone()[0]
                cv = int(res) + 1 if res is not None else 1
                dt = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                # Inserir cabeçalho da venda
                cursor.execute(
                    "INSERT INTO vendas (Cod_Venda, Data, Cod_Cliente, Tema, Total, Vlr_Pago) VALUES (?, ?, ?, ?, ?, ?)",
                    (cv, dt, dados['cod_cli'], dados['tema'], dados['total'], vlr_pago)
                )
                # Inserir itens e atualizar estoque
                for item in dados['itens']:
                    cursor.execute("UPDATE produtos SET `Estoque Atual` = `Estoque Atual` - ? WHERE Cod_Produto = ?", (item['Qtd'], item['Cod_Produto']))
                    cursor.execute(
                        "INSERT INTO vendas_itens (Cod_Venda, Cod_Produto, Qtd, Vlr_Unitario, Desconto, Total_Item, Observacoes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cv, item['Cod_Produto'], item['Qtd'], item['Preço Un.'], item['Desconto %'], item['Total'], item['Observacoes'])
                    )
                conn.commit()
                st.session_state.carrinho = []
                st.session_state.pagamento_pendente = None
                st.session_state.reset_venda_key += 1
                st.session_state.selected_cliente = "-- Selecione --"
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

    PLACEHOLDER = "-- Selecione --"

    if df_c is not None and not df_c.empty and df_p is not None and not df_p.empty:
        c_v1, c_v2 = st.columns(2)
        with c_v1:
            options_cli = [PLACEHOLDER] + sorted(df_c['Nome'].unique())
            if 'selected_cliente' not in st.session_state or st.session_state.selected_cliente not in options_cli:
                st.session_state.selected_cliente = PLACEHOLDER

            index_cli = options_cli.index(st.session_state.selected_cliente)

            # Campo desabilitado se houver itens no carrinho
            nome_cli = st.selectbox(
                "Cliente",
                options_cli,
                index=index_cli,
                key=f"cli_{st.session_state.reset_venda_key}",
                disabled=venda_em_curso
            )
            st.session_state.selected_cliente = nome_cli
            cod_cli = int(df_c[df_c['Nome'] == nome_cli]['Cod_Cliente'].values[0]) if nome_cli != PLACEHOLDER else None

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
                options_prod = [PLACEHOLDER] + sorted(df_p_ativos['Nome'].unique())
                nome_p = st.selectbox("Selecione o Produto", options_prod, key=f"p_s_{st.session_state.reset_prod_sel_key}")

            if nome_p != PLACEHOLDER:
                with col1:
                    d_p = df_p_ativos[df_p_ativos['Nome'] == nome_p].iloc[0]
                    disp = float(d_p['Estoque Atual']) - sum(i['Qtd'] for i in st.session_state.carrinho if i['Cod_Produto'] == d_p['Cod_Produto'])
                    p_venda = float(d_p.get('Preco_Promocional', 0)) if float(d_p.get('Preco_Promocional', 0)) > 0 else float(d_p.get('Preco', 0))
                    st.markdown(f"**Preço:** {formatar_markdown_br(p_venda)} | **Estoque Disponível:** {int(disp)}")
                with col2:
                    qtd_v = st.number_input("Qtd", min_value=1, key=f"q_{st.session_state.reset_prod_sel_key}")
                obs_v = st.text_area("Observações do Item", key=f"obs_{st.session_state.reset_prod_sel_key}", height=70)

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
                st.session_state.pagamento_pendente = {
                    'itens': ed_cart.to_dict('records'),
                    'total': total_final,
                    'total_fmt': formatar_br(total_final),
                    'cod_cli': cod_cli,
                    'tema': tema_v
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

        res_p = st.data_editor(df_p, hide_index=True, num_rows="fixed", width='stretch', key=f"p_ed_{st.session_state.p_key}",
            column_config={
                "Cod_Produto": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
                "Status": st.column_config.CheckboxColumn("Ativo", default=True),
                "Preco": st.column_config.NumberColumn("Preço", format="%.2f", min_value=0.01),
                "Estoque Atual": st.column_config.NumberColumn("Estoque Atual", format="%d")
            })

        if not df_p.equals(res_p.reset_index(drop=True)):
            st.session_state.p_alterado = True

        if salvar_p:
            if processar_salvamento(res_p, "produtos"):
                st.session_state.p_alterado = False
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
        # Enriquecer com nomes de cliente e produto
        df_rep = df_v.merge(df_c[['Cod_Cliente', 'Nome']], on='Cod_Cliente', how='left').rename(columns={'Nome': 'Cliente'})
        df_rep = df_rep.merge(df_p[['Cod_Produto', 'Nome']], on='Cod_Produto', how='left').rename(columns={'Nome': 'Produto'})

        # Resumo por venda (cabeçalho)
        vendas_cab = df_rep.drop_duplicates(subset='Cod_Venda')[['Cod_Venda', 'Data', 'Cliente', 'Tema', 'Total', 'Vlr_Pago']].sort_values('Cod_Venda', ascending=False)

        # Converter Data para datetime para filtro
        vendas_cab['Data_dt'] = pd.to_datetime(vendas_cab['Data'], dayfirst=True, errors='coerce')
        data_min = vendas_cab['Data_dt'].min().date()
        data_max = vendas_cab['Data_dt'].max().date()

        # Inicializar valor de data padrão
        if st.session_state.filtro_data_val is None:
            st.session_state.filtro_data_val = (data_min, data_max)

        # --- FILTROS ---
        with st.expander("🔍 Filtros", expanded=False):
            f1, f2, f3 = st.columns(3)
            with f1:
                clientes_opcoes = ["Todos"] + sorted(vendas_cab['Cliente'].dropna().unique().tolist())
                idx_cli = clientes_opcoes.index(st.session_state.filtro_cliente_val) if st.session_state.filtro_cliente_val in clientes_opcoes else 0
                filtro_cliente = st.selectbox("Cliente", clientes_opcoes, index=idx_cli)
            with f2:
                filtro_data = st.date_input("Intervalo de Data", value=st.session_state.filtro_data_val)
            with f3:
                filtro_pendente = st.checkbox("Somente com valor pendente", value=st.session_state.filtro_pendente_val)

            fb1, fb2 = st.columns(2)
            with fb1:
                btn_filtrar = st.button("🔍 Filtrar", type="primary", width='stretch')
            with fb2:
                btn_limpar = st.button("🗑️ Limpar Filtros", width='stretch')

        if btn_limpar:
            st.session_state.filtro_cliente_val = "Todos"
            st.session_state.filtro_data_val = (data_min, data_max)
            st.session_state.filtro_pendente_val = False
            st.session_state.filtros_aplicados = False
            st.rerun()

        if btn_filtrar:
            if isinstance(filtro_data, tuple) and len(filtro_data) == 2:
                diff = (filtro_data[1] - filtro_data[0]).days
                if diff > 31:
                    st.error("O intervalo de datas não pode ser maior que 31 dias.")
                else:
                    st.session_state.filtro_cliente_val = filtro_cliente
                    st.session_state.filtro_data_val = filtro_data
                    st.session_state.filtro_pendente_val = filtro_pendente
                    st.session_state.filtros_aplicados = True
                    st.rerun()
            else:
                st.error("Selecione um intervalo de datas válido (data inicial e data final).")

        # Aplicar filtros salvos no session_state
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
                    itens['Vlr. Total'] = itens['Total_Item'].apply(formatar_br)
                    st.table(itens[['Produto', 'Qtd', 'Vlr. Unitário', 'Desconto', 'Vlr. Total', 'Observacoes']])