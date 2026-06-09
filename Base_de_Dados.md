# Base de Dados — Frui Partis

Banco **PostgreSQL** hospedado no **Supabase**, acessado via `psycopg2` (escrita) e `SQLAlchemy + pandas` (leitura). Todas as tabelas ficam no schema `public`.

---

## Convenções de Tipagem

| Categoria | Tipo PostgreSQL | Aplicação |
|---|---|---|
| Chaves primárias e FKs | `integer` | `Cod_*`, `id`, `venda_id`, `criado_por`, `alterado_por` |
| Flags booleanas | `integer` (0/1) | `ativo`, `admin`, `Status` |
| Valores monetários (R$) | `numeric(10,2)` | Preços, totais, custos, pagamentos |
| Percentuais | `numeric(5,2)` | Desconto |
| Quantidades inteiras | `integer` | Estoques, quantidades de itens |
| Textos livres e datas | `text` | Nomes, observações, datas em formato `dd/mm/aaaa hh:mm:ss` |
| Datas estruturadas | `date` | `data_pagamento`, `data_cobranca` |
| Timestamps de auditoria | `timestamp` | `criado_em` em tabelas de transação |

> **Por que `numeric` para dinheiro?** O tipo `real` (float4) é ponto flutuante binário e armazena `19.90` como `19.899999618...`. O `numeric` tem precisão exata e é o padrão correto para valores financeiros.

---

## Tabelas

### `usuarios`
Controla o acesso ao sistema. Cada registro representa um usuário com e-mail e senha (hash bcrypt). O fluxo de ativação e redefinição de senha usa tokens UUID com validade de 24 horas armazenados aqui.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | `integer` PK | Identificador do usuário |
| `nome` | `text` | Nome completo |
| `cpf` | `text` | CPF (somente dígitos) |
| `email` | `text` UNIQUE | Login do usuário |
| `senha_hash` | `text` | Senha protegida com bcrypt |
| `ativo` | `integer` | `1` = ativo, `0` = aguardando ativação |
| `admin` | `integer` | `1` = perfil administrador |
| `criado_em` | `text` | Data/hora do cadastro (`dd/mm/aaaa hh:mm:ss`) |
| `token_ativacao` | `text` | Token UUID para ativação por e-mail (nullable) |
| `token_expira` | `text` | Expiração do token de ativação (nullable) |
| `token_senha` | `text` | Token UUID para redefinição de senha (nullable) |
| `token_senha_expira` | `text` | Expiração do token de redefinição (nullable) |

---

### `clientes`
Cadastro de clientes Pessoa Física (PF) e Pessoa Jurídica (PJ). Usado na seleção de cliente ao registrar uma venda e na exibição do histórico de vendas e inadimplência.

| Coluna | Tipo | Descrição |
|---|---|---|
| `Cod_Cliente` | `integer` PK | Identificador do cliente |
| `Nome` | `text` | Nome completo ou razão social |
| `Tipo_Pessoa` | `text` | `PF` ou `PJ` |
| `Sexo` | `text` | `M`, `F`, `O` ou `NA` |
| `Email` | `text` | E-mail de contato |
| `Telefone` | `text` | Telefone de contato |
| `CPF_CNPJ` | `text` | Documento fiscal |
| `RG/IE` | `text` | RG (PF) ou Inscrição Estadual (PJ) |
| `Data_Nasc` | `text` | Data de nascimento |
| `Debito_Credito` | `text` | Saldo histórico do sistema anterior |
| `Observacoes` | `text` | Observações gerais |
| `Endereco` | `text` | Logradouro |
| `Numero` | `text` | Número do endereço |
| `Complemento` | `text` | Complemento do endereço |
| `Bairro` | `text` | Bairro |
| `Cidade` | `text` | Cidade |
| `Estado` | `text` | Estado (UF) |
| `CEP` | `text` | CEP |
| `Pai` | `text` | Nome do pai (legado) |
| `Mae` | `text` | Nome da mãe (legado) |
| `criado_por` | `integer` FK → `usuarios.id` | Usuário que criou o registro |
| `criado_em` | `text` | Data/hora de criação |
| `alterado_por` | `integer` FK → `usuarios.id` | Usuário da última edição |
| `alterado_em` | `text` | Data/hora da última edição |

---

### `produtos`
Catálogo de produtos com controle de estoque. Produtos inativos (`Status = 0`) são ocultados na tela de venda mas preservados no histórico.

