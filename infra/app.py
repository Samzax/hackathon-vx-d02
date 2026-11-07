"""Entrada do CDK.

    cd infra && npx aws-cdk@2 synth                     # gera o CloudFormation (sem conta AWS)
    cd infra && npx aws-cdk@2 deploy                    # sobe na conta do perfil atual (us-east-1)
    npx aws-cdk@2 deploy -c certificado=arn:aws:acm:... # com HTTPS (domínio próprio)
"""

import os

import aws_cdk as cdk

from regulaia_stack import RegulaIA

app = cdk.App()
RegulaIA(
    app, "RegulaIA",
    certificado_arn=app.node.try_get_context("certificado"),
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region="us-east-1"),
    description="RegulaIA: torre de controle regulatória (API, Postgres, S3, radar do DOU)",
)
cdk.Tags.of(app).add("projeto", "regulaia")
app.synth()
