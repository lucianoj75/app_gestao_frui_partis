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

def preparar_download_dados():
    """Lê os arquivos do servidor e cria um arquivo ZIP na memória."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "x") as csv_zip:
        for file in [FILE_PRODUTOS, FILE_CLIENTES, FILE_VENDAS]:
            if os.path.exists(file):
                csv_zip.write(file, arcname=os.path.basename(file))
    return buf.getvalue()

def carregar_dados():
    df_p = pd.read_csv(FILE_PRODUTOS, sep=SEPARADOR, dtype={'Codigo': str, 'Status': bool})
    # Garantimos que as colunas sejam numéricas (float)
    df_p['Preço'] = pd.to_numeric(df_p['Preço'], errors='coerce').fillna(0.0)
    df_p['Preço Promocional'] = pd.to_numeric(df_p['Preço Promocional'], errors='coerce').fillna(0.0)
    
    df_c = pd.read_csv(FILE_CLIENTES, sep=SEPARADOR, dtype={'Codigo': str})
    return df_p, df_c

def formatar_br(valor):
    """Formatação padrão para Tabelas e DataFrames."""
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_markdown_br(valor):
    """Formatação com escape \$ para evitar conflito com LaTeX no st.markdown."""
    return f"R\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_proximo_cod_venda():
    if not os.path.exists(FILE_VENDAS): return 1
    try:
        df_v = pd.read_csv(FILE_VENDAS, sep=SEPARADOR)
        return int(df_v['Cod.Venda'].max()) + 1 if not df_v.empty else 1
    except: return 1

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
    df_p_ativos = df_p[df_p['Status'] == True].copy()
    nome_cli = st.selectbox("Selecione o Cliente", df_c['Nome'].unique(), key="venda_cliente")
    st.divider()
    
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            nome_p = st.selectbox("Escolha o Produto", df_p_ativos['Nome'].unique(), key="add_p")
            dados_p = df_p_ativos[df_p_ativos['Nome'] == nome_p].iloc[0]
            
            cod_p = dados_p['Codigo']
            estoque_p = float(dados_p['Estoque Atual'])
            p_base = float(dados_p['Preço'])
            p_promo = float(dados_p['Preço Promocional'])

            qtd_car = sum(item['Qtd'] for item in st.session_state.carrinho if item['Cod.Produto'] == cod_p)
            disp = estoque_p - qtd_car
            
            info_txt = f"**Cód:** {cod_p} | **Preço:** {formatar_markdown_br(p_base)} | **Estoque:** {int(disp)}"
            
            # Condição: Só exibe promoção se for maior que zero
            if p_promo > 0:
                info_txt += f" | 🔥 **PROMOÇÃO: {formatar_markdown_br(p_promo)}**"
                
            st.markdown(info_txt)

        with c2:
            max_v = int(disp) if disp > 0 else 1
            qtd_v = st.number_input("Qtd", min_value=1, max_value=max_v, step=1, key=f"q_{st.session_state.reset_key}")

        obs = st.text_area("Observações", height=70, key=f"o_{st.session_state.reset_key}")
        
        if st.button("➕ Adicionar ao Carrinho", width='stretch'):
            if disp >= qtd_v:
                preco_final = p_promo if p_promo > 0 else p_base
                st.session_state.carrinho.append({
                    'Cod.Produto': cod_p, 'Produto': nome_p, 'Qtd': qtd_v,
                    'Preço Un.': preco_final, 'Total': qtd_v * preco_final, 'Observacoes': obs
                })
                st.session_state.reset_key += 1
                st.rerun()

    if st.session_state.carrinho:
        df_cart = pd.DataFrame(st.session_state.carrinho).copy()
        df_cart['Preço Un.'] = df_cart['Preço Un.'].apply(formatar_br)
        df_cart['Total'] = df_cart['Total'].apply(formatar_br)
        st.table(df_cart)
        
        total_v = sum(item['Total'] for item in st.session_state.carrinho)
        st.markdown(f"### Total do Pedido: {formatar_markdown_br(total_v)}")
        
        b1, b2 = st.columns(2)
        with b1:
            if st.button("🗑️ Limpar Carrinho", width='stretch'):
                st.session_state.carrinho = []; st.rerun()
        with b2:
            if st.button("✅ Finalizar Venda", type="primary", width='stretch'):
                cod_v = gerar_proximo_cod_venda()
                dt_v = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                novas = []
                for item in st.session_state.carrinho:
                    idx = df_p[df_p['Codigo'] == item['Cod.Produto']].index[0]
                    df_p.at[idx, 'Estoque Atual'] -= item['Qtd']
                    novas.append({
                        'Cod.Venda': cod_v, 'Data': dt_v, 'Cliente': nome_cli,
                        'Cod.Produto': item['Cod.Produto'], 'Produto_Nome': item['Produto'],
                        'Qtd': item['Qtd'], 'Total': item['Total'], 'Observacoes': item['Observacoes']
                    })
                df_p.to_csv(FILE_PRODUTOS, index=False, sep=SEPARADOR)
                pd.concat([pd.read_csv(FILE_VENDAS, sep=SEPARADOR, dtype={'Cod.Produto': str}) if os.path.exists(FILE_VENDAS) else pd.DataFrame(), pd.DataFrame(novas)], ignore_index=True).to_csv(FILE_VENDAS, index=False, sep=SEPARADOR)
                st.session_state.carrinho = []; st.success(f"Venda {cod_v} salva!"); st.rerun()

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
    if c_key in st.session_state and (st.session_state[c_key].get("edited_rows") or st.session_state[c_key].get("added_rows")):
        if st.button("💾 Salvar Alterações", type="primary", width='stretch'):
            df_res.to_csv(FILE_PRODUTOS, index=False, sep=SEPARADOR)
            st.session_state.editor_key_seed += 1; st.rerun()

# --- ABA 3: RELATÓRIOS ---
with aba_relatorio:
    st.subheader("Análise de Resultados")
    
    # --- NOVO: SEÇÃO DE BACKUP ---
    with st.expander("💾 Exportar Backup de Dados"):
        st.write("Baixe uma cópia dos arquivos CSV atuais do servidor.")
        dados_zip = preparar_download_dados()
        st.download_button(
            label="📥 Baixar todos os CSVs (.zip)",
            data=dados_zip,
            file_name=f"backup_frui_partis_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip",
            width='stretch'
        )
    st.divider()
    
    if os.path.exists(FILE_VENDAS):
        df_v = pd.read_csv(FILE_VENDAS, sep=SEPARADOR, dtype={'Cod.Produto': str})
        
        if not df_v.empty:
            total_geral = df_v['Total'].sum()
            total_vendas = df_v['Cod.Venda'].nunique()
            ticket_medio = total_geral / total_vendas if total_vendas > 0 else 0
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Faturamento Total", formatar_br(total_geral))
            k2.metric("Qtd. de Vendas", total_vendas)
            k3.metric("Ticket Médio", formatar_br(ticket_medio))
            
            st.divider()
            
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown("##### Faturamento por Cliente")
                fat_cli = df_v.groupby('Cliente')['Total'].sum().reset_index()
                fig_cli = px.bar(fat_cli, x='Cliente', y='Total', color='Total', 
                                 labels={'Total':'Total (R$)'}, color_continuous_scale='Blues')
                # ATUALIZADO: use_container_width=True -> width='stretch'
                st.plotly_chart(fig_cli, width='stretch')
                
            with col_g2:
                st.markdown("##### Top 5 Produtos (Volume)")
                vol_prod = df_v.groupby('Produto_Nome')['Qtd'].sum().reset_index().sort_values('Qtd', ascending=False).head(5)
                fig_prod = px.pie(vol_prod, values='Qtd', names='Produto_Nome', hole=0.4)
                # ATUALIZADO: use_container_width=True -> width='stretch'
                st.plotly_chart(fig_prod, width='stretch')

            st.divider()
            
            st.markdown("##### Histórico de Pedidos")
            resumo_vendas = df_v.groupby(['Cod.Venda', 'Data', 'Cliente'])['Total'].sum().reset_index()
            resumo_vendas = resumo_vendas.sort_values('Cod.Venda', ascending=False)
            
            for _, row in resumo_vendas.iterrows():
                with st.expander(f"📦 Venda {row['Cod.Venda']} | {row['Data']} | {row['Cliente']} | {formatar_br(row['Total'])}"):
                    detalhe = df_v[df_v['Cod.Venda'] == row['Cod.Venda']][['Produto_Nome', 'Qtd', 'Total', 'Observacoes']].copy()
                    detalhe['Total'] = detalhe['Total'].apply(formatar_br)
                    st.table(detalhe)
        else:
            st.info("O arquivo de vendas está vazio.")
    else:
        st.info("Nenhuma venda realizada ainda.")