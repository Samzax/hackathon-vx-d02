"""Cliente boto3 para os serviços da AWS que a torre usa (Bedrock, Textract, S3).

Credencial: o perfil AWS do ambiente (AWS_PROFILE) ou as credenciais temporárias que a
organização do evento fornecer. Nunca chave no código nem no .env. Região: AWS_REGION, us-east-1 por padrão.
"""

from __future__ import annotations

import os


def cliente(servico: str, regiao: str | None = None, **kw):
    import boto3

    # "AWS_PROFILE=" vazio no .env faz o boto3 procurar um perfil de nome "" e falhar: vazio = perfil padrão
    if "AWS_PROFILE" in os.environ and not os.environ["AWS_PROFILE"].strip():
        del os.environ["AWS_PROFILE"]
    return boto3.Session().client(servico, region_name=regiao or os.environ.get("AWS_REGION") or "us-east-1", **kw)
