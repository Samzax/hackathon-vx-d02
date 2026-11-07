"""A RegulaIA na AWS (us-east-1), em uma pilha CDK.

    Internet ──HTTPS/HTTP──> ALB ──> ECS Fargate (API + front estático, mesma origem)
                                       │  ├── RDS Postgres 16 (subnets isoladas, sem acesso público)
                                       │  ├── S3 privado (documentos originais das evidências, por SHA-256)
                                       │  ├── Bedrock (IA: análise de atos e leitura de evidências)
                                       │  └── Textract (OCR de PDF escaneado)
    EventBridge (todo dia 06:00 BRT) ──> task Fargate: radar do DOU (mesma imagem, python -m api.jobs radar)
    EventBridge (domingo 03:00 BRT)  ──> task Fargate: descoberta de normas (python -m api.jobs descoberta)

Imagem: com `-c imagem_tag=<tag>`, vem do ECR (regulaia-api, construída pelo CodeBuild: infra/build_stack.py);
sem, o CDK constrói localmente com Docker. IA: `-c ia=1` liga o Bedrock; sem, a torre sobe sem IA
(as análises já gravadas e o cache da demo continuam aparecendo).

Decisões:
- **Sem NAT Gateway** (o item caro de uma VPC): as tasks ficam em subnet pública com IP próprio, e o
  security group só aceita tráfego vindo do ALB. O banco fica em subnet isolada, sem rota para a internet.
- **Segredos no Secrets Manager**: a senha do banco é gerada pela AWS e entra na task como variável;
  o token do agente MCP também. Nada de segredo na imagem nem no código.
- **Uma imagem, dois usos**: a mesma imagem (api/Dockerfile) roda a API e o job do radar.
- **Migração no start**: `alembic upgrade head` roda antes do uvicorn, com lock no Postgres (várias tasks).
- **Sem dado pessoal**: o SIGBM vai só com as linhas de empresa (CNPJ), como no repositório.
- **HTTPS sem domínio**: sem certificado próprio, um CloudFront fica na frente do ALB e dá
  https://<id>.cloudfront.net com certificado da AWS. O ALB só aceita os IPs do CloudFront (lista
  gerenciada), então ninguém fala HTTP direto com ele. Nada é cacheado, menos /_next/static/*
  (arquivos com hash no nome). Com `-c certificado=arn:...`, o ALB faz o HTTPS e o CloudFront sai.
"""

from __future__ import annotations

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_certificatemanager as acm,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origens_cf,
    aws_cloudwatch as cw,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_logs as logs,
    aws_rds as rds,
    aws_s3 as s3,
    aws_secretsmanager as sm,
)
from constructs import Construct

RAIZ = Path(__file__).resolve().parent.parent
BANCO = "regulaia"
# a URL do banco é montada na task a partir do segredo: estes caracteres quebrariam a URL
FORA_DA_SENHA = " %+~`#$&*()|[]{}:;<>?!'/@\"\\,="
# lista gerenciada com os IPs que o CloudFront usa para falar com a origem (um ID por região)
PREFIXO_CLOUDFRONT = {"us-east-1": "pl-3b927c52"}


