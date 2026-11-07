"""Dado pessoal: CPF criptografado por campo, mascarado na leitura, nunca para a IA nem para o Git.

O CPF do responsável técnico é o único dado pessoal da plataforma (o resto é dado de pessoa jurídica,
público no SIGBM). Regras, todas exercidas por teste:

- **Guardado cifrado por campo** (Fernet, da biblioteca `cryptography`), com a chave em
  `MITRA_CHAVE_DADOS`. Em produção ela vem do Secrets Manager como texto alfanumérico; qualquer texto
  serve, porque a chave Fernet é derivada por SHA-256. **Sem a variável a API sobe, mas guardar CPF dá
  erro claro**: nada de chave padrão no código, que viraria cifra decorativa.
- **A API devolve mascarado** (`***.456.789-**`). Ver o CPF inteiro é do Regulatório e da TI da própria
  empresa, e cada visualização vai para a auditoria (quem viu, de quem, quando).
- **Nunca para a IA**: o texto que vai para a extração passa por `sem_cpf`, que troca cada CPF por um
  marcador. Nunca para a demo (lá só CPF fictício, marcado como fictício) nem para a conta AWS do evento.
- LGPD: `exportar` e `apagar` (rota da TI da empresa, auditada) atendem ao titular.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re

MARCADOR = "[CPF REMOVIDO]"
VARIAVEL = "MITRA_CHAVE_DADOS"
# ddd.ddd.ddd-dd ou 11 dígitos seguidos (nenhum CPF de exemplo neste repositório, nem fictício:
# tests/test_documentacao.py recusa arquivo versionado com cara de CPF formatado)
_CPF = re.compile(r"\b(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})\b")


class SemChave(RuntimeError):
    """Não há chave de criptografia: guardar dado pessoal sem cifra não é opção."""


class CpfInvalido(ValueError):
    pass


def digitos(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


def valido(cpf: str) -> bool:
    """Os dois dígitos verificadores do CPF. CPF de teste com todos os dígitos iguais não passa."""
    d = digitos(cpf)
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = (soma * 10) % 11
        if int(d[tamanho]) != (0 if resto == 10 else resto):
            return False
    return True


def formatar(cpf: str) -> str:
    d = digitos(cpf)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else cpf


def mascarar(cpf: str) -> str:
    """O CPF com os três primeiros dígitos e os dois verificadores trocados por '*' (só o miolo
    aparece): é o que a API devolve por padrão."""
    d = digitos(cpf)
    if len(d) != 11:
        return "***.***.***-**"
    return f"***.{d[3:6]}.{d[6:9]}-**"


def chave_de(texto: str):
    """A chave Fernet derivada de qualquer texto (o Secrets Manager entrega alfanumérico de 64)."""
    from cryptography.fernet import Fernet

    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(texto.encode("utf-8")).digest()))


def _chave(chave: str | None = None):
    texto = chave if chave is not None else os.environ.get(VARIAVEL)
    if not texto:
        raise SemChave(
            f"{VARIAVEL} não está definida: sem ela não dá para guardar CPF. Em produção a chave vem do "
            "Secrets Manager; em desenvolvimento, exporte qualquer texto nessa variável.")
    return chave_de(texto)


def tem_chave(chave: str | None = None) -> bool:
    return bool(chave if chave is not None else os.environ.get(VARIAVEL))


def cifrar(cpf: str, chave: str | None = None) -> str:
    """O CPF cifrado, pronto para a coluna. CPF que não fecha os verificadores não entra."""
    if not valido(cpf):
        raise CpfInvalido(f"{cpf!r} não é um CPF válido (confira os dígitos)")
    return _chave(chave).encrypt(digitos(cpf).encode("ascii")).decode("ascii")


def decifrar(cifrado: str, chave: str | None = None) -> str:
    """O CPF formatado. Usar só onde a regra permite ver, e sempre com auditoria."""
    return formatar(_chave(chave).decrypt(cifrado.encode("ascii")).decode("ascii"))


def sem_cpf(texto: str) -> str:
    """O texto com cada CPF trocado pelo marcador: é esta versão que vai para a IA."""
    return _CPF.sub(lambda m: MARCADOR if valido("".join(m.groups())) else m.group(0), texto or "")


def tem_cpf(texto: str) -> bool:
    return sem_cpf(texto) != (texto or "")
