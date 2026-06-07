# Testes Unitários — Frui Partis

Documentação completa da suíte de testes automatizados: estratégia adotada, estrutura de arquivos, como executar e detalhamento de cada caso testado.

---

## Estrutura de arquivos

```
projeto/
├── app.py
└── tests/
    ├── __init__.py              ← arquivo vazio, necessário para o pytest localizar os módulos
    ├── test_funcoes_puras.py    ← testes de funções puras (sem banco, sem Streamlit)
    ├── test_banco_mock.py       ← testes de funções com banco de dados (usando mock)
    ├── test_relatorios.py       ← testes das funções de cálculo de relatórios
    └── test_inadimplencia.py    ← testes das funções da sub-aba Inadimplência (usando mock)
```

---

## Dependências

Antes de rodar os testes, instale as dependências (ative o ambiente virtual antes, se usar um):

```bash
pip install pytest numpy bcrypt pandas
```

O `numpy` e o `pandas` geralmente já estão presentes por serem dependências do projeto.

---

## Como executar

**Todos os testes de uma vez:**
```bash
pytest tests/ -v
```

**Um arquivo específico:**
```bash
pytest tests/test_funcoes_puras.py -v
pytest tests/test_banco_mock.py -v
pytest tests/test_relatorios.py -v
pytest tests/test_inadimplencia.py -v
```

A flag `-v` exibe cada teste individualmente com o resultado. Sem ela, aparece apenas o resumo final.

**Resultado esperado:** todos os testes devem passar (`passed`). Avisos (`warnings`) do Pandas sobre depreciações futuras são normais e não indicam falha.

---

## Estratégia de testes

O código foi dividido em três grupos conforme o tipo de dependência de cada função:

### 1. Funções puras (`test_funcoes_puras.py`)
Funções que recebem uma entrada e retornam uma saída, sem depender de banco de dados, e-mail ou interface Streamlit. São as mais simples de testar e as mais confiáveis — qualquer entrada produz um resultado determinístico.

### 2. Funções com banco de dados (`test_banco_mock.py`)
Funções que dependem de conexão com o PostgreSQL. A conexão é substituída por um objeto simulado (`MagicMock` do `unittest.mock`), garantindo que **nenhum banco real seja acessado** durante os testes. Os mocks verificam se as queries corretas foram chamadas, se o `commit` foi executado e se a conexão foi fechada.

### 3. Funções de cálculo de relatórios (`test_relatorios.py`)
Funções extraídas das abas de relatórios do Streamlit e isoladas como funções puras que recebem DataFrames e retornam DataFrames calculados. Testadas com dados sintéticos simples, cobrindo casos normais, bordas e entradas vazias.

### 4. Funções de inadimplência (`test_inadimplencia.py`)
Funções da sub-aba Inadimplência que dependem de conexão com o banco. Seguem o mesmo padrão de `test_banco_mock.py`: as funções são replicadas no arquivo de teste com `get_conn` como parâmetro explícito, e a conexão é substituída por `MagicMock`. Cobrem consultas de devedores, consultas de vendas em aberto, registro de avisos de cobrança e recebimento de pagamentos.

### O que não é testado automaticamente
Telas, abas, dialogs e qualquer elemento que dependa de `st.*` (Streamlit) têm custo alto para automatizar e retorno baixo. Esses são cobertos por testes manuais na aplicação.

---

## Detalhamento dos testes

### `test_funcoes_puras.py` — 53 testes

Cobre as funções puras extraídas do `app.py`. Nenhuma conexão com banco ou serviço externo é necessária.

#### `formatar_br(valor)` — 10 casos
Formata um número como moeda brasileira com escape de `$` para uso em `st.markdown` e `st.table` (ex: `R\$ 1.234,56`).

| Caso | Descrição |
|---|---|
| Valor inteiro | `1000` → `R\$ 1.000,00` |
| Valor float | `1234.56` → `R\$ 1.234,56` |
| Valor zero | `0` → `R\$ 0,00` |
| Valor negativo | `-50.5` → `R\$ -50,50` |
| String numérica | `"250.99"` → `R\$ 250,99` |
| Valor grande | `1000000` → `R\$ 1.000.000,00` |
| String inválida | `"abc"` → retorna `"abc"` sem exceção |
| None | Retorna `None` sem exceção |
| Arredondamento | `9.999` → `R\$ 10,00` |
| Centavos | `0.05` → `R\$ 0,05` |

