# Infra AWS (CDK em Python)

Uma pilha (`mitra_stack.py`) com tudo que a Mitra precisa em us-east-1:

| Peça | Serviço | Por quê |
|---|---|---|
| API + front | ECS Fargate atrás de um ALB, 1 a 4 tasks (escala por CPU), circuit breaker com rollback | Sem servidor para administrar; a mesma imagem do `docker compose` |
| Banco | RDS Postgres 16 (t4g.micro), subnet isolada, criptografado, backup diário | O mesmo esquema do Alembic; ninguém de fora alcança |
| Documentos | S3 privado, versionado, só TLS, criptografado | O PDF original de cada evidência, pelo SHA-256 |
| IA | Bedrock (Converse) | Análise de atos e leitura de evidências, sem chave de terceiro |
| OCR | Textract | PDF escaneado |
| Radar do DOU | EventBridge todo dia 06:00 BRT -> task Fargate | `python -m api.jobs radar`, mesma imagem |
| Segredos | Secrets Manager | Senha do banco (gerada pela AWS) e token do agente MCP |
| Observabilidade | CloudWatch Logs (JSON com request_id) + 3 alarmes | 5xx no ALB, nenhuma task saudável, CPU do banco |

**Custo:** sem NAT Gateway (o item caro de uma VPC). As tasks ficam em subnet pública com IP
próprio e só aceitam tráfego do ALB; o S3 vai pelo endpoint da VPC. Ordem de grandeza: alguns
dólares por dia (ALB, Fargate 0,5 vCPU, RDS micro), dentro do crédito do Free plan.

## Comandos

Duas pilhas: `RegulaIABuild` (ECR `regulaia-api` + CodeBuild: a imagem é construída na AWS, sem Docker
local) e `RegulaIA` (a aplicação Mitra — os ids das pilhas e do ECR mantêm o nome antigo porque já
estão deployados; renomear criaria um ambiente novo). A imagem sai do último commit (`git archive HEAD`) mais o
`api/Dockerfile` da pasta: rascunho não commitado de outra sessão nunca vai para a imagem.

```bash
uv sync --group infra
uv run --group infra pytest tests/test_infra.py      # confere as pilhas sem conta AWS
cd infra && npx aws-cdk@2 synth                       # gera o CloudFormation
cd infra && npx aws-cdk@2 bootstrap                   # uma vez por conta/região
cd infra && npx aws-cdk@2 deploy RegulaIABuild        # uma vez: ECR + CodeBuild
uv run --with "botocore[crt]" python infra/construir.py           # build na AWS; imprime TAG=...
cd infra && npx aws-cdk@2 deploy RegulaIA -c imagem_tag=<TAG>         # sem IA
cd infra && npx aws-cdk@2 deploy RegulaIA -c imagem_tag=<TAG> -c ia=1 # com o Bedrock
```

Na conta do evento: `AWS_PROFILE=vx` (`aws login --profile vx`) e `CDK_DEFAULT_ACCOUNT=777390839891`.
Segredos gerados pela AWS: senha do banco, token do agente, `MITRA_CHAVE_DADOS` (64 alfanuméricos; o
código deriva a chave Fernet) e `MITRA_SENHA_DEMO` (contas da demo no link público). Jobs: radar do
DOU todo dia 06:00 BRT; descoberta de normas domingo 03:00 BRT.

HTTPS sem domínio: o CloudFront fica na frente do ALB (`https://<id>.cloudfront.net`, certificado da AWS,
cookie `Secure`); o ALB só aceita os IPs do CloudFront e nada é cacheado além de `/_next/static/*`.
Com domínio próprio: `npx aws-cdk@2 deploy -c certificado=arn:aws:acm:...` (o ALB faz o HTTPS e o CloudFront sai).

## Deploy automático (GitHub Actions)

Cada push no `main` roda `.github/workflows/deploy.yml`: build da imagem no runner (mesma
`api/Dockerfile`), push no ECR `regulaia-api` com a tag do commit e `cdk deploy RegulaIA`. Sem
segredo no GitHub: o job assume a role `github-deploy` por OIDC, restrita a este repositório e ao
branch `main`. A role é criada uma vez, fora do CDK (o CDK não deve gerenciar quem faz o deploy dele):

```bash
aws iam create-open-id-connect-provider --profile vx \
  --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com
aws iam create-role --profile vx --role-name github-deploy \
  --assume-role-policy-document file://infra/github-deploy-confianca.json
aws iam put-role-policy --profile vx --role-name github-deploy \
  --policy-name deploy --policy-document file://infra/github-deploy-permissoes.json
```

Permissões mínimas (os dois JSON ao lado): push só no repositório `regulaia-api` e `sts:AssumeRole`
nas roles `cdk-*` do bootstrap — quem aplica o CloudFormation são as roles do CDK, como no deploy manual.

## Antes do deploy na conta do evento

- Em `mitra/modelos.toml`, os IDs do Bedrock são perfis de inferência `us.anthropic.*`. Modelo que a
  conta não libera é recusado uma vez e sai da fila sozinho (a API sonda o Bedrock ao subir e o log
  mostra `recusado pelo provedor`); não precisa reordenar nada.
- A conta do evento não pode receber dado pessoal: o repositório já leva só as linhas de empresa do
  SIGBM (sem CPF), e a imagem não leva `.env` nem `data/raw/`.
- O Bedrock tem de ficar abaixo de 1 requisição por segundo: `intervalo_minimo_s = 1.1` no provedor.
