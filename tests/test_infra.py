"""A pilha da AWS, conferida sem conta AWS: o CDK gera o CloudFormation e o teste lê o resultado.

Precisa do grupo `infra` (uv sync --group infra) e do Node (o aws-cdk-lib roda sobre jsii).
Sem eles, os testes são pulados; o CI tem um job só para isto."""

from __future__ import annotations

import shutil
import sys

import pytest

cdk = pytest.importorskip("aws_cdk")
if shutil.which("node") is None:
    pytest.skip("o aws-cdk-lib precisa do Node", allow_module_level=True)

from aws_cdk import assertions, aws_ecs as ecs  # noqa: E402

from regulaia import db  # noqa: E402

sys.path.insert(0, str(db.ROOT / "infra"))
from regulaia_stack import RegulaIA  # noqa: E402


@pytest.fixture(scope="module")
def modelo() -> assertions.Template:
    app = cdk.App()
    # imagem pública no lugar do build da imagem: o teste confere a pilha, não o Docker
    pilha = RegulaIA(app, "Teste", imagem=ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/python:3.13-slim"),
                     env=cdk.Environment(account="123456789012", region="us-east-1"))
    return assertions.Template.from_stack(pilha)


def test_banco_postgres_privado_e_criptografado(modelo):
    modelo.has_resource_properties("AWS::RDS::DBInstance", {
        "Engine": "postgres", "PubliclyAccessible": False, "StorageEncrypted": True, "DBName": "regulaia"})


def test_sem_nat_gateway(modelo):
    modelo.resource_count_is("AWS::EC2::NatGateway", 0)


def test_bucket_bloqueia_acesso_publico_e_exige_tls(modelo):
    modelo.has_resource_properties("AWS::S3::Bucket", {"PublicAccessBlockConfiguration": {
        "BlockPublicAcls": True, "BlockPublicPolicy": True, "IgnorePublicAcls": True, "RestrictPublicBuckets": True}})
    modelo.has_resource_properties("AWS::S3::BucketPolicy", {"PolicyDocument": {"Statement": assertions.Match.array_with([
        assertions.Match.object_like({"Effect": "Deny", "Condition": {"Bool": {"aws:SecureTransport": "false"}}})])}})


def test_api_no_fargate_atras_do_alb_com_healthcheck(modelo):
    modelo.has_resource_properties("AWS::ECS::Service", {"LaunchType": "FARGATE"})
    modelo.has_resource_properties("AWS::ElasticLoadBalancingV2::TargetGroup", {"HealthCheckPath": "/health"})


def test_segredos_vem_do_secrets_manager_e_nao_do_ambiente(modelo):
    defs = modelo.find_resources("AWS::ECS::TaskDefinition")
    for d in defs.values():
        for c in d["Properties"]["ContainerDefinitions"]:
            nomes_env = {e["Name"] for e in c.get("Environment", [])}
            nomes_seg = {s["Name"] for s in c.get("Secrets", [])}
            assert {"DB_SENHA", "REGULAIA_TOKEN_SERVICO"} <= nomes_seg
            assert not nomes_env & {"DB_SENHA", "REGULAIA_TOKEN_SERVICO", "REGULAIA_DATABASE_URL"}


def test_radar_roda_todo_dia_pelo_eventbridge(modelo):
    modelo.has_resource_properties("AWS::Events::Rule", {"ScheduleExpression": "cron(0 9 * * ? *)"})


def test_tasks_podem_chamar_bedrock_e_textract(modelo):
    politicas = modelo.find_resources("AWS::IAM::Policy")
    acoes = set()
    for p in politicas.values():
        for s in p["Properties"]["PolicyDocument"]["Statement"]:
            a = s["Action"]
            acoes |= set(a if isinstance(a, list) else [a])
    assert {"bedrock:InvokeModel", "bedrock:Converse", "textract:DetectDocumentText"} <= acoes


def test_banco_so_aceita_a_api_e_o_radar(modelo):
    regras = modelo.find_resources("AWS::EC2::SecurityGroupIngress")
    no_banco = [r for r in regras.values() if r["Properties"].get("FromPort") == 5432]
    assert len(no_banco) == 2 and all("SourceSecurityGroupId" in r["Properties"] for r in no_banco)


def test_descricoes_que_o_cloudformation_aceita(modelo):
    """O CloudFormation recusa acento na descrição do security group (o deploy quebraria no meio)."""
    import re

    padrao = re.compile(r"^[a-zA-Z0-9. _\-:/()#,@\[\]+=&;{}!$*]*$")
    for sg in modelo.find_resources("AWS::EC2::SecurityGroup").values():
        assert padrao.match(sg["Properties"]["GroupDescription"]), sg["Properties"]["GroupDescription"]
    for r in modelo.find_resources("AWS::EC2::SecurityGroupIngress").values():
        assert padrao.match(r["Properties"].get("Description", "")), r["Properties"]["Description"]
