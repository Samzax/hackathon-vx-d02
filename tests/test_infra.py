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

from mitra import db  # noqa: E402

sys.path.insert(0, str(db.ROOT / "infra"))
from mitra_stack import Mitra  # noqa: E402


@pytest.fixture(scope="module")
def modelo() -> assertions.Template:
    app = cdk.App()
    # imagem pública no lugar do build da imagem: o teste confere a pilha, não o Docker
    pilha = Mitra(app, "Teste", imagem=ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/python:3.13-slim"),
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
            assert {"DB_SENHA", "MITRA_TOKEN_SERVICO"} <= nomes_seg
            assert not nomes_env & {"DB_SENHA", "MITRA_TOKEN_SERVICO", "MITRA_DATABASE_URL"}


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


def test_descoberta_roda_toda_semana_pelo_eventbridge(modelo):
    modelo.has_resource_properties("AWS::Events::Rule", {"ScheduleExpression": "cron(0 6 ? * SUN *)"})
    comandos = [" ".join(c.get("Command", [])) for d in modelo.find_resources("AWS::ECS::TaskDefinition").values()
                for c in d["Properties"]["ContainerDefinitions"]]
    assert any("api.jobs descoberta" in c for c in comandos)


def test_ia_desligada_por_padrao_e_chave_de_dados_no_secrets_manager(modelo):
    for d in modelo.find_resources("AWS::ECS::TaskDefinition").values():
        for c in d["Properties"]["ContainerDefinitions"]:
            env = {e["Name"]: e["Value"] for e in c.get("Environment", [])}
            assert env["MITRA_BEDROCK"] == ""
            assert {"MITRA_CHAVE_DADOS", "MITRA_SENHA_DEMO"} <= {s["Name"] for s in c.get("Secrets", [])}


def test_bedrock_liberado_nas_outras_regioes_do_perfil_de_inferencia(modelo):
    recursos = set()
    for p in modelo.find_resources("AWS::IAM::Policy").values():
        for s in p["Properties"]["PolicyDocument"]["Statement"]:
            if s.get("Sid") == "IAViaBedrock":
                r = s["Resource"]
                recursos |= {x if isinstance(x, str) else str(x) for x in (r if isinstance(r, list) else [r])}
    assert "arn:aws:bedrock:*::foundation-model/*" in recursos


def test_ia_ligada_com_contexto():
    app = cdk.App()
    pilha = Mitra(app, "TesteIA", ia=True, imagem=ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/python:3.13-slim"),
                     env=cdk.Environment(account="123456789012", region="us-east-1"))
    defs = assertions.Template.from_stack(pilha).find_resources("AWS::ECS::TaskDefinition")
    envs = [{e["Name"]: e["Value"] for e in c.get("Environment", [])}
            for d in defs.values() for c in d["Properties"]["ContainerDefinitions"]]
    assert all(e["MITRA_BEDROCK"] == "1" for e in envs)


def test_imagem_do_ecr_pela_tag():
    app = cdk.App()
    pilha = Mitra(app, "TesteEcr", imagem_tag="abc123", env=cdk.Environment(account="123456789012", region="us-east-1"))
    texto = str(assertions.Template.from_stack(pilha).to_json())
    assert "regulaia-api" in texto and "abc123" in texto


def test_build_na_aws_privilegiado_e_publica_no_ecr():
    from build_stack import MitraBuild

    app = cdk.App()
    t = assertions.Template.from_stack(MitraBuild(app, "TesteBuild", env=cdk.Environment(
        account="123456789012", region="us-east-1")))
    t.has_resource_properties("AWS::ECR::Repository", {"RepositoryName": "regulaia-api"})
    t.has_resource_properties("AWS::CodeBuild::Project", {"Environment": assertions.Match.object_like(
        {"PrivilegedMode": True})})
    t.has_resource_properties("AWS::S3::Bucket", {"PublicAccessBlockConfiguration": assertions.Match.object_like(
        {"BlockPublicAcls": True})})


def test_https_pelo_cloudfront_sem_cache_na_api(modelo):
    modelo.has_resource_properties("AWS::CloudFront::Distribution", {"DistributionConfig": assertions.Match.object_like({
        "DefaultCacheBehavior": assertions.Match.object_like({
            "ViewerProtocolPolicy": "redirect-to-https",
            "AllowedMethods": assertions.Match.array_with(["POST", "DELETE"]),
            "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",         # CachingDisabled
        })})})
    for d in modelo.find_resources("AWS::ECS::TaskDefinition").values():
        for c in d["Properties"]["ContainerDefinitions"]:
            assert {e["Name"]: e["Value"] for e in c.get("Environment", [])}["MITRA_COOKIE_SEGURO"] == "1"


def test_alb_so_aceita_o_cloudfront(modelo):
    for sg in modelo.find_resources("AWS::EC2::SecurityGroup").values():
        for regra in sg["Properties"].get("SecurityGroupIngress", []):
            assert regra.get("CidrIp") != "0.0.0.0/0", regra
    assert "pl-3b927c52" in str(modelo.to_json())


def test_com_certificado_proprio_o_cloudfront_sai():
    app = cdk.App()
    pilha = Mitra(app, "TesteCert", certificado_arn="arn:aws:acm:us-east-1:123456789012:certificate/abc",
                     imagem=ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/python:3.13-slim"),
                     env=cdk.Environment(account="123456789012", region="us-east-1"))
    assertions.Template.from_stack(pilha).resource_count_is("AWS::CloudFront::Distribution", 0)


def test_descricoes_que_o_cloudformation_aceita(modelo):
    """O CloudFormation recusa acento na descrição do security group (o deploy quebraria no meio)."""
    import re

    padrao = re.compile(r"^[a-zA-Z0-9. _\-:/()#,@\[\]+=&;{}!$*]*$")
    for sg in modelo.find_resources("AWS::EC2::SecurityGroup").values():
        assert padrao.match(sg["Properties"]["GroupDescription"]), sg["Properties"]["GroupDescription"]
    for r in modelo.find_resources("AWS::EC2::SecurityGroupIngress").values():
        assert padrao.match(r["Properties"].get("Description", "")), r["Properties"]["Description"]
