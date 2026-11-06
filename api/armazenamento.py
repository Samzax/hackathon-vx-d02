"""Onde ficam os documentos originais: pasta local (dev) ou S3 privado (AWS).

O nome é o SHA-256 do conteúdo: o mesmo PDF enviado duas vezes vira um objeto só, e o hash
gravado na evidência prova que o arquivo não mudou depois."""

from __future__ import annotations

import re

from .config import Config, pasta_local


def _seguro(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nome)[-80:] or "documento.pdf"


def guardar(cfg: Config, sha256: str, nome: str, dados: bytes) -> str:
    chave = f"evidencias/{sha256[:2]}/{sha256}/{_seguro(nome)}"
    if pasta := pasta_local(cfg):
        destino = pasta / chave
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.exists():
            destino.write_bytes(dados)
        return str(destino)
    from regulaia import aws

    bucket, _, prefixo = cfg.armazenamento.removeprefix("s3://").partition("/")
    chave = f"{prefixo.rstrip('/')}/{chave}" if prefixo else chave
    aws.cliente("s3").put_object(Bucket=bucket, Key=chave, Body=dados, ServerSideEncryption="AES256",
                                 ContentType="application/pdf")
    return f"s3://{bucket}/{chave}"
