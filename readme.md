---
status: ![Status](https://img.shields.io/badge/Status-Operacional-brightgreen)
version: 2.0.0
last_updated: 2026-06-01
---

# 🍎 Sistema de Gestão Frui Partis

Aplicação web desenvolvida em **Python** com o framework **Streamlit** para gerenciar o fluxo completo de uma operação comercial: cadastro de produtos e clientes, fechamento de vendas com controle de estoque automatizado, relatórios e controle de acesso por usuários.

---

## 🚀 Funcionalidades

O sistema é dividido em quatro módulos principais acessíveis via abas, protegidos por autenticação:

### 1. 🛒 Registrar Venda
- Seleção de cliente e tema da venda
- Carrinho de compras com múltiplos itens e validação de estoque em tempo real
- Suporte a descontos percentuais por item e cálculo de total líquido
- Baixa automática de estoque ao finalizar a venda
- Bloqueio de alteração de cliente enquanto houver itens no carrinho, garantindo integridade da transação

### 2. 📋 Gestão de Produtos
- Cadastro rápido de novos produtos (nome, preço, estoque inicial)
- Edição direta na tabela para alteração de preços, nomes e status
- Ativação e inativação de produtos sem excluí-los do histórico

### 3. 👥 Gestão de Clientes
- Cadastro com diferenciação entre Pessoa Física (PF) e Pessoa Jurídica (PJ)
- Armazenamento de e-mail, telefone e informações demográficas
- Edição direta dos dados cadastrais

### 4. 📈 Relatórios
- Histórico detalhado de vendas com filtros por cliente, período e pendências
- Faturamento mensal com ticket médio
- Ranking dos 10 produtos mais vendidos
- Exportação do banco de dados em `.zip` para backup

---

## 🔐 Autenticação e Controle de Acesso

O sistema possui um fluxo completo de autenticação:

- **Login** por e-mail e senha. Senhas armazenadas como hash `bcrypt` — nunca em texto puro.
- **Cadastro de novo usuário** com validação de campos (senha entre 6 e 10 caracteres, ao menos uma letra maiúscula e um número). Novos cadastros ficam **inativos** até confirmação por e-mail.
- **Ativação por e-mail** — um link único com validade de 24 horas é enviado ao usuário. Ao clicar, o cadastro é ativado automaticamente.
- **Esqueci minha senha** — o usuário informa o e-mail cadastrado e recebe um link para redefinir a senha, também com validade de 24 horas.
- **Perfil admin** — campo booleano na tabela de usuários que permitirá no futuro funcionalidades exclusivas para administradores.
- **Auditoria** — todos os registros do sistema armazenam o ID do usuário que criou ou alterou cada dado, junto com o timestamp da operação.

---

## 🗄️ Estrutura do Banco de Dados

O banco de dados é SQLite (`frui_partis.db`) com cinco tabelas:

| Tabela | Descrição |
|---|---|
| `usuarios` | Controle de acesso: e-mail, senha (hash), status ativo/inativo, perfil admin, tokens de ativação e redefinição de senha |
| `clientes` | Cadastro de clientes PF e PJ |
| `produtos` | Cadastro de produtos com controle de estoque e status |
| `vendas` | Cabeçalho de cada venda (cliente, data, tema, total, valor pago) |
| `vendas_itens` | Itens de cada venda (produto, quantidade, valor unitário, desconto) |

Todas as tabelas possuem campos de auditoria: `criado_por`, `criado_em`, `alterado_por` e `alterado_em`.

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| Python | Linguagem principal |
| Streamlit | Interface web |
| SQLite | Banco de dados local |
| Pandas | Manipulação de dados e tabelas |
| bcrypt | Hash seguro de senhas |
| smtplib | Envio de e-mails via Gmail SMTP |
| uuid | Geração de tokens únicos |

---

## ⚙️ Configuração de Credenciais

As credenciais **não ficam no código**. São lidas via `st.secrets`, que funciona de duas formas:

**Localmente** — crie o arquivo `.streamlit/secrets.toml` na raiz do projeto:
```toml
SMTP_USER    = "seu_email@gmail.com"
SMTP_PASS    = "sua_senha_de_app_gmail"
APP_BASE_URL = "http://localhost:8501"
```

**Streamlit Cloud** — acesse **Settings → Secrets** no painel do seu app e cadastre as mesmas variáveis.

> O arquivo `secrets.toml.example` na raiz do projeto serve como modelo. O `secrets.toml` real nunca deve ser enviado ao GitHub.

---

## ▶️ Como Executar Localmente

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

## 🐙 Controle de Versão com Git e GitHub

Esta seção descreve como manter o repositório atualizado a partir do computador local usando o **VS Code** e o **Git**.

### Pré-requisitos
- Git instalado: [git-scm.com/download/win](https://git-scm.com/download/win)
- VS Code com o repositório aberto na pasta do projeto

### Primeiro acesso — conectar a pasta local ao GitHub
Abra o terminal do VS Code (**Ctrl + '**) e rode:
```bash
git remote add origin https://github.com/lucianoj75/app_gestao_frui_partis.git
git pull origin main
```
Na autenticação, use seu **usuário do GitHub** e o **Personal Access Token** como senha.

### Enviar atualizações (dia a dia)
No VS Code, pelo painel **Source Control** (ícone de ramificação na barra lateral):
1. Os arquivos modificados aparecem listados automaticamente
2. Escreva uma mensagem descrevendo o que mudou no campo **Message**
3. Clique em **Commit & Push**

Ou pelo terminal:
```bash
git add .
git commit -m "descrição do que foi alterado"
git push origin main
```

### Gerar um novo Personal Access Token
Caso o token expire, gere um novo em:
[github.com/settings/tokens](https://github.com/settings/tokens)
- Tipo: **Classic**
- Escopo: marque apenas **`repo`**
- Validade sugerida: 90 dias

### O que nunca deve ir ao GitHub
O arquivo `.gitignore` já está configurado para proteger:
```
.streamlit/secrets.toml   ← credenciais SMTP
*.db                      ← banco de dados com dados dos clientes
apoio/                    ← pasta de apoio local
backup_app/               ← pasta de backups locais
```

---

## 📋 Requisitos

```
streamlit
pandas
bcrypt
```
