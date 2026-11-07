"""Build da imagem na AWS, sem Docker local: zipa o código, sobe no S3 e roda o CodeBuild.

    uv run --with "botocore[crt]" python infra/construir.py [tag] [--sobrepor caminho,caminho]

(`botocore[crt]`: o boto3 só lê a credencial do `aws login` com ele; fica fora do pyproject de propósito.)

O zip sai do último commit (`git archive HEAD`), não da pasta: várias sessões mexem na mesma cópia, e
rascunho não commitado (migração pela metade, por exemplo) não pode ir para a imagem, que roda
`alembic upgrade head` no start. `--sobrepor` põe por cima, da pasta, só os arquivos listados
(padrão: api/Dockerfile). O zip respeita o .dockerignore (nada de .env, data/raw/).
A tag padrão é o commit (mais "-mod" se algo foi sobreposto e a hora). Precisa da pilha RegulaIABuild.
Imprime a tag no fim, para o `cdk deploy RegulaIA -c imagem_tag=<tag>`.
"""

from __future__ import annotations

import fnmatch
import io
import subprocess
import sys
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from regulaia.aws import cliente  # noqa: E402

PILHA = "RegulaIABuild"
FONTE = "fonte.zip"


def _ignorados() -> list[str]:
    linhas = (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return [l.strip().rstrip("/") for l in linhas if l.strip() and not l.startswith("#") and not l.startswith("!")]


def _ignorado(rel: str, padroes: list[str]) -> bool:
    partes = rel.split("/")
    for p in padroes:
        if "/" in p:        # caminho a partir da raiz (data/raw, front/out...)
            if rel == p or rel.startswith(p + "/") or fnmatch.fnmatch(rel, p):
                return True
        elif any(fnmatch.fnmatch(parte, p) for parte in partes):   # nome em qualquer nível
            return True
    return False


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, check=True).stdout


def zipar(sobrepor: list[str]) -> bytes:
    """Arquivos do HEAD (git archive) mais os de `sobrepor`, lidos da pasta."""
    padroes = _ignorados() + ["infra/cdk.out", "node_modules"]
    commitado = zipfile.ZipFile(io.BytesIO(_git("archive", "--format=zip", "HEAD")))
    buf = io.BytesIO()
    n = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in commitado.infolist():
            if info.is_dir() or info.filename in sobrepor or _ignorado(info.filename, padroes):
                continue
            z.writestr(info.filename, commitado.read(info))
            n += 1
        for rel in sobrepor:
            z.write(RAIZ / rel, rel)
            n += 1
    print(f"zip: {n} arquivos do HEAD {_git('rev-parse', '--short', 'HEAD').decode().strip()}"
          f" + sobrepostos {sobrepor}, {buf.tell() / 1e6:.1f} MB")
    return buf.getvalue()


def tag_padrao(sobrepor: list[str]) -> str:
    commit = _git("rev-parse", "--short", "HEAD").decode().strip()
    mudou = any(_git("diff", "--name-only", "HEAD", "--", p).strip() for p in sobrepor)
    return commit + ("-mod" if mudou else "") + "-" + time.strftime("%H%M%S")


def saidas() -> dict[str, str]:
    pilha = cliente("cloudformation").describe_stacks(StackName=PILHA)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in pilha.get("Outputs", [])}


def main(argv: list[str]) -> int:
    sobrepor = ["api/Dockerfile"]
    if "--sobrepor" in argv:
        i = argv.index("--sobrepor")
        sobrepor = [p for p in argv[i + 1].split(",") if p]
        argv = argv[:i] + argv[i + 2:]
    tag = argv[0] if argv else tag_padrao(sobrepor)
    out = saidas()
    cliente("s3").put_object(Bucket=out["BucketFonte"], Key=FONTE, Body=zipar(sobrepor))
    cb = cliente("codebuild")
    build = cb.start_build(projectName=out["ProjetoBuild"], environmentVariablesOverride=[
        {"name": "TAG", "value": tag, "type": "PLAINTEXT"}])["build"]
    print(f"build {build['id']} (tag {tag})")
    fase = ""
    while True:
        b = cb.batch_get_builds(ids=[build["id"]])["builds"][0]
        if b["currentPhase"] != fase:
            fase = b["currentPhase"]
            print(f"  {time.strftime('%H:%M:%S')} {fase}")
        if b["buildStatus"] != "IN_PROGRESS":
            break
        time.sleep(10)
    if b["buildStatus"] != "SUCCEEDED":
        logs = b.get("logs", {})
        print(f"build {b['buildStatus']}: logs em {logs.get('groupName')} / {logs.get('streamName')}")
        return 1
    print(f"imagem: {out['Repositorio']}:{tag}")
    print(f"TAG={tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
