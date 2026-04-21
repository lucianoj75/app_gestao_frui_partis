import streamlit as st
import pandas as pd
from datetime import datetime
import os
import io
import zipfile

# --- CONFIGURAÇÕES DE ARQUITETURA ---
PASTA_DADOS = 'Dados'
FILE_PRODUTOS = os.path.join(PASTA_DADOS, 'Produtos.csv')
FILE_CLIENTES = os.path.join(PASTA_DADOS, 'Clientes.csv')
FILE_VENDAS = os.path.join(PASTA_DADOS, 'Vendas_Realizadas.csv')
SEPARADOR = ';'

st.set_page_config(page_title="Gestão de Vendas Frui Partis", layout="wide")

# --- FUNÇÕES DE CARREGAMENTO COM CACHE ---
@st.cache_data(ttl=600)
def carregar_estoque():
    return pd.read_csv(FILE_PRODUTOS, sep=SEPARADOR, dtype={'Status': bool})

@st.cache_data(ttl=600)
def carregar_clientes():
    return pd.read_csv(FILE_CLIENTES, sep=SEPARADOR)

def carregar_vendas():
    if os.path.exists(FILE_VENDAS):
        return pd.read_csv(FILE_VENDAS, sep=SEPARADOR)
    return pd.DataFrame()

# --- INICIALIZAÇÃO DO ESTADO ---
if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []
if 'reset_produto_key' not in st.session_state:
    st.session_state.reset_produto_key = 0
if 'reset_venda_key' not in st.session_state:
    st.session_state.reset_venda_key = 0
if 'editor_p_key' not in st.session_state:
    st.session_state.editor_p_key = 0
if 'editor_c_key' not in st.session_state:
    st.session_state.editor_c_key = 0

# --- CARREGAMENTO INICIAL ---
df_p = carregar_estoque()
df_c = carregar_clientes()
df_v = carregar_vendas()

# Tratamento de preços para cálculos
df_p['Preço'] = pd.to_numeric(df_p['Preço'], errors='coerce').fillna(0.0)
df_p['Preço Promocional'] = pd.to_numeric(df_p['Preço Promocional'], errors='coerce').fillna(0.0)

# --- FUNÇÕES AUXILIARES ---
def formatar_br(valor):
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_markdown_br(valor):
    return f"R\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def preparar_download_dados():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "x") as csv_zip:
        for file in [FILE_PRODUTOS, FILE_CLIENTES, FILE_VENDAS]:
            if os.path.exists(file):
                csv_zip.write(file, arcname=os.path.basename(file))
    return buf.getvalue()

# --- INTERFACE ---
aba_venda, aba_gestao_p, aba_gestao_c, aba_relatorio = st.tabs([
    "🛒 Registrar Venda", "📋 Gestão de Produtos", "👥 Gestão de Clientes", "📈 Relatórios"
])

