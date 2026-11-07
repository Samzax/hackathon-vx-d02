"""Build da imagem na própria AWS: CodeBuild compila o api/Dockerfile e publica no ECR.

    código (zip) ──> S3 (fonte) ──> CodeBuild (docker build, modo privilegiado) ──> ECR regulaia-api:<tag>
                                                                                      │
                                         pilha RegulaIA (-c imagem_tag=<tag>) ────────┘

Por quê: o deploy não depende de Docker na máquina de quem sobe (e o mesmo build serve para um CI).
As imagens base vêm do espelho público do ECR (public.ecr.aws/docker/library), não do Docker Hub:
o CodeBuild sai por IPs compartilhados e o Docker Hub limita pull anônimo.

    python infra/construir.py           # zipa o código, sobe no S3, roda o build e espera; imprime a tag
"""

from __future__ import annotations

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    aws_logs as logs,
    aws_s3 as s3,
)
from constructs import Construct

REPOSITORIO = "regulaia-api"   # nome legado: o repositório ECR já existe na conta com as imagens publicadas
FONTE = "fonte.zip"
ESPELHO = "public.ecr.aws/docker/library"


class MitraBuild(Stack):
    def __init__(self, scope: Construct, id_: str, **kw) -> None:
        super().__init__(scope, id_, **kw)

        repo = ecr.Repository(
            self, "Imagens", repository_name=REPOSITORIO,
            image_scan_on_push=True,
            lifecycle_rules=[ecr.LifecycleRule(max_image_count=15, description="guarda as 15 mais novas")],
            removal_policy=RemovalPolicy.DESTROY, empty_on_delete=True,
        )
        fonte = s3.Bucket(
            self, "Fonte",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(7))],
            removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True,
        )

        projeto = codebuild.Project(
            self, "Build",
            description="docker build do api/Dockerfile e push para o ECR",
            source=codebuild.Source.s3(bucket=fonte, path=FONTE),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                compute_type=codebuild.ComputeType.MEDIUM,     # o build do Next.js passa de 3 GB
                privileged=True,                               # docker dentro do build
            ),
            environment_variables={
                "REPO_URI": codebuild.BuildEnvironmentVariable(value=repo.repository_uri),
                "TAG": codebuild.BuildEnvironmentVariable(value="manual"),
                "ESPELHO": codebuild.BuildEnvironmentVariable(value=ESPELHO),
            },
            timeout=Duration.minutes(30),
            logging=codebuild.LoggingOptions(cloud_watch=codebuild.CloudWatchLoggingOptions(
                log_group=logs.LogGroup(self, "LogsBuild", retention=logs.RetentionDays.ONE_MONTH,
                                        removal_policy=RemovalPolicy.DESTROY))),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {"commands": [
                        "aws ecr get-login-password | docker login --username AWS --password-stdin ${REPO_URI%%/*}",
                    ]},
                    "build": {"commands": [
                        "docker build -f api/Dockerfile --build-arg REGISTRO=$ESPELHO -t $REPO_URI:$TAG .",
                    ]},
                    "post_build": {"commands": [
                        'if [ "$CODEBUILD_BUILD_SUCCEEDING" = "1" ]; then docker push $REPO_URI:$TAG; fi',
                    ]},
                },
            }),
        )
        repo.grant_pull_push(projeto)

        CfnOutput(self, "Repositorio", value=repo.repository_uri)
        CfnOutput(self, "BucketFonte", value=fonte.bucket_name)
        CfnOutput(self, "ProjetoBuild", value=projeto.project_name)
