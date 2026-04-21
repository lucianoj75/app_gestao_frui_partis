import streamlit as st
import pandas as pd
from datetime import datetime
import os
import plotly.express as px
import io
import zipfile

# --- CONFIGURAÇÕES DE ARQUITETURA ---
PASTA_DADOS = 'Dados'
FILE_PRODUTOS = os.path.join(PASTA_DADOS, 'Produtos.csv')
FILE_CLIENTES = os.path.join(PASTA_DADOS, 'Clientes.csv')
FILE_VENDAS = os.path.join(PASTA_DADOS, 'Vendas_Realizadas.csv')
SEPARADOR = ';'

st.set_page_config(page_title="Gestão de Vendas Frui Partis", layout="wide")

# --- INICIALIZAÇÃO DO ESTADO ---
if 'carrinho' not in st.session_state:
    st.session_state.carrinho = []
if 'reset_key' not in st.session_state:
    st.session_state.reset_key = 0
if 'editor_key_seed' not in st.session_state:
    st.session_state.editor_key_seed = 0

def carregar_dados():
    # Carrega produtos e clientes garantindo que códigos sejam strings para o merge
    df_p = pd.read_csv(FILE_PRODUTOS, sep=SEPARADOR, dtype={'Codigo': str, 'Status': bool})
    df_p['Preço'] = pd.to_numeric(df_p['Preço'], errors='coerce').fillna(0.0)
    df_p['Preço Promocional'] = pd.to_numeric(df_p['Preço Promocional'], errors='coerce').fillna(0.0)
    
    df_c = pd.read_csv(FILE_CLIENTES, sep=SEPARADOR, dtype={'Codigo': str})
    return df_p, df_c

def formatar_br(valor):
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_markdown_br(valor):
    return f"R\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_proximo_cod_venda():
    if not os.path.exists(FILE_VENDAS): return 1
    try:
        df_v = pd.read_csv(FILE_VENDAS, sep=SEPARADOR)
        return int(df_v['Cod.Venda'].max()) + 1 if not df_v.empty else 1
    except: return 1

def preparar_download_dados():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "x") as csv_zip:
        for file in [FILE_PRODUTOS, FILE_CLIENTES, FILE_VENDAS]:
            if os.path.exists(file):
                csv_zip.write(file, arcname=os.path.basename(file))
    return buf.getvalue()

# --- CARREGAMENTO ---
try:
    df_p, df_c = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

aba_venda, aba_gestao, aba_relatorio = st.tabs([
    "🛒 Registrar Venda", "📋 Gestão de Produtos", "📈 Relatórios"
])

# --- ABA 1: REGISTRAR VENDA ---
with aba_venda:
    st.subheader("Nova Venda")
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        # Seleciona pelo nome, mas guardaremos o código
        nome_cli = st.selectbox("Selecione o Cliente", df_c['Nome'].unique(), key="venda_cliente")
        cod_cli = df_c[df_c['Nome'] == nome_cli]['Codigo'].values[0]
    with col_v2:
        tema_venda = st.text_input("Tema da Venda", key="tema_venda")
    
    st.divider()
    
    df_p_ativos = df_p[df_p['Status'] == True].copy()
    
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            nome_p = st.selectbox("Escolha o Produto", df_p_ativos['Nome'].unique(), key="add_p")
            dados_p = df_p_ativos[df_p_ativos['Nome'] == nome_p].iloc[0]
            
            cod_p, estoque_p = dados_p['Codigo'], float(dados_p['Estoque Atual'])
            p_base, p_promo = float(dados_p['Preço']), float(dados_p['Preço Promocional'])

            qtd_car = sum(item['Qtd'] for item in st.session_state.carrinho if item['Cod.Produto'] == cod_p)
            disp = estoque_p - qtd_car
            
            info_txt = f"**Cód:** {cod_p} | **Preço:** {formatar_markdown_br(p_base)} | **Estoque:** {int(disp)}"
            if p_promo > 0:
                info_txt += f" | 🔥 **PROMOÇÃO: {formatar_markdown_br(p_promo)}**"
            st.markdown(info_txt)

        with c2:
            max_v = int(disp) if disp > 0 else 1
            qtd_v = st.number_input("Qtd", min_value=1, max_value=max_v, step=1, key=f"q_{st.session_state.reset_key}")

        obs_item = st.text_area("Observações do Produto", height=70, key=f"o_{st.session_state.reset_key}")
        
        if st.button("➕ Adicionar ao Carrinho", width='stretch'):
            if disp >= qtd_v:
                preco_final = p_promo if p_promo > 0 else p_base
                st.session_state.carrinho.append({
                    'Cod.Produto': cod_p, 
                    'Produto': nome_p, # Apenas para exibição temporária no carrinho
                    'Qtd': qtd_v,
                    'Preço Un.': preco_final, 
                    'Total': qtd_v * preco_final, 
                    'Observacoes': obs_item
                })
                st.session_state.reset_key += 1
                st.rerun()

    if st.session_state.carrinho:
        st.markdown("### 🛒 Carrinho Atual")
        df_cart = pd.DataFrame(st.session_state.carrinho).copy()
        df_cart_display = df_cart[['Cod.Produto', 'Produto', 'Qtd', 'Preço Un.', 'Total', 'Observacoes']].copy()
        df_cart_display['Preço Un.'] = df_cart_display['Preço Un.'].apply(formatar_br)
        df_cart_display['Total'] = df_cart_display['Total'].apply(formatar_br)
        st.table(df_cart_display)
        
        total_v = sum(item['Total'] for item in st.session_state.carrinho)
        st.markdown(f"### Total do Pedido: {formatar_markdown_br(total_v)}")
        
        if st.button("✅ Finalizar Venda", type="primary", width='stretch'):
            cod_v = gerar_proximo_cod_venda()
            dt_v = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            novas = []
            for item in st.session_state.carrinho:
                # Atualiza estoque
                idx = df_p[df_p['Codigo'] == item['Cod.Produto']].index[0]
                df_p.at[idx, 'Estoque Atual'] -= item['Qtd']
                
                # Prepara linha normalizada (sem nomes)
                novas.append({
                    'Cod.Venda': cod_v, 
                    'Data': dt_v, 
                    'Cod.Cliente': cod_cli, # FK Cliente
                    'Tema': tema_venda,
                    'Cod.Produto': item['Cod.Produto'], # FK Produto
                    'Qtd': item['Qtd'], 
                    'Total': item['Total'], 
                    'Observacoes': item['Observacoes']
                })
            
            df_p.to_csv(FILE_PRODUTOS, index=False, sep=SEPARADOR)
            hist_vendas = pd.read_csv(FILE_VENDAS, sep=SEPARADOR, dtype={'Cod.Produto': str, 'Cod.Cliente': str}) if os.path.exists(FILE_VENDAS) else pd.DataFrame()
            pd.concat([hist_vendas, pd.DataFrame(novas)], ignore_index=True).to_csv(FILE_VENDAS, index=False, sep=SEPARADOR)
            
            st.session_state.carrinho = []
            st.success("Venda finalizada com sucesso!")
            st.rerun()