# --- ABA 1: REGISTRAR VENDA ---
with aba_venda:
    st.subheader("Nova Venda")
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        nome_cli = st.selectbox("Selecione o Cliente", df_c['Nome'].unique(), key=f"cli_{st.session_state.reset_venda_key}")
        cod_cli = df_c[df_c['Nome'] == nome_cli]['Cod_Cliente'].values[0]
    with col_v2:
        tema_venda = st.text_input("Tema da Venda", key=f"tema_{st.session_state.reset_venda_key}")
    
    st.divider()
    
    df_p_ativos = df_p[df_p['Status'] == True].copy()
    
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            nome_p = st.selectbox("Escolha o Produto", df_p_ativos['Nome'].unique(), key=f"p_sel_{st.session_state.reset_produto_key}")
            dados_p = df_p_ativos[df_p_ativos['Nome'] == nome_p].iloc[0]
            cod_p, estoque_p = dados_p['Cod_Produto'], float(dados_p['Estoque Atual'])
            p_base, p_promo = float(dados_p['Preço']), float(dados_p['Preço Promocional'])
            
            qtd_car = sum(item['Qtd'] for item in st.session_state.carrinho if item['Cod_Produto'] == cod_p)
            disp = estoque_p - qtd_car
            
            info_txt = f"**Cód:** {cod_p} | **Preço:** {formatar_markdown_br(p_base)} | **Estoque:** {int(disp)}"
            if p_promo > 0: info_txt += f" | 🔥 **PROMOÇÃO: {formatar_markdown_br(p_promo)}**"
            st.markdown(info_txt)
        with c2:
            max_v = int(disp) if disp > 0 else 1
            qtd_v = st.number_input("Qtd", min_value=1, max_value=max_v, step=1, key=f"q_{st.session_state.reset_produto_key}")

        obs_item = st.text_area("Observações do Produto", height=70, key=f"o_{st.session_state.reset_produto_key}")
        
        if st.button("➕ Adicionar ao Carrinho", width='stretch'):
            if disp >= qtd_v:
                preco_final = p_promo if p_promo > 0 else p_base
                st.session_state.carrinho.append({
                    'Cod_Produto': cod_p, 'Produto': nome_p, 'Qtd': qtd_v,
                    'Preço Un.': preco_final, 'Desconto %': 0.0, 
                    'Total': qtd_v * preco_final, 'Observacoes': obs_item
                })
                st.session_state.reset_produto_key += 1
                st.rerun()

    if st.session_state.carrinho:
        st.markdown("### 🛒 Itens no Carrinho")
        df_cart = pd.DataFrame(st.session_state.carrinho)
        
        df_editado = st.data_editor(
            df_cart,
            column_config={
                "Cod_Produto": None,
                "Produto": st.column_config.TextColumn("Produto", disabled=True),
                "Qtd": st.column_config.NumberColumn("Qtd", disabled=True),
                "Preço Un.": st.column_config.NumberColumn("Preço Un.", format="R$ %.2f", disabled=True),
                "Desconto %": st.column_config.NumberColumn("Desconto (%)", min_value=0.0, max_value=100.0, step=0.5, format="%.1f%%"),
                "Total": st.column_config.NumberColumn("Total Item", format="R$ %.2f", disabled=True),
                "Observacoes": st.column_config.TextColumn("Observações")
            },
            hide_index=True, width='stretch', key=f"ed_cart_{st.session_state.reset_venda_key}"
        )

        df_editado['Total'] = (df_editado['Qtd'] * df_editado['Preço Un.']) * (1 - df_editado['Desconto %'] / 100)
        total_venda = df_editado['Total'].sum()
        
        c_tot1, c_tot2 = st.columns([2, 1])
        with c_tot2:
            st.metric("Total Líquido da Venda", formatar_br(total_venda))

        if st.button("✅ Finalizar Venda", type="primary", width='stretch'):
            cod_v = int(df_v['Cod.Venda'].max()) + 1 if not df_v.empty else 1
            dt_v = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            
            novas = []
            for _, item in df_editado.iterrows():
                idx = df_p[df_p['Cod_Produto'] == item['Cod_Produto']].index[0]
                df_p.at[idx, 'Estoque Atual'] -= item['Qtd']
                novas.append({
                    'Cod.Venda': cod_v, 'Data': dt_v, 'Cod_Cliente': cod_cli, 
                    'Tema': str(tema_venda), 'Cod_Produto': item['Cod_Produto'], 
                    'Qtd': item['Qtd'], 'Vlr_Unitario_Produto': item['Preço Un.'],
                    'Desconto_Item': item['Desconto %'], 'Total': item['Total'], 
                    'Observacoes': item['Observacoes']
                })
            
            df_p.to_csv(FILE_PRODUTOS, index=False, sep=SEPARADOR)
            pd.concat([df_v, pd.DataFrame(novas)], ignore_index=True).to_csv(FILE_VENDAS, index=False, sep=SEPARADOR)
            
            st.cache_data.clear()
            st.session_state.carrinho = []
            st.session_state.reset_venda_key += 1
            st.session_state.reset_produto_key += 1
            st.success("Venda registrada!")
            st.rerun()