class RegulaIA(Stack):
    def __init__(self, scope: Construct, id_: str, *, certificado_arn: str | None = None,
                 imagem: ecs.ContainerImage | None = None, imagem_tag: str | None = None,
                 ia: bool = False, **kw) -> None:
        super().__init__(scope, id_, **kw)

        # ------------------------------------------------------------------ rede
        vpc = ec2.Vpc(
            self, "Rede", max_azs=2, nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="publica", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="banco", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24),
            ],
        )
        # o S3 pela rede da AWS, sem sair para a internet
        vpc.add_gateway_endpoint("S3", service=ec2.GatewayVpcEndpointAwsService.S3)

        # ------------------------------------------------------------------ dados
        documentos = s3.Bucket(
            self, "Documentos",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[s3.LifecycleRule(noncurrent_version_expiration=Duration.days(90))],
        )

        sg_banco = ec2.SecurityGroup(self, "SgBanco", vpc=vpc, description="Postgres: only the API and the radar job",
                                     allow_all_outbound=False)
        banco = rds.DatabaseInstance(
            self, "Banco",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[sg_banco],
            database_name=BANCO,
            credentials=rds.Credentials.from_generated_secret("regulaia", exclude_characters=FORA_DA_SENHA),
            allocated_storage=20,
            storage_encrypted=True,
            publicly_accessible=False,
            backup_retention=Duration.days(1),
            deletion_protection=False,
            removal_policy=RemovalPolicy.SNAPSHOT,
            cloudwatch_logs_exports=["postgresql"],
            cloudwatch_logs_retention=logs.RetentionDays.ONE_WEEK,
        )

        token_agente = sm.Secret(
            self, "TokenAgente", description="Bearer do agente MCP e dos jobs para a API",
            generate_secret_string=sm.SecretStringGenerator(exclude_punctuation=True, password_length=48),
        )
        # chave da criptografia por campo (CPF): 64 caracteres alfanuméricos; o código deriva dela a chave
        chave_dados = sm.Secret(
            self, "ChaveDados", description="REGULAIA_CHAVE_DADOS: criptografia por campo do dado pessoal",
            generate_secret_string=sm.SecretStringGenerator(exclude_punctuation=True, password_length=64),
        )
        # senha das contas da demo no link público (a do arquivo da demo está no Git)
        senha_demo = sm.Secret(
            self, "SenhaDemo", description="REGULAIA_SENHA_DEMO: senha das contas ficticias da demo",
            generate_secret_string=sm.SecretStringGenerator(exclude_punctuation=True, password_length=20),
        )

        # ------------------------------------------------------------------ aplicação
        cluster = ecs.Cluster(self, "Cluster", vpc=vpc, container_insights_v2=ecs.ContainerInsights.ENABLED)
        if imagem is None and imagem_tag:
            repo = ecr.Repository.from_repository_name(self, "Imagens", "regulaia-api")
            imagem = ecs.ContainerImage.from_ecr_repository(repo, tag=imagem_tag)
        imagem = imagem or ecs.ContainerImage.from_asset(str(RAIZ), file="api/Dockerfile",
                                                         exclude=["infra/cdk.out", ".venv", ".git", "front/node_modules"])
        assert banco.secret is not None
        segredos = {
            "DB_USUARIO": ecs.Secret.from_secrets_manager(banco.secret, "username"),
            "DB_SENHA": ecs.Secret.from_secrets_manager(banco.secret, "password"),
            "DB_HOST": ecs.Secret.from_secrets_manager(banco.secret, "host"),
            "REGULAIA_TOKEN_SERVICO": ecs.Secret.from_secrets_manager(token_agente),
            "REGULAIA_CHAVE_DADOS": ecs.Secret.from_secrets_manager(chave_dados),
            "REGULAIA_SENHA_DEMO": ecs.Secret.from_secrets_manager(senha_demo),
        }
        https = certificado_arn is not None
        prefixo_cf = None if https else PREFIXO_CLOUDFRONT.get(self.region)   # CloudFront na frente do ALB
        ambiente = {
            "REGULAIA_ARMAZENAMENTO": f"s3://{documentos.bucket_name}/",
            "REGULAIA_COOKIE_SEGURO": "1" if https or prefixo_cf else "0",
            "REGULAIA_ORIGENS": "",
            "AWS_REGION": self.region,
            "REGULAIA_BEDROCK": "1" if ia else "",   # provedor Bedrock (modelos em regulaia/modelos.toml)
            "REGULAIA_TETO_DIA_USD": "10",            # link público: teto de gasto com IA por dia
        }
        # a URL do banco é montada aqui, com a senha que veio do Secrets Manager
        url = f"postgresql://$DB_USUARIO:$DB_SENHA@$DB_HOST:5432/{BANCO}"
        comando_api = ["sh", "-c", f'export REGULAIA_DATABASE_URL="{url}" && alembic upgrade head && '
                                   "exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --proxy-headers "
                                   "--forwarded-allow-ips='*' --workers 2"]
        comando_radar = ["sh", "-c", f'export REGULAIA_DATABASE_URL="{url}" && exec python -m api.jobs radar']
        comando_descoberta = ["sh", "-c", f'export REGULAIA_DATABASE_URL="{url}" && exec python -m api.jobs descoberta']

        logs_api = logs.LogGroup(self, "LogsApi", retention=logs.RetentionDays.ONE_MONTH,
                                 removal_policy=RemovalPolicy.DESTROY)
        servico = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "Api",
            cluster=cluster,
            cpu=512,
            memory_limit_mib=1024,
            desired_count=1,
            min_healthy_percent=100,      # com uma task, o deploy sobe a nova antes de derrubar a velha
            public_load_balancer=True,
            open_listener=prefixo_cf is None,     # com CloudFront, o ALB só aceita os IPs dele (abaixo)
            assign_public_ip=True,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            certificate=acm.Certificate.from_certificate_arn(self, "Certificado", certificado_arn) if https else None,
            redirect_http=https,
            protocol=elbv2.ApplicationProtocol.HTTPS if https else elbv2.ApplicationProtocol.HTTP,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            health_check_grace_period=Duration.seconds(120),
            runtime_platform=ecs.RuntimePlatform(cpu_architecture=ecs.CpuArchitecture.X86_64,
                                                 operating_system_family=ecs.OperatingSystemFamily.LINUX),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=imagem,
                container_port=8000,
                command=comando_api,
                environment=ambiente,
                secrets=segredos,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="api", log_group=logs_api),
            ),
        )
        servico.target_group.configure_health_check(path="/health", healthy_http_codes="200",
                                                    interval=Duration.seconds(30))
        escala = servico.service.auto_scale_task_count(min_capacity=1, max_capacity=4)
        escala.scale_on_cpu_utilization("Cpu", target_utilization_percent=60)
        sg_banco.add_ingress_rule(servico.service.connections.security_groups[0], ec2.Port.tcp(5432),
                                  "API no Postgres")

        # ------------------------------------------------------------------ HTTPS: CloudFront na frente do ALB
        cdn = None
        if prefixo_cf:
            servico.load_balancer.connections.allow_from(ec2.Peer.prefix_list(prefixo_cf), ec2.Port.tcp(80),
                                                         "Only CloudFront reaches the ALB")
            origem = origens_cf.LoadBalancerV2Origin(
                servico.load_balancer, protocol_policy=cf.OriginProtocolPolicy.HTTP_ONLY,
                read_timeout=Duration.seconds(60),     # análise com IA pode passar dos 30 s padrão
            )
            cdn = cf.Distribution(
                self, "Cdn", comment="RegulaIA: HTTPS na frente do ALB",
                price_class=cf.PriceClass.PRICE_CLASS_ALL,      # inclui os pontos de presença no Brasil
                http_version=cf.HttpVersion.HTTP2_AND_3,
                default_behavior=cf.BehaviorOptions(
                    origin=origem,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,               # API e páginas: nada em cache
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER,    # cookies, cabeçalhos, query
                ),
                additional_behaviors={"/_next/static/*": cf.BehaviorOptions(
                    origin=origem,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,              # nome com hash: cache longo
                    compress=True,
                )},
            )

        # ------------------------------------------------------------------ radar do DOU (job diário)
        tarefa_radar = ecs.FargateTaskDefinition(self, "TarefaRadar", cpu=512, memory_limit_mib=1024)
        tarefa_radar.add_container(
            "radar", image=imagem, command=comando_radar, environment=ambiente, secrets=segredos,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="radar", log_retention=logs.RetentionDays.ONE_MONTH),
        )
        # os dois jobs (radar e descoberta) usam o mesmo security group: só saída, e o Postgres os aceita
        sg_radar = ec2.SecurityGroup(self, "SgRadar", vpc=vpc, description="Jobs (radar, descoberta): egress only")
        sg_banco.add_ingress_rule(sg_radar, ec2.Port.tcp(5432), "Jobs no Postgres")
        events.Rule(
            self, "RadarDiario",
            description="Radar do DOU todo dia às 06:00 de Brasília",
            schedule=events.Schedule.cron(minute="0", hour="9"),
            targets=[targets.EcsTask(
                cluster=cluster, task_definition=tarefa_radar, subnet_selection=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PUBLIC), assign_public_ip=True, security_groups=[sg_radar],
            )],
        )

        # ------------------------------------------------------------------ descoberta de normas (job semanal)
        # lê dezenas de milhares de normas das fontes oficiais: mais memória que o radar
        tarefa_descoberta = ecs.FargateTaskDefinition(self, "TarefaDescoberta", cpu=1024, memory_limit_mib=2048)
        tarefa_descoberta.add_container(
            "descoberta", image=imagem, command=comando_descoberta, environment=ambiente, secrets=segredos,
            logging=ecs.LogDrivers.aws_logs(stream_prefix="descoberta", log_retention=logs.RetentionDays.ONE_MONTH),
        )
        events.Rule(
            self, "DescobertaSemanal",
            description="Descoberta de normas todo domingo às 03:00 de Brasília",
            schedule=events.Schedule.cron(minute="0", hour="6", week_day="SUN"),
            targets=[targets.EcsTask(
                cluster=cluster, task_definition=tarefa_descoberta, subnet_selection=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PUBLIC), assign_public_ip=True, security_groups=[sg_radar],
            )],
        )

        # ------------------------------------------------------------------ permissões (mínimas)
        for papel in (servico.task_definition.task_role, tarefa_radar.task_role, tarefa_descoberta.task_role):
            documentos.grant_read_write(papel)
            papel.add_to_principal_policy(iam.PolicyStatement(
                sid="IAViaBedrock",
                actions=["bedrock:InvokeModel", "bedrock:Converse"],
                # perfil de inferência us./global. manda a chamada para outra região: o modelo de base
                # tem de ser liberado em qualquer região, não só na da pilha
                resources=["arn:aws:bedrock:*::foundation-model/*",
                           f"arn:aws:bedrock:*:{self.account}:inference-profile/*"],
            ))
            papel.add_to_principal_policy(iam.PolicyStatement(
                sid="OcrViaTextract", actions=["textract:DetectDocumentText", "textract:AnalyzeDocument"],
                resources=["*"],     # o Textract não tem recurso por ARN nessas ações
            ))

        # ------------------------------------------------------------------ alarmes
        lb = servico.load_balancer.metrics
        cw.Alarm(self, "Erros5xx", metric=lb.http_code_elb(elbv2.HttpCodeElb.ELB_5XX_COUNT, period=Duration.minutes(5)),
                 threshold=5, evaluation_periods=1, alarm_description="API devolvendo 5xx",
                 treat_missing_data=cw.TreatMissingData.NOT_BREACHING)
        cw.Alarm(self, "SemTarefaSaudavel", metric=servico.target_group.metrics.healthy_host_count(
                     period=Duration.minutes(1)),
                 threshold=1, comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
                 evaluation_periods=3, alarm_description="Nenhuma task da API saudável atrás do ALB")
        cw.Alarm(self, "BancoCpu", metric=banco.metric_cpu_utilization(period=Duration.minutes(5)),
                 threshold=80, evaluation_periods=3, alarm_description="Postgres com CPU alta")

        if cdn is not None:
            CfnOutput(self, "Endereco", value=f"https://{cdn.distribution_domain_name}")
        else:
            CfnOutput(self, "Endereco", value=f"{'https' if https else 'http'}://{servico.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "BucketDocumentos", value=documentos.bucket_name)
        CfnOutput(self, "SegredoBanco", value=banco.secret.secret_name)
        CfnOutput(self, "SegredoSenhaDemo", value=senha_demo.secret_name)
        CfnOutput(self, "NomeCluster", value=cluster.cluster_name)
