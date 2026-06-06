# Testes Automatizados — Frui Partis

Documentação sobre a estratégia de testes do projeto, como está organizada e como executar.

---

## Estrutura de pastas

```
seu-projeto/
├── app.py
└── tests/
    ├── __init__.py                ← arquivo vazio, necessário para o pytest encontrar os testes
    ├── test_funcoes_puras.py      ← testes das funções puras (sem banco, sem Streamlit)
    └── test_banco_mock.py         ← testes das funções com banco de dados (usando mock)
```

---

## Dependências

Antes de rodar os testes, certifique-se de que as dependências estão instaladas no seu ambiente (ative o ambiente virtual antes, se usar um):

```bash
pip install pytest numpy bcrypt pandas
```

O `numpy` e o `pandas` geralmente já estão presentes por serem dependências do projeto.

---

## Como executar

**Rodar todos os testes de uma vez:**

```bash
pytest tests/ -v
```

**Rodar um arquivo específico:**

```bash
pytest tests/test_funcoes_puras.py -v
pytest tests/test_banco_mock.py -v
```

A flag `-v` é opcional, mas recomendada — ela exibe cada teste individualmente com o resultado. Sem ela, aparece apenas o resumo final.

---

## Estratégia de testes

O código foi dividido em dois grupos para fins de teste:

### 1. Funções puras

São funções que recebem uma entrada e retornam uma saída, sem depender de banco de dados, e-mail ou interface Streamlit. São as mais simples de testar e as mais confiáveis.

### 2. Funções com efeitos colaterais

São funções que dependem do banco de dados (PostgreSQL/Supabase), envio de e-mail ou da sessão do Streamlit. Precisam de **mock** — ou seja, substituições controladas dessas dependências — para serem testadas sem infraestrutura real. Nenhum dado é criado ou alterado no banco durante os testes.

### O que não testamos automaticamente

Telas, abas, dialogs e qualquer elemento que dependa de `st.*` (Streamlit) têm custo alto para automatizar e retorno baixo. Esses são cobertos por testes manuais.

---

## Arquivos de teste

### `test_funcoes_puras.py`

Cobre as funções puras extraídas do `app.py`. Nenhuma conexão com banco ou serviço externo é necessária para rodá-lo.

| Função | Casos testados |
|---|---|
| `formatar_br` | Inteiro, float, zero, negativo, string numérica, valor grande, arredondamento, centavos, string inválida, None |
| `formatar_markdown_br` | Prefixo com dupla barra, inteiro, zero, string inválida, diferença em relação à `formatar_br` |
| `validar_senha` | Senha válida, muito curta, muito longa, sem maiúscula, sem número, só números, limites mínimo e máximo, vazia |
| `validar_cpf_formato` | CPF formatado, só dígitos, vazio, com espaços, com letras, só pontuação |
| `converter` | `np.int64`, `np.float64`, `np.bool_` (True/False), NaN nativo, `np.nan`, string, int nativo, None |

### `test_banco_mock.py`

Cobre as funções que dependem do banco de dados. A conexão com o PostgreSQL é substituída por um objeto simulado (`MagicMock`), garantindo que nenhum banco real seja acessado.

| Função | Casos testados |
|---|---|
| `verificar_login` | E-mail não cadastrado, senha incorreta, usuário inativo, login válido comum, login válido admin, conexão fechada |
| `ativar_por_token` | Token inválido, token expirado, ativação com sucesso, commit chamado, conexão fechada |
| `gerar_token_ativacao` | Retorna UUID, tokens únicos, UPDATE executado, commit, conexão fechada, expiração em 24h |
| `gerar_token_senha` | Retorna UUID, tokens únicos, UPDATE executado, commit, conexão fechada |
| `processar_salvamento` | Sucesso, UPDATE por linha, commit, conexão fechada, remoção de nomes vazios, proteção de colunas de auditoria, retorno False em exceção, conexão fechada mesmo em exceção |

---

## Refatorações realizadas no `app.py`

As seguintes mudanças foram feitas para melhorar a testabilidade do código, sem alterar nenhum comportamento da aplicação:

- **`converter` extraída para o escopo de módulo** — antes estava aninhada dentro de `processar_salvamento`, o que impedia sua importação e teste direto. Agora é uma função de primeiro nível, reutilizável e testável.

- **`import numpy as np` adicionado ao topo** — necessário após a extração de `converter`, que usa tipos numpy.

- **`processar_salvamento` recebe `usuario_logado` como parâmetro** — antes dependia da variável global `usuario_logado = st.session_state.usuario`, que só existe em tempo de execução do Streamlit. Agora o valor é passado explicitamente pela chamada, eliminando o acoplamento com o estado da sessão.

---

## Próximos passos

- [x] Criar `test_funcoes_puras.py`
- [x] Criar `test_banco_mock.py`
- [x] Refatorar `app.py` para melhorar testabilidade (`converter` e `usuario_logado`)
- [ ] Avaliar cobertura das funções de carregamento de dados (`carregar_estoque`, `carregar_clientes`, `carregar_vendas`)
- [ ] Avaliar cobertura dos cálculos de relatório (faturamento mensal, top 10 produtos)