# --- ABA 2: GESTÃO DE PRODUTOS ---
with aba_gestao_p:
    st.subheader("Painel de Produtos")
    p_key = f"ed_p_{st.session_state.editor_p_key}"
    df_res_p = st.data_editor(df_p, hide_index=True, width='stretch', key=p_key)
    if st.button("💾 Salvar Alterações de Produtos", width='stretch'):
        df_res_p.to_csv(FILE_PRODUTOS, index=False, sep=SEPARADOR)
        st.cache_data.clear()
        st.session_state.editor_p_key += 1
        st.rerun()

# --- ABA 3: GESTÃO DE CLIENTES ---
with aba_gestao_c:
    st.subheader("Painel de Clientes")
    c_key = f"ed_c_{st.session_state.editor_c_key}"
    
    # Exibição editável baseada na estrutura de Clientes.csv (protegendo apenas o código)
    df_res_c = st.data_editor(
        df_c, 
        hide_index=True, 
        width='stretch', 
        key=c_key,
        column_config={
            "Cod_Cliente": st.column_config.TextColumn("Cód. Cliente", disabled=True)
        }
    )
    
    if st.button("💾 Salvar Alterações de Clientes", width='stretch'):
        df_res_c.to_csv(FILE_CLIENTES, index=False, sep=SEPARADOR)
        st.cache_data.clear() # Atualiza os selectboxes da aba de venda
        st.session_state.editor_c_key += 1
        st.rerun()

# --- ABA 4: RELATÓRIOS ---
with aba_relatorio:
    st.subheader("Análise de Resultados")
    with st.expander("💾 Backup"):
        st.download_button("📥 Baixar CSVs", data=preparar_download_dados(), file_name="backup.zip", width='stretch')
    
    if not df_v.empty:
        df_display = df_v.merge(df_c[['Cod_Cliente', 'Nome']], on='Cod_Cliente', how='left').rename(columns={'Nome': 'Cliente'})
        df_display = df_display.merge(df_p[['Cod_Produto', 'Nome']], on='Cod_Produto', how='left').rename(columns={'Nome': 'Produto'})
        
        c1, c2 = st.columns([2, 1])
        with c1: f_cli = st.multiselect("Filtrar Cliente", options=sorted(df_display['Cliente'].unique()))
        with c2: b_tema = st.text_input("Busca Tema/Cliente")
        
        df_f = df_display.copy()
        if f_cli: df_f = df_f[df_f['Cliente'].isin(f_cli)]
        if b_tema: df_f = df_f[df_f['Tema'].str.contains(b_tema, case=False, na=False) | df_f['Cliente'].str.contains(b_tema, case=False, na=False)]
        
        k1, k2 = st.columns(2)
        k1.metric("Faturamento", formatar_br(df_f['Total'].sum()))
        k2.metric("Vendas", df_f['Cod.Venda'].nunique())
        
        resumo = df_f.groupby(['Cod.Venda', 'Data', 'Cliente', 'Tema'])['Total'].sum().reset_index().sort_values('Cod.Venda', ascending=False)
        for _, row in resumo.iterrows():
            with st.expander(f"📦 {row['Cod.Venda']} | {row['Cliente']} | {row['Tema']} | {formatar_br(row['Total'])}"):
                detalhe = df_f[df_f['Cod.Venda'] == row['Cod.Venda']].copy()
                
                if 'Vlr_Unitario_Produto' in detalhe.columns:
                    detalhe['Vlr.Un.'] = detalhe['Vlr_Unitario_Produto'].apply(formatar_br)
                detalhe['Total'] = detalhe['Total'].apply(formatar_br)
                if 'Desconto_Item' in detalhe.columns:
                    detalhe['Desconto'] = detalhe['Desconto_Item'].apply(lambda x: f"{x:.1f}%")
                
                col_view = ['Produto', 'Qtd', 'Vlr.Un.', 'Desconto', 'Total', 'Observacoes']
                st.table(detalhe[[c for c in col_view if c in detalhe.columns]])
    else:
        st.info("Nenhuma venda encontrada.")