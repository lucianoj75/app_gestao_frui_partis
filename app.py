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

# --- 1. INICIALIZAÇÃO DO ESTADO (PREVENÇÃO DE KEYERROR) ---
if 'p_key' not in st.session_state: st.session_state.p_key = 0
if 'c_key' not in st.session_state: st.session_state.c_key = 0
if 'carrinho' not in st.session_state: st.session_state.carrinho = []
if 'reset_venda_key' not in st.session_state: st.session_state.reset_venda_key = 0
if 'reset_prod_sel_key' not in st.session_state: st.session_state.reset_prod_sel_key = 0

# --- FUNÇÕES DE CARREGAMENTO ---
@st.cache_data(ttl=600)
def carregar_estoque():
    df = pd.read_csv(FILE_PRODUTOS, sep=SEPARADOR)
    if 'Status' in df.columns:
        df['Status'] = df['Status'].map({'True': True, 'False': False, True: True, False: False}).fillna(True)
    return df

@st.cache_data(ttl=600)
def carregar_clientes():
    return pd.read_csv(FILE_CLIENTES, sep=SEPARADOR)

def carregar_vendas():
    if os.path.exists(FILE_VENDAS):
        return pd.read_csv(FILE_VENDAS, sep=SEPARADOR)
    return pd.DataFrame()

# --- LÓGICA DE VALIDAÇÃO E SALVAMENTO ENXUTA ---
def processar_salvamento(df_editado, coluna_id, caminho_arquivo, tipo_entidade):
    df_final = df_editado.copy()
    
    # Limpeza básica: remove linhas onde o Nome está totalmente vazio
    if 'Nome' in df_final.columns:
        df_final = df_final[df_final['Nome'].fillna('').str.strip() != ""]

    if tipo_entidade == "PRODUTOS":
        # Se o Estoque Atual não for informado, grava zero como valor default
        if 'Estoque Atual' in df_final.columns:
            df_final['Estoque Atual'] = df_final['Estoque Atual'].fillna(0)
            
        # Converte Preço para numérico (o que não for número vira NaN)
        df_final['Preço'] = pd.to_numeric(df_final['Preço'], errors='coerce')
        
        # Validação funcional: Verifica se existe algum preço inválido (NaN ou <= 0)
        if df_final['Preço'].isna().any() or (df_final['Preço'] <= 0).any():
            st.error("Erro: Todos os produtos ativos devem ter um 'Preço' válido e maior que zero.")
            return False
            
    elif tipo_entidade == "CLIENTES":
        if 'Tipo_Pessoa' in df_final.columns:
            df_final['Tipo_Pessoa'] = df_final['Tipo_Pessoa'].str.upper().str.strip()
            if not df_final['Tipo_Pessoa'].isin(['PF', 'PJ']).all():
                st.error("Erro: O campo 'Tipo_Pessoa' deve ser PF ou PJ.")
                return False

    # Auto-incremento de IDs
    mask_novos = df_final[coluna_id].isna()
    if mask_novos.any():
        ultimo_id = pd.to_numeric(df_final[coluna_id], errors='coerce').max()
        if pd.isna(ultimo_id): ultimo_id = 0
        novos_ids = range(int(ultimo_id) + 1, int(ultimo_id) + 1 + mask_novos.sum())
        df_final.loc[mask_novos, coluna_id] = list(novos_ids)
    
    df_final[coluna_id] = df_final[coluna_id].astype(int)
    df_final.to_csv(caminho_arquivo, index=False, sep=SEPARADOR)
    st.cache_data.clear()
    return True

# --- CARREGAMENTO INICIAL ---
df_p = carregar_estoque()
df_c = carregar_clientes()
df_v = carregar_vendas()

# --- AUXILIARES ---
def formatar_br(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

def formatar_markdown_br(valor):
    try:
        return f"R\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

def preparar_download_dados():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "x") as csv_zip:
        for f in [FILE_PRODUTOS, FILE_CLIENTES, FILE_VENDAS]:
            if os.path.exists(f): csv_zip.write(f, arcname=os.path.basename(f))
    return buf.getvalue()

# --- INTERFACE ---
aba_venda, aba_gestao_p, aba_gestao_c, aba_relatorio = st.tabs([
    "🛒 Registrar Venda", "📋 Gestão de Produtos", "👥 Gestão de Clientes", "📈 Relatórios"
])

