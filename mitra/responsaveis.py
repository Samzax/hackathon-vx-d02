"""Responsáveis técnicos: quem responde tecnicamente por cada unidade ou ativo, e o dado pessoal.

Por unidade ou por ativo: responsável técnico, coordenador do PAEBM e afins, com nome, CPF, registro no
conselho, número da ART e vigência da ART. **ART vencendo vira obrigação** (`obrigacao_de_art`).

O CPF é o único dado pessoal da plataforma e segue as regras de `pessoal.py`:
- guardado **cifrado por campo**, com a chave em `MITRA_CHAVE_DADOS` (sem ela, guardar CPF dá erro
  claro: nada de chave padrão no código);
- lido **mascarado** por padrão (`cpf_mascarado`); ver o CPF inteiro é do Regulatório e da TI da própria
  empresa, por `ver_cpf`, e **cada visualização vai para a auditoria** (quem viu, de quem, quando) — a
  rota da API é que grava a trilha;
- nunca vai para a IA, nunca para o Git, nunca para a demo com CPF de pessoa de verdade (na demo,
  `ficticio=1`), nunca para a conta AWS do evento.

LGPD: `exportar` devolve o que a plataforma guarda de pessoa (com o CPF em claro, para o titular) e
`apagar` remove os responsáveis de uma empresa. As duas são da TI da própria empresa e auditadas.

Empreendedor pessoa física (as linhas do SIGBM com CPF, que ficam fora da base pública) entra como
cliente informando os próprios dados, com o **consentimento registrado**: quem consentiu, quando e
para quê (`consentimento`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from . import db, pessoal
from .instanciacao import RESPONSAVEIS, ErroInstanciacao, registrar

PAPEIS = {
    "responsavel_tecnico": "Responsável técnico",
    "coordenador_paebm": "Coordenador do PAEBM",
    "responsavel_ambiental": "Responsável ambiental",
    "responsavel_seguranca": "Responsável pela segurança do trabalho",
}


class ErroResponsavel(ValueError):
    pass


@dataclass
class Responsavel:
    id: int
    empresa_id: int
    papel: str
    papel_rotulo: str
    nome: str
    cpf_mascarado: str
    registro: str | None
    art_numero: str | None
    art_vigencia_ate: str | None
    unidade: str | None
    ativo_codigo: str | None
    ficticio: bool
    consentimento: dict | None
    criado_por: str
    criado_em: str


def _linha(r) -> Responsavel:
    d = dict(r)
    return Responsavel(
        id=d["id"], empresa_id=d["empresa_id"], papel=d["papel"],
        papel_rotulo=PAPEIS.get(d["papel"], d["papel"]), nome=d["nome"],
        cpf_mascarado=(f"***.{d['cpf_fim'][:3]}.{d['cpf_fim'][3:]}-**" if d.get("cpf_fim")
                       else "não informado"),
        registro=d["registro"], art_numero=d["art_numero"], art_vigencia_ate=d["art_vigencia_ate"],
        unidade=d["unidade"], ativo_codigo=d["ativo_codigo"], ficticio=bool(d["ficticio"]),
        consentimento=json.loads(d["consentimento"]) if d.get("consentimento") else None,
        criado_por=d["criado_por"], criado_em=d["criado_em"])


def registrar_responsavel(conn, empresa_id: int, *, papel: str, nome: str, por: str,
                          cpf: str | None = None, registro: str | None = None,
                          art_numero: str | None = None, art_vigencia_ate: str | None = None,
                          unidade: str | None = None, ativo_codigo: str | None = None,
                          consentimento: dict | None = None, ficticio: bool = False,
                          chave: str | None = None) -> int:
    """Grava o responsável. O CPF entra cifrado; sem `MITRA_CHAVE_DADOS`, levanta `pessoal.SemChave`
    (a API continua de pé, mas não guarda dado pessoal sem cifra)."""
    if papel not in PAPEIS:
        raise ErroResponsavel(f"papel desconhecido: {papel!r} (há: {', '.join(PAPEIS)})")
    nome = (nome or "").strip()
    if not nome:
        raise ErroResponsavel("informe o nome do responsável")
    if unidade and not conn.execute("SELECT 1 FROM unidade WHERE empresa_id = ? AND nome = ?",
                                    (empresa_id, unidade)).fetchone():
        raise ErroResponsavel(f"a empresa não tem a unidade {unidade!r}")
    if ativo_codigo and not db.ativo_por_codigo(conn, empresa_id, ativo_codigo):
        raise ErroResponsavel(f"a empresa não tem o ativo {ativo_codigo!r}")
    if not unidade and not ativo_codigo:
        raise ErroResponsavel("diga por qual unidade ou ativo esta pessoa responde")
    if art_vigencia_ate:
        try:
            date.fromisoformat(art_vigencia_ate)
        except ValueError:
            raise ErroResponsavel(f"vigência da ART: {art_vigencia_ate!r} não é data AAAA-MM-DD") from None
    cifrado = fim = None
    if cpf:
        cifrado = pessoal.cifrar(cpf, chave)          # confere os dígitos e exige a chave
        fim = pessoal.digitos(cpf)[3:9]               # o miolo, para a máscara (não identifica sozinho)
    with conn:
        cur = conn.execute(
            "INSERT INTO responsavel_tecnico (empresa_id, papel, nome, cpf_cifrado, cpf_fim, registro, "
            "art_numero, art_vigencia_ate, unidade, ativo_codigo, consentimento, ficticio, criado_por, "
            "criado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (empresa_id, papel, nome, cifrado, fim, registro, art_numero, art_vigencia_ate, unidade,
             ativo_codigo, json.dumps(consentimento, ensure_ascii=False) if consentimento else None,
             int(ficticio), por, db.agora()))
    registrar(conn, empresa_id, RESPONSAVEIS, f"{PAPEIS[papel]}: {nome}", por,
              {"unidade": unidade, "ativo": ativo_codigo, "art_vigencia_ate": art_vigencia_ate})
    return cur.lastrowid


def responsaveis(conn, empresa_id: int, unidades: list[str] | None = None) -> list[Responsavel]:
    """Os responsáveis da empresa, sempre com o CPF mascarado. `unidades`: o escopo de um gestor
    restrito (só os das unidades dele; o CPF continua mascarado para todos)."""
    rows = conn.execute("SELECT * FROM responsavel_tecnico WHERE empresa_id = ? ORDER BY unidade, nome",
                        (empresa_id,)).fetchall()
    out = [_linha(r) for r in rows]
    if unidades is not None:
        permitidas = set(unidades)
        out = [r for r in out if r.unidade in permitidas or r.ativo_codigo in permitidas]
    return out


def responsavel(conn, empresa_id: int, responsavel_id: int) -> Responsavel | None:
    """Um responsável da empresa. O de outra cliente não existe para esta."""
    r = conn.execute("SELECT * FROM responsavel_tecnico WHERE id = ? AND empresa_id = ?",
                     (responsavel_id, empresa_id)).fetchone()
    return _linha(r) if r else None


def ver_cpf(conn, empresa_id: int, responsavel_id: int, chave: str | None = None) -> str:
    """O CPF inteiro. Quem chama precisa gravar a visualização na auditoria: é dado pessoal, e a regra
    é que cada vez que alguém vê fica registrado (a rota da API faz isso)."""
    r = conn.execute("SELECT cpf_cifrado FROM responsavel_tecnico WHERE id = ? AND empresa_id = ?",
                     (responsavel_id, empresa_id)).fetchone()
    if r is None:
        raise ErroResponsavel(f"responsável {responsavel_id} não é desta empresa")
    if not r["cpf_cifrado"]:
        raise ErroResponsavel("este responsável não tem CPF informado")
    return pessoal.decifrar(r["cpf_cifrado"], chave)


def apagar(conn, empresa_id: int, responsavel_id: int, por: str) -> bool:
    r = responsavel(conn, empresa_id, responsavel_id)
    if r is None:
        return False
    with conn:
        conn.execute("DELETE FROM responsavel_tecnico WHERE id = ? AND empresa_id = ?",
                     (responsavel_id, empresa_id))
    registrar(conn, empresa_id, RESPONSAVEIS, f"responsável {r.nome} removido", por, {"id": responsavel_id})
    return True


# ------------------------------------------------------------------ a ART vencendo


def obrigacao_de_art(conn, empresa_id: int, responsavel_id: int, por: str,
                     dias_antes: int = 30) -> str | None:
    """A vigência da ART vira obrigação: renovar a ART antes de vencer. Sem vigência no cadastro, não há
    o que cobrar (nada é presumido)."""
    from .licencas import _proximo_codigo, _responsavel_padrao

    r = responsavel(conn, empresa_id, responsavel_id)
    if r is None:
        raise ErroResponsavel(f"responsável {responsavel_id} não é desta empresa")
    if not r.art_vigencia_ate:
        return None
    empresa = conn.execute("SELECT nome FROM empresa WHERE id = ?", (empresa_id,)).fetchone()["nome"]
    norma = f"ART {r.art_numero or r.registro or r.nome}"
    if conn.execute("SELECT 1 FROM obrigacao WHERE empresa = ? AND norma = ?",
                    (empresa, norma)).fetchone():
        return None                 # já criada: chamar de novo não duplica
    vence = date.fromisoformat(r.art_vigencia_ate)
    pedir_ate = date.fromordinal(vence.toordinal() - dias_antes)
    alvo = r.ativo_codigo or r.unidade
    tipo_ativo = "unidade"
    if r.ativo_codigo:
        a = db.ativo_por_codigo(conn, empresa_id, r.ativo_codigo)
        tipo_ativo = a["tipo"] if a else "unidade"
    codigo = _proximo_codigo(conn, empresa_id, empresa, "ART")
    with conn:
        ob = conn.execute("INSERT INTO obrigacao (codigo, tipo_ativo, norma, area, empresa) "
                          "VALUES (?, ?, ?, 'documentacao', ?)",
                          (codigo, tipo_ativo, norma, empresa)).lastrowid
        conn.execute(
            "INSERT INTO obrigacao_versao (obrigacao_id, versao, titulo, artigo, aplica_se_a, regra, "
            "periodicidade, agenda, prazo, vigencia_desde, vigencia_ate, responsavel, evidencia, fonte, "
            "status, decidida_por, decidida_em) "
            "VALUES (?, 1, ?, 'vigência da ART', ?, '*', 'Evento único', ?, ?, NULL, ?, ?, ?, ?, "
            "'vigente', ?, ?)",
            (ob, f"Renovar a ART de {r.nome} ({r.papel_rotulo})", f"o responsável por {alvo}",
             f"data:{pedir_ate.isoformat()}",
             f"Até {pedir_ate:%d/%m/%Y} ({dias_antes} dias antes de a ART vencer, em {vence:%d/%m/%Y})",
             r.art_vigencia_ate, _responsavel_padrao(conn, empresa_id, "documentacao"),
             "ART nova registrada no conselho", norma, por, db.agora()))
    registrar(conn, empresa_id, RESPONSAVEIS, f"ART de {r.nome} ({codigo})", por,
              {"vence": r.art_vigencia_ate, "pedir_ate": pedir_ate.isoformat()})
    return codigo


# ------------------------------------------------------------------ LGPD


def exportar(conn, empresa_id: int, chave: str | None = None) -> list[dict]:
    """O que a plataforma guarda de pessoa, para o titular (rota da TI da empresa, auditada).
    Aqui o CPF vai **em claro**: é o direito de acesso do titular, não uma listagem de tela."""
    out = []
    for r in conn.execute("SELECT * FROM responsavel_tecnico WHERE empresa_id = ? ORDER BY id",
                          (empresa_id,)):
        d = dict(r)
        cpf = None
        if d["cpf_cifrado"]:
            try:
                cpf = pessoal.decifrar(d["cpf_cifrado"], chave)
            except pessoal.SemChave:
                cpf = "(cifrado: a chave MITRA_CHAVE_DADOS não está nesta instalação)"
        out.append({"id": d["id"], "papel": PAPEIS.get(d["papel"], d["papel"]), "nome": d["nome"],
                    "cpf": cpf, "registro": d["registro"], "art_numero": d["art_numero"],
                    "art_vigencia_ate": d["art_vigencia_ate"], "unidade": d["unidade"],
                    "ativo": d["ativo_codigo"], "ficticio": bool(d["ficticio"]),
                    "consentimento": json.loads(d["consentimento"]) if d["consentimento"] else None,
                    "guardado_por": d["criado_por"], "guardado_em": d["criado_em"]})
    return out


def apagar_dados_pessoais(conn, empresa_id: int, por: str) -> int:
    """Apaga os dados pessoais da empresa (todos os responsáveis técnicos). As obrigações criadas a
    partir das ARTs ficam: são da empresa, não da pessoa — mas perdem o nome no título."""
    n = conn.execute("SELECT COUNT(*) FROM responsavel_tecnico WHERE empresa_id = ?",
                     (empresa_id,)).fetchone()[0]
    with conn:
        conn.execute("DELETE FROM responsavel_tecnico WHERE empresa_id = ?", (empresa_id,))
    registrar(conn, empresa_id, RESPONSAVEIS, "dados pessoais apagados (LGPD)", por, {"removidos": n})
    return n


def consentimento_de(quem: str, para_que: str, empresa: str | None = None) -> dict:
    """O consentimento registrado do empreendedor pessoa física: quem, quando e para quê."""
    if not (quem or "").strip() or not (para_que or "").strip():
        raise ErroInstanciacao("o consentimento precisa dizer quem consentiu e para quê")
    return {"quem": quem.strip(), "para_que": para_que.strip(), "em": db.agora(), "empresa": empresa}