# --- ABA 2: GESTÃO ---
with aba_gestao:
    st.subheader("Painel de Produtos")
    c_key = f"ed_{st.session_state.editor_key_seed}"
    df_res = st.data_editor(
        df_p,
        column_config={
            "Codigo": st.column_config.TextColumn("Cód.", disabled=True),
            "Preço": st.column_config.NumberColumn("Preço Base", format="%.2f"),
            "Preço Promocional": st.column_config.NumberColumn("Promoção", format="%.2f"),
            "Estoque Atual": st.column_config.NumberColumn("Estoque"),
            "Status": st.column_config.CheckboxColumn("Ativo")
        },
        hide_index=True, width='stretch', key=c_key
    )
    if c_key in st.session_state and (st.session_state[c_key].get("edited_rows")):
        if st.button("💾 Salvar Alterações"):
            df_res.to_csv(FILE_PRODUTOS, index=False, sep=SEPARADOR)
            st.session_state.editor_key_seed += 1; st.rerun()

# --- ABA 3: RELATÓRIOS ---
with aba_relatorio:
    st.subheader("Análise de Resultados")
    
    with st.expander("💾 Exportar Backup de Dados"):
        dados_zip = preparar_download_dados()
        st.download_button("📥 Baixar CSVs (.zip)", data=dados_zip, file_name=f"backup_frui_{datetime.now().strftime('%Y%m%d')}.zip", mime="application/zip", width='stretch')
    
    if os.path.exists(FILE_VENDAS):
        df_v = pd.read_csv(FILE_VENDAS, sep=SEPARADOR, dtype={'Cod.Produto': str, 'Cod.Cliente': str})
        if not df_v.empty:
            # --- NORMALIZAÇÃO EM TEMPO DE EXECUÇÃO (JOIN) ---
            # Trazemos o Nome do Cliente
            df_v = df_v.merge(df_c[['Codigo', 'Nome']], left_on='Cod.Cliente', right_on='Codigo', how='left').rename(columns={'Nome': 'Cliente_Nome'}).drop(columns=['Codigo'])
            # Trazemos o Nome do Produto
            df_v = df_v.merge(df_p[['Codigo', 'Nome']], left_on='Cod.Produto', right_on='Codigo', how='left').rename(columns={'Nome': 'Prod_Nome'}).drop(columns=['Codigo'])
            
            total_geral = df_v['Total'].sum()
            total_vendas = df_v['Cod.Venda'].nunique()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Faturamento", formatar_br(total_geral))
            k2.metric("Vendas", total_vendas)
            k3.metric("Ticket Médio", formatar_br(total_geral/total_vendas))
            
            st.divider()
            
            st.markdown("##### Histórico de Pedidos")
            resumo_vendas = df_v.groupby(['Cod.Venda', 'Data', 'Cliente_Nome', 'Tema'])['Total'].sum().reset_index()
            resumo_vendas = resumo_vendas.sort_values('Cod.Venda', ascending=False)
            
            for _, row in resumo_vendas.iterrows():
                tema_str = f" | {row['Tema']}" if pd.notna(row['Tema']) and row['Tema'] != "" else ""
                with st.expander(f"📦 {row['Cod.Venda']} | {row['Cliente_Nome']}{tema_str} | {formatar_br(row['Total'])}"):
                    detalhe = df_v[df_v['Cod.Venda'] == row['Cod.Venda']][['Prod_Nome', 'Qtd', 'Total', 'Observacoes']].copy()
                    detalhe['Total'] = detalhe['Total'].apply(formatar_br)
                    st.table(detalhe)
                    st.caption(f"Data: {row['Data']}")
        else: st.info("Sem vendas.")
    else: st.info("Arquivo não encontrado.")