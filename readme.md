---
status: ![Status](https://img.shields.io/badge/Status-Operacional-brightgreen)
version: 2.4.0
last_updated: 2026-06-07
---

# Sistema de Gestão Frui Partis

Aplicação web desenvolvida em **Python** com o framework **Streamlit** para gerenciar o fluxo completo de uma operação comercial: cadastro de produtos e clientes, registro de vendas com controle de estoque, relatórios de faturamento e controle de acesso por usuários. O banco de dados é hospedado na nuvem via **Supabase (PostgreSQL)**.

---

## Funcionalidades

O sistema é organizado em quatro abas principais, acessíveis somente após autenticação.

### Registrar Venda
- Seleção de cliente e tema da venda
- Carrinho de compras com múltiplos itens
- Validação de estoque em tempo real com confirmação opcional para produtos sem estoque
- Valor de venda editável por item e suporte a desconto percentual
- Campo de observações por item
- Bloqueio de alteração de cliente enquanto houver itens no carrinho
- Popup de pagamento: registro do valor pago com INSERT em `vendas_pagamentos` e cálculo automático do saldo pendente
- Baixa automática de estoque ao confirmar a venda

### Gestão de Produtos
- Cadastro de novos produtos (nome, preço, estoque inicial, observações)
- Edição direta na tabela: preço, custo, nome, estoque, observações e status ativo/inativo
- Campo **Custo (R$)** editável — permite calcular margem de lucro no relatório Top 10 Produtos
- Inativação sem exclusão — produtos inativos não aparecem para venda mas permanecem no histórico
- Aviso visual de alterações não salvas

### Gestão de Clientes
- Cadastro com distinção entre Pessoa Física (PF) e Pessoa Jurídica (PJ)
- Campos: nome, tipo, sexo, e-mail e telefone
- Edição direta dos dados cadastrais na tabela

### Relatórios
Quatro sub-abas independentes:

**Dashboard**
- Filtro de mês no topo (Janeiro até o mês corrente, em pt-BR) com opção "Todos" — controla todos os blocos
- Métricas do período selecionado: faturamento, quantidade de vendas e ticket médio
  - Com mês específico: exibe delta vs mês anterior (verde ↑ / vermelho ↓ / badge âmbar "Sem variação" / sem indicador quando sem vendas)
  - Com "Todos": exibe totais do ano sem delta
- Gráfico de linha interativo (Plotly) com evolução mensal da métrica selecionada (Faturamento, Qtd. Vendas ou Ticket Médio); ponto âmbar destaca o mês selecionado no filtro
- Top 3 produtos mais vendidos no período (mês ou ano inteiro), por quantidade
- Alerta de produtos ativos com estoque zerado

**Vendas**
- Histórico completo com expansão por venda, exibindo itens, valores unitários, desconto e observações
- Filtros por cliente, intervalo de datas (até 31 dias) e pendência de pagamento
- Métrica de faturamento total do período filtrado

**Top 10 Produtos**
- Ranking dos 10 produtos com maior média de unidades vendidas por mês
- Colunas: quantidade média/mês, valor médio/mês, meses com venda, margem % e margem R$
- Margem calculada automaticamente quando o custo do produto está cadastrado

**Inadimplência**
- Métricas de topo: total em aberto, clientes devedores e data da dívida mais antiga
- Tabela de clientes devedores com saldo total e número de vendas em aberto
- Expansão por cliente com detalhamento de cada venda em aberto (total, valor pago, saldo)
- Botão 📣 por venda para registrar aviso de cobrança com data e observação
- Botão 💲 por venda para receber pagamento parcial ou total com data e observação
- Saldos atualizados em tempo real após cada pagamento registrado

---

## Autenticação e Controle de Acesso

### Login
- Autenticação por e-mail e senha
- Senhas armazenadas como hash `bcrypt` — nunca em texto puro
- Usuários inativos não conseguem logar e recebem automaticamente um novo link de ativação por e-mail

### Cadastro de novo usuário
- Campos: nome completo, CPF, e-mail e senha
- Regras de senha: entre 6 e 10 caracteres, ao menos uma letra maiúscula e um número
- Novo cadastro fica **inativo** até confirmação por e-mail
- Se o e-mail já existir e estiver inativo, oferece opção de reenvio do link de ativação

### Ativação por e-mail
- Link único enviado ao e-mail do usuário com validade de 24 horas
- Ao clicar, o cadastro é ativado automaticamente via token na URL (`?token=...`)

### Esqueci minha senha
- Usuário informa o e-mail cadastrado e recebe link de redefinição com validade de 24 horas
- Acesso via token na URL (`?reset_token=...`) com formulário de nova senha

### Perfil admin
- Campo booleano na tabela de usuários, disponível para expansão futura de funcionalidades exclusivas

### Auditoria
- Todos os registros armazenam `criado_por`, `criado_em`, `alterado_por` e `alterado_em`
- Colunas de auditoria são protegidas e não ficam visíveis ou editáveis nas tabelas da interface

---

## Banco de Dados

Banco **PostgreSQL** hospedado no **Supabase**, com sete tabelas:

| Tabela | Descrição |
|---|---|
| `usuarios` | Controle de acesso: e-mail, senha (hash bcrypt), status ativo/inativo, perfil admin, tokens de ativação e redefinição de senha |
| `clientes` | Cadastro de clientes PF e PJ |
| `produtos` | Cadastro de produtos com controle de estoque, status ativo/inativo e custo unitário |
| `vendas` | Cabeçalho de cada venda: cliente, data, tema e total |
| `vendas_itens` | Itens de cada venda: produto, quantidade, valor unitário, desconto, total e observações |
| `vendas_pagamentos` | Histórico de pagamentos por venda: valor, data e observação — inclui o pagamento no ato da venda |
| `vendas_cobranças` | Histórico de avisos de cobrança por venda: data do contato e observação |

Todas as tabelas possuem campos de auditoria: `criado_por`, `criado_em`, `alterado_por` e `alterado_em`.

---

## Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| Python | Linguagem principal |
| Streamlit | Interface web |
| Supabase (PostgreSQL) | Banco de dados em nuvem |
| psycopg2 | Driver de conexão com PostgreSQL |
| SQLAlchemy | Engine para leitura de dados com Pandas |
| Pandas | Manipulação de dados e tabelas |
| NumPy | Conversão de tipos para compatibilidade com PostgreSQL |
| bcrypt | Hash seguro de senhas |
| smtplib | Envio de e-mails via Gmail SMTP |
| uuid | Geração de tokens únicos de ativação e redefinição de senha |

---

## Configuração de Credenciais

As credenciais **não ficam no código**. São lidas via `st.secrets`, que funciona de duas formas:

**Localmente** — crie o arquivo `.streamlit/secrets.toml` na raiz do projeto:
```toml
SMTP_USER    = "seu_email@gmail.com"
SMTP_PASS    = "sua_senha_de_app_gmail"
APP_BASE_URL = "http://localhost:8501"

DB_HOST = "seu_host_supabase"
DB_PORT = "6543"
DB_NAME = "postgres"
DB_USER = "seu_usuario"
DB_PASS = "sua_senha"
```

**Streamlit Cloud** — acesse **Settings → Secrets** no painel do seu app e cadastre as mesmas variáveis.

> O arquivo `secrets.toml.example` na raiz do projeto serve como modelo. O `secrets.toml` real nunca deve ser enviado ao GitHub.

---

## Como Executar Localmente

**1. Instale as dependências:**
```bash
pip install -r requirements.txt
```

**2. Configure o arquivo de credenciais** conforme descrito acima.

**3. Execute a aplicação:**
```bash
streamlit run app.py
```

---

## Testes Unitários

O projeto conta com uma suíte de testes automatizados cobrindo as funções de negócio, validação, formatação e acesso ao banco de dados. Os testes são executados sem depender de banco real, Streamlit ou e-mail.

```bash
pytest tests/ -v
```

Para detalhes completos sobre a estratégia, os arquivos e os casos cobertos, consulte:

📄 [Testes_Unitários.md](Testes_Unitários.md)

---

## Controle de Versão com Git e GitHub

### Repositório
[github.com/lucianoj75/app_gestao_frui_partis](https://github.com/lucianoj75/app_gestao_frui_partis)

### Enviar atualizações (dia a dia)
```bash
git add .
git commit -m "descrição do que foi alterado"
git push origin main
```

> **Dica:** sempre faça um `git pull` antes de começar a trabalhar, para garantir que sua versão local está sincronizada com o GitHub.

### O que nunca deve ir ao GitHub
O arquivo `.gitignore` já está configurado para proteger:
```
.streamlit/secrets.toml   ← credenciais SMTP e Supabase
*.db                      ← banco de dados local (legado)
apoio/                    ← pasta de apoio local
backup_app/               ← pasta de backups locais
```

---

## Requisitos

```
streamlit
pandas
bcrypt
psycopg2-binary
sqlalchemy
numpy
```
