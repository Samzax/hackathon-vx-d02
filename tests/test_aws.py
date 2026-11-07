"""Adaptadores da AWS testados sem a AWS: Bedrock (Converse) e S3 com clientes falsos.
No evento, o que muda é só configuração (.env e IDs em modelos.toml)."""

import tomllib

import pytest

from mitra import arquivos, ia


class ConverseFalso:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.pedidos = resposta, erro, []

    def converse(self, **kw):
        self.pedidos.append(kw)
        if self.erro:
            raise self.erro
        return self.resposta


RESPOSTA = {"output": {"message": {"role": "assistant", "content": [{"text": '{"mudancas": [], '},
                                                                     {"text": '"motivo": "nada"}'}]}},
            "usage": {"inputTokens": 1200, "outputTokens": 80, "totalTokens": 1280}, "stopReason": "end_turn"}


def _bedrock(cliente, relogio=None, dormir=None):
    cfg = tomllib.loads(ia.CONFIG.read_text(encoding="utf-8"))["provedores"]["bedrock"]
    return ia.ClienteBedrock("bedrock", cfg, cliente=cliente, relogio=relogio, dormir=dormir)


def test_converse_recebe_sistema_e_usuario_e_devolve_texto_e_tokens():
    falso = ConverseFalso(RESPOSTA)
    texto, tin, tout = _bedrock(falso).chamar(ia.Modelo("bedrock", "modelo-x"), "SISTEMA", "USUARIO", 4000, "s")
    assert (texto, tin, tout) == ('{"mudancas": [], "motivo": "nada"}', 1200, 80)
    p = falso.pedidos[0]
    assert p["modelId"] == "modelo-x" and p["system"] == [{"text": "SISTEMA"}]
    assert p["messages"] == [{"role": "user", "content": [{"text": "USUARIO"}]}]
    assert p["inferenceConfig"] == {"maxTokens": 4000}


def test_menos_de_uma_requisicao_por_segundo():
    agora, esperas = [100.0], []
    b = _bedrock(ConverseFalso(RESPOSTA), relogio=lambda: agora[0], dormir=lambda s: (esperas.append(s),
                                                                                  agora.__setitem__(0, agora[0] + s)))
    m = ia.Modelo("bedrock", "x")
    b.chamar(m, "s", "u", 10, "")
    agora[0] += 0.3
    b.chamar(m, "s", "u", 10, "")
    assert esperas == [pytest.approx(0.8)]          # 1,1 s de intervalo mínimo (regra do evento: < 1 req/s)
    agora[0] += 5
    b.chamar(m, "s", "u", 10, "")
    assert len(esperas) == 1


def test_roteador_usa_o_bedrock_e_passa_ao_proximo_se_ele_falhar():
    erro = ConverseFalso(erro=RuntimeError("AccessDeniedException"))

    class OutroFalso:
        def chamar(self, *a, **k):
            return '{"ok": true}', 10, 2

    rot = ia.Roteador(None, provedores={"bedrock": _bedrock(erro), "anthropic": OutroFalso()})
    rot.cfg["camadas"]["2"]["modelos"] = [{"provedor": "bedrock", "modelo": "x"},
                                          {"provedor": "anthropic", "modelo": "claude-haiku-5-5"}]
    r = rot.pedir_json("t", 2, "s", "u", "v1")
    assert r.dados == {"ok": True} and r.modelo.provedor == "anthropic"
    assert r.tentativas and r.tentativas[0].startswith("bedrock:x: FalhaProvedor: RuntimeError")


def test_bedrock_so_liga_com_a_variavel_e_sem_chave_aws_no_codigo(monkeypatch):
    pytest.importorskip("boto3")
    assert "bedrock" not in ia.Roteador(None, env={}).provedores
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    rot = ia.Roteador(None, env={"MITRA_BEDROCK": "1"})
    assert isinstance(rot.provedores["bedrock"], ia.ClienteBedrock)        # cria o cliente sem chamar a AWS
    cfg = tomllib.loads(ia.CONFIG.read_text(encoding="utf-8"))
    assert cfg["provedores"]["bedrock"]["regiao"] == "us-east-1"
    texto = ia.CONFIG.read_text(encoding="utf-8")
    assert "AKIA" not in texto and "aws_secret" not in texto.lower()


def test_evidencia_vai_para_pasta_local_sem_bucket(tmp_path, monkeypatch):
    monkeypatch.delenv("MITRA_S3_BUCKET", raising=False)
    monkeypatch.setattr(arquivos, "PASTA", tmp_path / "evidencias")
    onde = arquivos.guardar("C:\\fotos\\FIR B3 (1).pdf", b"%PDF-1.4 a")
    assert onde.endswith("/FIR_B3_1_.pdf")
    assert (tmp_path / "evidencias").rglob("FIR_B3_1_.pdf").__next__().read_bytes() == b"%PDF-1.4 a"
    assert arquivos.guardar("x.pdf", b"b") != arquivos.guardar("x.pdf", b"c")    # mesmo nome não sobrescreve


def test_evidencia_vai_para_o_s3_com_bucket(monkeypatch):
    class S3Falso:
        def __init__(self):
            self.objetos = []

        def put_object(self, **kw):
            self.objetos.append(kw)

    monkeypatch.setenv("MITRA_S3_BUCKET", "mitra-evidencias")
    s3 = S3Falso()
    onde = arquivos.guardar("FIR.pdf", b"%PDF", s3=s3)
    assert onde.startswith("s3://mitra-evidencias/evidencias/") and onde.endswith("/FIR.pdf")
    o = s3.objetos[0]
    assert o["Bucket"] == "mitra-evidencias" and o["Body"] == b"%PDF"
    assert o["ServerSideEncryption"] == "AES256" and "ACL" not in o              # nada de objeto público