| Coluna | Tipo | Descrição |
|---|---|---|
| `Cod_Produto` | `integer` PK | Identificador do produto |
| `Nome` | `text` | Nome do produto |
| `Preco` | `numeric(10,2)` | Preço de venda padrão |
| `custo` | `numeric(10,2)` | Custo unitário (usado no cálculo de margem) |
| `Estoque Atual` | `integer` | Quantidade em estoque |
| `Estoque Min.` | `integer` | Estoque mínimo desejado |
| `Estoque Max.` | `integer` | Estoque máximo desejado |
| `Status` | `integer` | `1` = ativo, `0` = inativo |
| `Observacoes` | `text` | Observações sobre o produto |
| `Categoria` | `text` | Categoria do produto |
| `Unidade` | `text` | Unidade de medida |
| `Marca` | `text` | Marca do produto |
| `Codigo Extra` | `text` | Código auxiliar (legado) |
| `Preco Promocional` | `numeric(10,2)` | Preço promocional (quando ativo, sobrepõe o preço padrão na venda) |
| `Data Inicial` | `text` | Início da promoção |
| `Data Final` | `text` | Fim da promoção |
| `Kit / Combo` | `text` | Indicador de kit ou combo |
| `criado_por` | `integer` FK → `usuarios.id` | Usuário que criou o registro |
| `criado_em` | `text` | Data/hora de criação |
| `alterado_por` | `integer` FK → `usuarios.id` | Usuário da última edição |
| `alterado_em` | `text` | Data/hora da última edição |

---

### `vendas`
Cabeçalho de cada venda. Um registro por venda, referenciando o cliente e armazenando o total calculado. Os itens ficam em `vendas_itens` e os pagamentos em `vendas_pagamentos`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `Cod_Venda` | `integer` PK | Identificador da venda |
| `Data` | `text` | Data e hora da venda (`dd/mm/aaaa hh:mm:ss`) |
| `Cod_Cliente` | `integer` FK → `clientes.Cod_Cliente` | Cliente da venda |
| `Tema` | `text` | Tema ou descrição livre da venda |
| `Total` | `numeric(10,2)` | Valor total da venda (soma dos itens com desconto) |
| `criado_por` | `integer` FK → `usuarios.id` | Usuário que registrou a venda |
| `criado_em` | `text` | Data/hora de criação |
| `alterado_por` | `integer` FK → `usuarios.id` | Usuário da última edição |
| `alterado_em` | `text` | Data/hora da última edição |

---

### `vendas_itens`
Itens de cada venda. Cada linha representa um produto adicionado ao carrinho, com quantidade, valor unitário praticado e desconto aplicado. A baixa de estoque é feita no momento da confirmação da venda.

| Coluna | Tipo | Descrição |
|---|---|---|
| `Cod_Item` | `integer` PK | Identificador do item |
| `Cod_Venda` | `integer` FK → `vendas.Cod_Venda` | Venda à qual o item pertence |
| `Cod_Produto` | `integer` FK → `produtos.Cod_Produto` | Produto vendido |
| `Qtd` | `integer` | Quantidade vendida |
| `Vlr_Unitario` | `numeric(10,2)` | Preço unitário praticado no momento da venda |
| `Desconto` | `numeric(5,2)` | Percentual de desconto aplicado (0 a 100) |
| `Total_Item` | `numeric(10,2)` | Total do item após desconto |
| `Observacoes` | `text` | Observações específicas do item |
| `criado_por` | `integer` FK → `usuarios.id` | Usuário que registrou o item |
| `criado_em` | `text` | Data/hora de criação |
| `alterado_por` | `integer` FK → `usuarios.id` | Usuário da última edição |
| `alterado_em` | `text` | Data/hora da última edição |

---

### `vendas_pagamentos`
Histórico de pagamentos por venda. Uma venda pode ter múltiplos registros aqui (pagamento parcial no ato + complementos posteriores). O saldo em aberto é sempre calculado dinamicamente como `vendas.Total - SUM(vendas_pagamentos.valor)`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | `integer` PK | Identificador do pagamento |
| `venda_id` | `integer` FK → `vendas.Cod_Venda` | Venda referenciada |
| `valor` | `numeric(10,2)` | Valor pago neste registro |
| `data_pagamento` | `date` | Data do pagamento |
| `observacao` | `text` | Observação (ex: "Pagamento no ato da venda") |
| `criado_por` | `integer` FK → `usuarios.id` | Usuário que registrou o pagamento |
| `criado_em` | `timestamp` | Data/hora de criação (automático) |

---

### `vendas_cobrancas`
Histórico de avisos de cobrança por venda. Cada registro representa um contato de cobrança realizado para uma venda em aberto. Usado exclusivamente na sub-aba Inadimplência.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | `integer` PK | Identificador do aviso |
| `venda_id` | `integer` FK → `vendas.Cod_Venda` | Venda referenciada |
| `data_cobranca` | `date` | Data em que o contato foi realizado |
| `observacao` | `text` | Descrição do contato (obrigatória) |
| `criado_por` | `integer` FK → `usuarios.id` | Usuário que registrou o aviso |
| `criado_em` | `timestamp` | Data/hora de criação (automático) |
