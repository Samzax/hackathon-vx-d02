"""Onde fica o PDF original de cada evidência registrada (a prova do que foi entregue).

Sem configuração: pasta local data/evidencias/ (fora do Git).
MITRA_S3_BUCKET=nome-do-bucket: Amazon S3, na região do AWS_REGION, com criptografia no servidor.
O bucket deve ter o acesso público bloqueado (regra do evento); este módulo nunca cria nem muda bucket.

O endereço gravado no banco termina no nome do arquivo (.../<hash>/<nome>.pdf), então a torre mostra
o nome original; o hash do conteúdo evita que dois arquivos de mesmo nome se sobrescrevam.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASTA = ROOT / "data" / "evidencias"


def _nome_seguro(nome: str) -> str:
    base = Path(nome.replace("\\", "/")).name or "documento.pdf"
    return re.sub(r"[^\w.\-]+", "_", base)


def guardar(nome: str, conteudo: bytes, s3=None) -> str:
    """Guarda o original e devolve onde ficou (caminho relativo ao projeto, ou s3://bucket/chave)."""
    chave = f"evidencias/{hashlib.sha256(conteudo).hexdigest()[:16]}/{_nome_seguro(nome)}"
    bucket = os.environ.get("MITRA_S3_BUCKET", "").strip()
    if bucket:
        if s3 is None:
            from . import aws

            s3 = aws.cliente("s3")
        s3.put_object(Bucket=bucket, Key=chave, Body=conteudo, ContentType="application/pdf",
                      ServerSideEncryption="AES256")
        return f"s3://{bucket}/{chave}"
    destino = PASTA / chave.split("/", 1)[1]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    return destino.relative_to(ROOT).as_posix() if destino.is_relative_to(ROOT) else destino.as_posix()