#### `formatar_df(valor)` — 8 casos
Formata um número como moeda brasileira em texto puro para uso em `st.dataframe` (ex: `R$ 1.234,56`), sem escape de `$`.

| Caso | Descrição |
|---|---|
| Sem barra no prefixo | Resultado começa com `R$ ` e não contém `\` |
| Valor inteiro | `1000` → `R$ 1.000,00` |
| Valor float | `1234.56` → `R$ 1.234,56` |
| Valor zero | `0` → `R$ 0,00` |
| Valor negativo | `-50.5` → `R$ -50,50` |
| String inválida | `"abc"` → retorna `"abc"` sem exceção |
| None | Retorna `None` sem exceção |
| Diferente de `formatar_br` | `formatar_df` não tem `\`; `formatar_br` tem |

#### `formatar_markdown_br(valor)` — 5 casos
Variante com duplo escape (`R\\$ `) para contextos de markdown aninhado.

| Caso | Descrição |
|---|---|
| Prefixo com dupla barra | Resultado começa com `R\\\\$` |
| Valor inteiro | `1000` → `R\\$ 1.000,00` |
| Valor zero | `0` → `R\\$ 0,00` |
| String inválida | Retorna o valor original sem exceção |
| Mais barras que `formatar_br` | Confirma a diferença de escaping entre as funções |

#### `validar_senha(senha)` — 10 casos
Valida regras de senha: 6 a 10 caracteres, ao menos uma maiúscula e um número. Retorna `None` se válida ou a mensagem de erro correspondente.

| Caso | Resultado esperado |
|---|---|
| Senha válida (mínimo) | `None` |
| Senha válida (máximo) | `None` |
| Muito curta (< 6) | Mensagem de tamanho |
| Muito longa (> 10) | Mensagem de tamanho |
| Sem maiúscula | Mensagem de maiúscula |
| Sem número | Mensagem de número |
| Só números | Mensagem de maiúscula (verificado primeiro) |
| Limite mínimo exato (6) | `None` |
| Limite máximo exato (10) | `None` |
| Vazia | Mensagem de tamanho |

#### `validar_cpf_formato(cpf)` — 6 casos
Remove todos os caracteres não numéricos de uma string de CPF.

| Caso | Resultado esperado |
|---|---|
| CPF formatado (`123.456.789-09`) | `"12345678909"` |
| Só dígitos | Retorna inalterado |
| Vazio | `""` |
| Com espaços | Remove espaços |
| Com letras | Remove letras |
| Só pontuação | `""` |

#### `converter(v)` — 9 casos
Converte tipos NumPy para tipos nativos Python compatíveis com o driver PostgreSQL (psycopg2).

| Caso | Resultado esperado |
|---|---|
| `np.int64` | `int` nativo |
| `np.float64` | `float` nativo |
| `np.bool_(True)` | `True` (tipo `bool`) |
| `np.bool_(False)` | `False` (tipo `bool`) |
| `float("nan")` | `None` |
| `np.nan` | `None` |
| String | Passa inalterada |
| `int` nativo | Passa inalterado |
| `None` | Passa inalterado |

---

### `test_banco_mock.py` — 25 testes

Cobre as funções que dependem do banco de dados. A conexão com o PostgreSQL é substituída por `MagicMock`, sem acessar banco real.

#### `verificar_login(email, senha)` — 6 casos
Autentica o usuário consultando a tabela `usuarios` e verificando o hash da senha com `bcrypt`.

| Caso | Resultado esperado |
|---|---|
| E-mail não cadastrado | Retorna `None, "E-mail não cadastrado.", None` |
| Senha incorreta | Retorna `None, "Senha incorreta.", None` |
| Usuário inativo | Retorna `None, "inativo", {dados do usuário}` |
| Login válido (comum) | Retorna dict com `id`, `nome`, `email`, `admin=False` |
| Login válido (admin) | Retorna dict com `admin=True` |
| Conexão fechada após consulta | `conn.close()` é chamado mesmo em caso de erro |

#### `ativar_por_token(token)` — 5 casos
Valida o token de ativação na URL, verifica expiração e ativa o usuário no banco.

| Caso | Resultado esperado |
|---|---|
| Token inválido | `False, "Token inválido."` |
| Token expirado | `False, "Link de ativação expirado..."` |
| Token válido | `True, nome_do_usuario` |
| Token válido — commit | `conn.commit()` é chamado |
| Token válido — conexão | `conn.close()` é chamado |

#### `gerar_token_ativacao(usuario_id)` — 6 casos
Gera um UUID, calcula a expiração em 24 horas e persiste no banco.

| Caso | Resultado esperado |
|---|---|
| Retorna string UUID | Resultado é string no formato UUID |
| Tokens únicos | Duas chamadas geram tokens diferentes |
| UPDATE executado | `cursor.execute` é chamado com `UPDATE usuarios` |
| Commit chamado | `conn.commit()` é chamado |
| Conexão fechada | `conn.close()` é chamado |
| Expira em 24h | Data de expiração é aproximadamente `now + 24h` |

#### `gerar_token_senha(usuario_id)` — 5 casos
Gera token e expiração para redefinição de senha. Mesma lógica da ativação, com campo diferente.

| Caso | Resultado esperado |
|---|---|
| Retorna string UUID | Resultado é string no formato UUID |
| Tokens únicos | Duas chamadas geram tokens diferentes |
| UPDATE executado | `cursor.execute` chamado com `UPDATE usuarios` |
| Commit chamado | `conn.commit()` é chamado |
| Conexão fechada | `conn.close()` é chamado |

#### `processar_salvamento(df, tabela, pk, usuario)` — 8 casos
Persiste as edições feitas nas tabelas de produtos e clientes, protegendo colunas de auditoria.

| Caso | Resultado esperado |
|---|---|
| Sucesso | Retorna `True` |
| UPDATE por linha | `cursor.execute` chamado uma vez por linha do DataFrame |
| Commit chamado | `conn.commit()` é chamado |
| Conexão fechada (sucesso) | `conn.close()` é chamado |
| Nome vazio removido | Linhas com `Nome` vazio não geram UPDATE |
| Colunas de auditoria protegidas | `criado_por`, `criado_em` etc. não aparecem no SET do UPDATE |
| Retorna False em exceção | Captura exceção e retorna `False` |
| Conexão fechada (exceção) | `conn.close()` é chamado mesmo em caso de erro |

---

### `test_relatorios.py` — 19 testes

Cobre as funções puras extraídas das abas de relatórios. Testadas com DataFrames sintéticos simples.

#### `calcular_faturamento_mensal(df_vendas, ano)` — 10 casos
Recebe um DataFrame de vendas e um ano, e retorna um DataFrame com 12 meses, faturamento, quantidade de vendas e ticket médio.

| Caso | Resultado esperado |
|---|---|
| Sempre 12 linhas | Resultado tem exatamente 12 linhas |
| Colunas obrigatórias | Contém `Mes`, `Mes_Nome`, `Qtd_Vendas`, `Faturamento`, `Ticket_Medio` |
| Faturamento de janeiro | Soma correta das vendas do mês |
| Ticket médio de janeiro | `Faturamento / Qtd_Vendas` correto |
| Mês sem vendas | `Faturamento`, `Qtd_Vendas` e `Ticket_Medio` = 0 |
| Ano diferente | Todos os meses com valor 0 |
| DataFrame vazio | Retorna 12 linhas zeradas sem erro |
| Venda única | Faturamento e ticket médio iguais ao valor da venda |
| Ticket médio zero sem vendas | Nenhum mês vazio tem ticket > 0 |
| Múltiplas vendas no mesmo mês | Soma, contagem e ticket médio corretos |

#### `calcular_top10_produtos(df_itens)` — 9 casos
Recebe um DataFrame de itens de venda e retorna os top 10 produtos por média de unidades vendidas por mês.

| Caso | Resultado esperado |
|---|---|
| Colunas obrigatórias | Contém `Produto`, `Qtd_Media`, `Valor_Medio`, `Meses_Ativos` |
| Ordenação decrescente | `Qtd_Media` em ordem decrescente |
| Índice começa em 1 | Primeiro índice é 1 (ranking) |
| Produto líder correto | Produto com maior média aparece em primeiro |
| Máximo 10 produtos | Nunca retorna mais de 10 linhas |
| DataFrame vazio | Retorna DataFrame vazio sem erro |
| Produto único | Retorna 1 linha com os valores corretos |
| Média mensal calculada | Média de unidades entre os meses com venda |
| Meses ativos corretos | Conta corretamente os meses em que o produto vendeu |

---

### `test_inadimplencia.py` — 11 testes

Cobre as funções da sub-aba Inadimplência. A conexão com o PostgreSQL é substituída por `MagicMock`.

#### `buscar_inadimplentes()` — 2 casos
Retorna DataFrame com clientes que possuem vendas com saldo em aberto, agrupados e ordenados por saldo total decrescente.

| Caso | Resultado esperado |
|---|---|
| Colunas obrigatórias | Contém `cliente_id`, `cliente`, `vendas_em_aberto`, `saldo_total`, `mais_antiga` |
| Sem inadimplentes | Retorna DataFrame vazio com as colunas corretas |

#### `buscar_vendas_em_aberto(cliente_id)` — 2 casos
Retorna DataFrame com as vendas em aberto de um cliente específico, ordenadas pela data mais antiga.

| Caso | Resultado esperado |
|---|---|
| Colunas obrigatórias | Contém `venda_id`, `data`, `total`, `pago`, `saldo` |
| Passa cliente_id correto | O valor `42` aparece nos parâmetros da query executada |

#### `registrar_cobranca(venda_id, data_cobranca, observacao, usuario_id)` — 3 casos
Insere um registro na tabela `vendas_cobranças` com data, observação e usuário responsável.

| Caso | Resultado esperado |
|---|---|
| Execute chamado | `cursor.execute` chamado com INSERT em `vendas_cobranças` |
| Commit chamado | `conn.commit()` é chamado |
| Conexão fechada em exceção | `conn.close()` é chamado mesmo quando `cursor.execute` lança exceção |

#### `registrar_pagamento(venda_id, valor, data_pagamento, observacao, usuario_id)` — 4 casos
Insere um registro na tabela `vendas_pagamentos` com valor, data, observação e usuário responsável.

| Caso | Resultado esperado |
|---|---|
| Execute chamado | `cursor.execute` chamado com INSERT em `vendas_pagamentos` |
| Commit chamado | `conn.commit()` é chamado |
| Conexão fechada em exceção | `conn.close()` é chamado mesmo quando `cursor.execute` lança exceção |
| Validação de valor máximo | Valor superior ao saldo em aberto é detectado como inválido |

---

## Refatorações realizadas no `app.py` para viabilizar os testes

As mudanças abaixo melhoraram a testabilidade do código sem alterar nenhum comportamento da aplicação:

- **`converter` extraída para o escopo de módulo** — antes estava aninhada dentro de `processar_salvamento`, o que impedia sua importação direta. Agora é uma função de primeiro nível, reutilizável e testável.

- **`processar_salvamento` recebe `usuario_logado` como parâmetro** — antes dependia da variável global `usuario_logado = st.session_state.usuario`, que só existe em tempo de execução do Streamlit. Agora o valor é passado explicitamente, eliminando o acoplamento com o estado da sessão.

- **`calcular_faturamento_mensal` e `calcular_top10_produtos` extraídas das abas** — a lógica de cálculo estava embutida diretamente nas abas do Streamlit, misturada com chamadas de UI (`st.selectbox`, `st.metric` etc.). Ao separá-las em funções puras, tornam-se testáveis com DataFrames simples. As abas agora apenas chamam essas funções e exibem os resultados.

- **`formatar_df` criada para contexto de dataframe** — a função `formatar_br` usa `R\$` para escapar o cifrão no Markdown (evitando que o Streamlit interprete como delimitador LaTeX). Para colunas de `st.dataframe`, o texto é renderizado como texto puro, e a barra apareceria literalmente. A `formatar_df` usa `R$` sem escape, resolvendo o problema de exibição nas sub-abas de relatórios.

---

## Situação atual

| Arquivo | Testes | Status |
|---|---|---|
| `test_funcoes_puras.py` | 53 | ✅ Todos passando |
| `test_banco_mock.py` | 25 | ✅ Todos passando |
| `test_relatorios.py` | 19 | ✅ Todos passando |
| `test_inadimplencia.py` | 11 | ✅ Todos passando |
| **Total** | **108** | ✅ |