# --- ABA 1: REGISTRAR VENDA ---
with aba_venda:
    st.subheader("Nova Venda")
    if not df_c.empty and not df_p.empty:
        c_v1, c_v2 = st.columns(2)
        with c_v1:
            nome_cli = st.selectbox("Cliente", sorted(df_c['Nome'].unique()), key=f"cli_{st.session_state.reset_venda_key}")
            cod_cli = df_c[df_c['Nome'] == nome_cli]['Cod_Cliente'].values[0]
        with c_v2:
            tema_v = st.text_input("Tema da Venda", key=f"tema_{st.session_state.reset_venda_key}")
        
        st.divider()
        df_p_ativos = df_p[df_p['Status'] == True].copy()
        
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                nome_p = st.selectbox("Selecione o Produto", sorted(df_p_ativos['Nome'].unique()), key=f"p_s_{st.session_state.reset_prod_sel_key}")
                d_p = df_p_ativos[df_p_ativos['Nome'] == nome_p].iloc[0]
                disp = float(d_p['Estoque Atual']) - sum(i['Qtd'] for i in st.session_state.carrinho if i['Cod_Produto'] == d_p['Cod_Produto'])
                p_venda = float(d_p['Preço Promocional']) if float(d_p['Preço Promocional']) > 0 else float(d_p['Preço'])
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
            "Cod_Produto": None, 
            "Preço Un.": st.column_config.NumberColumn(format="R$ %.2f", disabled=True),
            "Desconto %": st.column_config.NumberColumn(format="%.1f%%", min_value=0.0, max_value=100.0),
            "Total": st.column_config.NumberColumn(format="R$ %.2f", disabled=True)
        }, key=f"ed_cart_{st.session_state.reset_venda_key}")
        
        ed_cart['Total'] = (ed_cart['Qtd'] * ed_cart['Preço Un.']) * (1 - ed_cart['Desconto %'] / 100)
        total_final = ed_cart['Total'].sum()
        st.metric("Total Líquido", formatar_br(total_final))
        
        if st.button("✅ Finalizar Venda", type="primary", width='stretch'):
            cv = int(df_v['Cod.Venda'].max()) + 1 if not df_v.empty else 1
            dt = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            novas_linhas = []
            for _, item in ed_cart.iterrows():
                idx = df_p[df_p['Cod_Produto'] == item['Cod_Produto']].index[0]
                df_p.at[idx, 'Estoque Atual'] -= item['Qtd']
                novas_linhas.append({
                    'Cod.Venda': cv, 'Data': dt, 'Cod_Cliente': cod_cli, 'Tema': tema_v,
                    'Cod_Produto': item['Cod_Produto'], 'Qtd': item['Qtd'], 
                    'Vlr_Unitario_Produto': item['Preço Un.'], 'Desconto_Item': item['Desconto %'],
                    'Total': item['Total'], 'Observacoes': item['Observacoes']
                })
            df_p.to_csv(FILE_PRODUTOS, index=False, sep=SEPARADOR)
            pd.concat([df_v, pd.DataFrame(novas_linhas)], ignore_index=True).to_csv(FILE_VENDAS, index=False, sep=SEPARADOR)
            st.session_state.carrinho = []
            st.session_state.reset_venda_key += 1
            st.cache_data.clear()
            st.success("Venda registrada com sucesso!")
            st.rerun()

# --- ABA 2: GESTÃO DE PRODUTOS ---
with aba_gestao_p:
    st.subheader("📋 Gestão de Produtos")
    st.caption("Insira o Nome e o Preço para salvar novos itens.")
    res_p = st.data_editor(df_p, hide_index=True, num_rows="dynamic", width='stretch', key=f"p_ed_{st.session_state.p_key}",
        column_config={
            "Cod_Produto": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
            "Status": st.column_config.CheckboxColumn("Ativo", default=True),
            "Preço": st.column_config.NumberColumn("Preço", format="%.2f", min_value=0.01),
            "Estoque Atual": st.column_config.NumberColumn("Estoque Atual", format="%d")
        })
    if st.button("💾 Salvar Alterações de Produtos", width='stretch'):
        if processar_salvamento(res_p, "Cod_Produto", FILE_PRODUTOS, "PRODUTOS"):
            st.session_state.p_key += 1
            st.rerun()

# --- ABA 3: GESTÃO DE CLIENTES ---
with aba_gestao_c:
    st.subheader("👥 Gestão de Clientes")
    res_c = st.data_editor(df_c, hide_index=True, num_rows="dynamic", width='stretch', key=f"c_ed_{st.session_state.c_key}",
        column_config={
            "Cod_Cliente": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
            "Tipo_Pessoa": st.column_config.SelectboxColumn("Tipo_Pessoa", options=["PF", "PJ"]),
            "Sexo": st.column_config.SelectboxColumn("Sexo", options=["M", "F", "O", "NA", ""])
        })
    if st.button("💾 Salvar Alterações de Clientes", width='stretch'):
        if processar_salvamento(res_c, "Cod_Cliente", FILE_CLIENTES, "CLIENTES"):
            st.session_state.c_key += 1
            st.rerun()

# --- ABA 4: RELATÓRIOS ---
with aba_relatorio:
    st.subheader("📈 Histórico e Relatórios")
    st.download_button("📥 Baixar Backup (ZIP)", data=preparar_download_dados(), file_name="backup_fruipartis.zip")
    
    if not df_v.empty:
        df_rep = df_v.merge(df_c[['Cod_Cliente', 'Nome']], on='Cod_Cliente', how='left').rename(columns={'Nome': 'Cliente'})
        df_rep = df_rep.merge(df_p[['Cod_Produto', 'Nome']], on='Cod_Produto', how='left').rename(columns={'Nome': 'Produto'})
        
        st.metric("Faturamento Total", formatar_br(df_rep['Total'].sum()))
        
        vendas_resumo = df_rep.groupby(['Cod.Venda', 'Data', 'Cliente', 'Tema'])['Total'].sum().reset_index().sort_values('Cod.Venda', ascending=False)
        
        for _, row in vendas_resumo.iterrows():
            # Exibe: Venda ID | Data | Cliente | Tema | Valor Total
            header_venda = f"Venda {row['Cod.Venda']} | {row['Data']} | {row['Cliente']} | {row['Tema']} | {formatar_br(row['Total'])}"
            with st.expander(header_venda):
                itens = df_rep[df_rep['Cod.Venda'] == row['Cod.Venda']].copy()
                itens['Vlr. Unitário'] = itens['Vlr_Unitario_Produto'].apply(formatar_br)
                itens['Desconto (%)'] = itens['Desconto_Item'].apply(lambda x: f"{x}%")
                itens['Vlr. Total'] = itens['Total'].apply(formatar_br)
                st.table(itens[['Produto', 'Qtd', 'Vlr. Unitário', 'Desconto (%)', 'Vlr. Total', 'Observacoes']])
    else:
        st.info("Nenhuma venda realizada ainda.")