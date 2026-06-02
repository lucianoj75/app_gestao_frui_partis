---
status: ![Status](https://img.shields.io/badge/Status-Operacional-brightgreen)
version: 1.1.0
last_updated: 2026-05-12
---

# 🍎 Sistema de Gestão Frui Partis

Este sistema é uma aplicação robusta desenvolvida em **Python** utilizando o framework **Streamlit**. Ele foi projetado para gerenciar o fluxo completo de uma operação comercial: desde o cadastro de produtos e clientes até o fechamento de vendas com controle de estoque automatizado.

## 🛠️ Arquitetura Técnica

- **Frontend/Interface:** Streamlit.
- **Interface Limpa:** O uso de `st.dialog` (janelas pop-up) para novos cadastros mantém a experiência do usuário fluida, evitando recarregamentos desnecessários da página principal.
- **Banco de Dados:** SQLite (Arquivo local: `Dados/frui_partis.db`).
- **Persistência de Dados:** Uso de `st.session_state` para gestão de carrinho e estados de formulários.
- **Cache:** Implementação de `@st.cache_data` para otimização de leitura do banco de dados.

---

## 🚀 Funcionalidades Principais

O sistema é dividido em quatro módulos principais acessíveis via abas:

### 1. 🛒 Registrar Venda
O coração do sistema. Permite a montagem de um pedido dinâmico.
- **Segurança de Processos:** O sistema bloqueia a alteração do cliente ou do "tema" da venda enquanto houver itens no carrinho, garantindo a integridade total dos dados da transação em curso.
- **Seleção de Cliente:** Busca automática na base de clientes cadastrados.
- **Carrinho de Compras:** Adição de múltiplos itens com validação de estoque em tempo real.
- **Cálculos Automáticos:** Suporte a descontos percentuais por item e cálculo de Total Líquido.
- **Baixa de Estoque:** Ao finalizar a venda, o sistema subtrai automaticamente as quantidades do banco de dados.

### 2. 📋 Gestão de Produtos
Módulo para controle de inventário.
- **Cadastro Rápido:** Interface adaptativa para inclusão de novos produtos com nome, preço e estoque inicial.
- **Edição em Grade:** Edição direta na tabela (Data Editor) para alterar preços, nomes ou status de ativação.
- **Status Ativo/Inativo:** Permite desativar produtos sem excluí-los do histórico.

### 3. 👥 Gestão de Clientes
Base de dados de contatos.
- **Segmentação:** Diferenciação entre Pessoa Física (PF) e Pessoa Jurídica (PJ).
- **Dados de Contato:** Armazenamento de e-mail, telefone e informações demográficas (sexo).
- **Edição Direta:** Interface amigável para atualização de dados cadastrais.

### 4. 📈 Relatórios e Backup
Módulo de inteligência e segurança.
- **Tratamento de Dados Local:** Implementação de funções de formatação de moeda brasileira (`R$ 0,00`), tornando os relatórios profissionais e adequados ao mercado local.
- **Faturamento:** Visualização do faturamento total acumulado.
- **Histórico Detalhado:** Lista de vendas agrupadas por ID, com "expanders" que revelam os itens específicos de cada transação.
- **Segurança de Dados:** Botão de exportação que gera um arquivo `.zip` contendo o banco de dados SQLite para backup.

---

## 📊 Estrutura de Dados (DB)

O sistema opera com três tabelas fundamentais:
1.  **`produtos`**: `Cod_Produto`, `Nome`, `Preco`, `Estoque Atual`, `Observacoes`, `Status`.
2.  **`clientes`**: `Cod_Cliente`, `Nome`, `Tipo_Pessoa`, `Sexo`, `Email`, `Telefone`.
3.  **`vendas`**: `Cod.Venda`, `Data`, `Cod_Cliente`, `Tema`, `Cod_Produto`, `Qtd`, `Vlr_Unitario_Produto`, `Desconto_Item`, `Total`.

---

## 📋 Requisitos para Execução

Para rodar o sistema localmente, certifique-se de ter instalado:
```bash
pip install streamlit pandas
```
E execute:
```bash
streamlit run app.py
```
