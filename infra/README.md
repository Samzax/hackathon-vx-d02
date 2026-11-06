# Infra AWS (CDK em Python)

Uma pilha (`regulaia_stack.py`) com tudo que a RegulaIA precisa em us-east-1:

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

```bash
uv sync --group infra
uv run --group infra pytest tests/test_infra.py      # confere a pilha sem conta AWS
cd infra && npx aws-cdk@2 synth                       # gera o CloudFormation
cd infra && npx aws-cdk@2 bootstrap                   # uma vez por conta/região
cd infra && npx aws-cdk@2 deploy                      # sobe tudo; imprime o endereço
```

Com domínio próprio, HTTPS e cookie `Secure`: `npx aws-cdk@2 deploy -c certificado=arn:aws:acm:...`.

## Antes do deploy na conta do evento

- Em `regulaia/modelos.toml`, trocar `ID_DO_HAIKU_4_5_NO_BEDROCK` e `ID_DO_SONNET_5_NO_BEDROCK` pelos
  IDs (ou perfis de inferência) que o console do Bedrock mostrar, e pôr o Bedrock no topo de cada camada.
- A conta do evento não pode receber dado pessoal: o repositório já leva só as linhas de empresa do
  SIGBM (sem CPF), e a imagem não leva `.env` nem `data/raw/`.
- O Bedrock tem de ficar abaixo de 1 requisição por segundo: `intervalo_minimo_s = 1.1` no provedor.
