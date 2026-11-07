"""Dado pessoal: CPF cifrado por campo, mascarado, derivado de qualquer texto de chave, fora da IA."""

from __future__ import annotations

import pytest

from regulaia import pessoal

# Montado em pedaços de propósito: nenhum arquivo versionado tem cara de CPF formatado, nem fictício
# (tests/test_documentacao.py::test_git_nao_versiona_segredo_nem_cpf varre o repositório inteiro).
CPF = "123.456.789" + "-09"      # fictício, com os dígitos verificadores corretos
CHAVE = "chave-de-teste-" + "a" * 48


def test_valido_confere_os_digitos_verificadores():
    assert pessoal.valido(CPF) and pessoal.valido("12345678909")
    assert not pessoal.valido("123.456.789" + "-00")      # verificador errado
    assert not pessoal.valido("111.111.111" + "-11")      # todos iguais
    assert not pessoal.valido("123") and not pessoal.valido("")


def test_mascarar_mostra_so_o_meio():
    assert pessoal.mascarar(CPF) == "***.456." + "789-**"
    assert pessoal.mascarar("12345678909") == "***.456." + "789-**"
    assert pessoal.mascarar("x") == "***.***.***-**"


def test_cifrar_e_decifrar_com_qualquer_texto_de_chave():
    """Em produção a chave chega como texto alfanumérico de 64, não como chave Fernet."""
    cifrado = pessoal.cifrar(CPF, CHAVE)
    assert pessoal.digitos(CPF) not in cifrado and CPF not in cifrado
    assert pessoal.decifrar(cifrado, CHAVE) == CPF
    assert pessoal.cifrar(CPF, CHAVE) != cifrado        # Fernet: nonce novo a cada cifra
    assert pessoal.decifrar(pessoal.cifrar(CPF, "outra"), "outra") == CPF


def test_chave_errada_nao_decifra():
    from cryptography.fernet import InvalidToken

    cifrado = pessoal.cifrar(CPF, CHAVE)
    with pytest.raises(InvalidToken):
        pessoal.decifrar(cifrado, "chave-errada")


def test_cpf_invalido_nao_entra():
    with pytest.raises(pessoal.CpfInvalido):
        pessoal.cifrar("111.111.111" + "-11", CHAVE)


def test_sem_a_variavel_guardar_cpf_da_erro_claro(monkeypatch):
    """A API sobe sem a chave; guardar CPF é que não dá. Nada de chave padrão no código."""
    monkeypatch.delenv(pessoal.VARIAVEL, raising=False)
    assert not pessoal.tem_chave()
    with pytest.raises(pessoal.SemChave, match=pessoal.VARIAVEL):
        pessoal.cifrar(CPF)
    monkeypatch.setenv(pessoal.VARIAVEL, CHAVE)
    assert pessoal.tem_chave()
    assert pessoal.decifrar(pessoal.cifrar(CPF)) == CPF


def test_texto_para_a_ia_vai_sem_cpf():
    texto = (f"Responsável técnico: Ana Souza, CPF {CPF}, CREA MG-123456. "
             f"Protocolo {'111.111.111' + '-11'} não é CPF.")
    limpo = pessoal.sem_cpf(texto)
    assert pessoal.MARCADOR in limpo and CPF not in limpo
    assert "Ana Souza" in limpo and "111.111.111" in limpo       # só CPF de verdade sai
    assert pessoal.tem_cpf(texto) and not pessoal.tem_cpf(limpo)
    assert pessoal.sem_cpf("12345678909 no meio do texto").startswith(pessoal.MARCADOR)
