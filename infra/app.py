"""Entrada do CDK. Duas pilhas: RegulaIABuild (ECR + CodeBuild) e RegulaIA (a aplicação Mitra).

    cd infra && npx aws-cdk@2 synth                              # gera o CloudFormation (sem conta AWS)
    cd infra && npx aws-cdk@2 deploy RegulaIABuild               # uma vez: repositório e projeto de build
    uv run --with "botocore[crt]" python infra/construir.py      # build da imagem na AWS; imprime a tag
    cd infra && npx aws-cdk@2 deploy RegulaIA -c imagem_tag=<tag>          # sobe a aplicação sem IA
    cd infra && npx aws-cdk@2 deploy RegulaIA -c imagem_tag=<tag> -c ia=1  # com o Bedrock ligado
    npx aws-cdk@2 deploy RegulaIA -c certificado=arn:aws:acm:...           # com HTTPS (domínio próprio)

Sem `imagem_tag`, o CDK constrói a imagem localmente (precisa de Docker).

Os ids das pilhas (RegulaIA, RegulaIABuild) mantêm o nome antigo do produto: são as pilhas já
deployadas na conta do evento — renomear o id criaria um ambiente novo do zero, sem os dados.
"""

import os

import aws_cdk as cdk

from build_stack import MitraBuild
from mitra_stack import Mitra

app = cdk.App()
ambiente = cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region="us-east-1")
MitraBuild(app, "RegulaIABuild", env=ambiente,
           description="Mitra: build da imagem na AWS (ECR + CodeBuild)")
Mitra(
    app, "RegulaIA",
    certificado_arn=app.node.try_get_context("certificado"),
    imagem_tag=app.node.try_get_context("imagem_tag"),
    ia=str(app.node.try_get_context("ia") or "") in ("1", "true", "sim"),
    env=ambiente,
    description="Mitra: torre de controle regulatória (API, Postgres, S3, radar do DOU)",
)
cdk.Tags.of(app).add("projeto", "mitra")
app.synth()
