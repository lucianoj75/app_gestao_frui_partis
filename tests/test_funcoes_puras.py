"""
Testes unitários para as funções puras do app.py.

Como executar:
    pip install pytest numpy
    pytest test_funcoes_puras.py -v

Nota sobre `converter`:
    A função está definida dentro de `processar_salvamento`, o que impede
    sua importação direta. Ela foi replicada aqui para fins de teste.
    Recomenda-se movê-la para o escopo de módulo no app.py para facilitar
    manutenção e testes futuros.
"""

import re
import math
import pytest
import numpy as np


# =============================================================================
# Replicação das funções puras extraídas do app.py
# =============================================================================

def formatar_br(valor):
    try:
        return f"R\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor


def formatar_df(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor


def formatar_markdown_br(valor):
    try:
        return f"R\\\\$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor


def validar_senha(senha):
    if len(senha) < 6 or len(senha) > 10:
        return "A senha deve ter entre 6 e 10 caracteres."
    if not any(c.isupper() for c in senha):
        return "A senha deve ter pelo menos uma letra maiúscula."
    if not any(c.isdigit() for c in senha):
        return "A senha deve ter pelo menos um número."
    return None


def validar_cpf_formato(cpf):
    return re.sub(r'\D', '', cpf)


def converter(v):
    """Converte tipos numpy para tipos nativos Python compatíveis com PostgreSQL."""
    if isinstance(v, np.integer):  return int(v)
    if isinstance(v, np.floating): return float(v)
    if isinstance(v, np.bool_):    return bool(v)
    if v != v:                     return None  # NaN
    return v


# =============================================================================
# Testes: formatar_br
# =============================================================================

class TestFormatarBr:

    def test_valor_inteiro(self):
        assert formatar_br(1000) == "R\\$ 1.000,00"

    def test_valor_float(self):
        assert formatar_br(1234.56) == "R\\$ 1.234,56"

    def test_valor_zero(self):
        assert formatar_br(0) == "R\\$ 0,00"

    def test_valor_negativo(self):
        assert formatar_br(-50.5) == "R\\$ -50,50"

    def test_valor_string_numerica(self):
        # Aceita string que pode ser convertida para float
        assert formatar_br("250.99") == "R\\$ 250,99"

    def test_valor_grande(self):
        assert formatar_br(1000000) == "R\\$ 1.000.000,00"

    def test_valor_string_invalida(self):
        # Deve retornar o próprio valor original sem lançar exceção
        resultado = formatar_br("abc")
        assert resultado == "abc"

    def test_valor_none(self):
        # None não pode ser convertido; deve retornar None sem exceção
        resultado = formatar_br(None)
        assert resultado is None

    def test_arredondamento_duas_casas(self):
        assert formatar_br(9.999) == "R\\$ 10,00"

    def test_valor_centavos(self):
        assert formatar_br(0.05) == "R\\$ 0,05"


# =============================================================================
# Testes: formatar_markdown_br
# =============================================================================

class TestFormatarMarkdownBr:

    def test_prefixo_escapado(self):
        # Deve conter R\\$ (dupla barra) para renderizar corretamente em markdown
        resultado = formatar_markdown_br(100)
        assert resultado.startswith("R\\\\$")

    def test_valor_inteiro(self):
        assert formatar_markdown_br(1000) == "R\\\\$ 1.000,00"

    def test_valor_zero(self):
        assert formatar_markdown_br(0) == "R\\\\$ 0,00"

    def test_valor_string_invalida(self):
        resultado = formatar_markdown_br("xyz")
        assert resultado == "xyz"

    def test_diferenca_entre_funcoes(self):
        # formatar_markdown_br deve ter mais barras que formatar_br
        r_br  = formatar_br(100)
        r_md  = formatar_markdown_br(100)
        assert r_md.count("\\") > r_br.count("\\")


# =============================================================================
# Testes: formatar_df
# =============================================================================

class TestFormatarDf:

    def test_sem_barra_no_prefixo(self):
        # Texto puro para st.dataframe — sem barra invertida antes do $
        resultado = formatar_df(100)
        assert resultado.startswith("R$ ")
        assert "\\" not in resultado

    def test_valor_inteiro(self):
        assert formatar_df(1000) == "R$ 1.000,00"

    def test_valor_float(self):
        assert formatar_df(1234.56) == "R$ 1.234,56"

    def test_valor_zero(self):
        assert formatar_df(0) == "R$ 0,00"

    def test_valor_negativo(self):
        assert formatar_df(-50.5) == "R$ -50,50"

    def test_valor_string_invalida(self):
        assert formatar_df("abc") == "abc"

    def test_valor_none(self):
        assert formatar_df(None) is None

    def test_diferente_de_formatar_br(self):
        # formatar_df não deve ter barra; formatar_br deve ter
        assert "\\" not in formatar_df(100)
        assert "\\" in formatar_br(100)


# =============================================================================
# Testes: validar_senha
# =============================================================================

class TestValidarSenha:

    def test_senha_valida(self):
        assert validar_senha("Senha1") is None

    def test_senha_valida_longa(self):
        assert validar_senha("Abcdef123!") is None

    def test_senha_muito_curta(self):
        erro = validar_senha("Ab1")
        assert erro == "A senha deve ter entre 6 e 10 caracteres."

    def test_senha_muito_longa(self):
        erro = validar_senha("Abcdefgh123")  # 11 caracteres
        assert erro == "A senha deve ter entre 6 e 10 caracteres."

    def test_senha_sem_maiuscula(self):
        erro = validar_senha("senha1")
        assert erro == "A senha deve ter pelo menos uma letra maiúscula."

    def test_senha_sem_numero(self):
        erro = validar_senha("SenhaSem")
        assert erro == "A senha deve ter pelo menos um número."

    def test_senha_so_numeros(self):
        # Sem maiúscula → erro de maiúscula (verificação ocorre antes do número)
        erro = validar_senha("123456")
        assert erro == "A senha deve ter pelo menos uma letra maiúscula."

    def test_senha_no_limite_minimo(self):
        # Exatamente 6 caracteres válidos
        assert validar_senha("Valid1") is None

    def test_senha_no_limite_maximo(self):
        # Exatamente 10 caracteres válidos
        assert validar_senha("Validaaa10") is None

    def test_senha_vazia(self):
        erro = validar_senha("")
        assert erro == "A senha deve ter entre 6 e 10 caracteres."


# =============================================================================
# Testes: validar_cpf_formato
# =============================================================================

class TestValidarCpfFormato:

    def test_cpf_formatado(self):
        assert validar_cpf_formato("123.456.789-09") == "12345678909"

    def test_cpf_so_digitos(self):
        assert validar_cpf_formato("12345678909") == "12345678909"

    def test_cpf_vazio(self):
        assert validar_cpf_formato("") == ""

    def test_cpf_com_espacos(self):
        assert validar_cpf_formato("123 456 789 09") == "12345678909"

    def test_cpf_com_letras(self):
        # Remove tudo que não for dígito, incluindo letras
        assert validar_cpf_formato("123ABC456") == "123456"

    def test_cpf_apenas_pontuacao(self):
        assert validar_cpf_formato("...-") == ""


# =============================================================================
# Testes: converter (numpy → Python nativo)
# =============================================================================

class TestConverter:

    def test_numpy_int(self):
        resultado = converter(np.int64(42))
        assert resultado == 42
        assert type(resultado) is int

    def test_numpy_float(self):
        resultado = converter(np.float64(3.14))
        assert abs(resultado - 3.14) < 1e-9
        assert type(resultado) is float

    def test_numpy_bool_true(self):
        resultado = converter(np.bool_(True))
        assert resultado is True
        assert type(resultado) is bool

    def test_numpy_bool_false(self):
        resultado = converter(np.bool_(False))
        assert resultado is False
        assert type(resultado) is bool

    def test_nan_retorna_none(self):
        assert converter(float("nan")) is None

    def test_numpy_nan_retorna_none(self):
        assert converter(np.nan) is None

    def test_string_passa_inalterada(self):
        assert converter("texto") == "texto"

    def test_int_nativo_passa_inalterado(self):
        assert converter(7) == 7

    def test_none_passa_inalterado(self):
        # None != None é False, então não entra no branch NaN; retorna None mesmo
        assert converter(None) is None
