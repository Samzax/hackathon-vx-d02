"""Leitor de evidências: um documento enviado pela operação vira a comprovação de um período.

  PDF -> texto -> (regra) qual ativo, qual documento, qual data -> obrigação e período
                 se a regra não fecha tudo, a IA tenta; o Python confere o que a IA disse
                 contra o texto (a data tem de estar no documento, o ativo tem de existir).

Além de dar baixa na obrigação, a leitura procura gatilhos de Inspeção de Segurança
Especial (ISE), pela norma que vale no dia para aquela barragem:
  Res. ANM 95/2022, art. 27  -> anomalia com pontuação 10
  Res. ANM 220/2025, art. 42 -> anomalia com EC1, EC3, EC4 ou EC5 = 5 (EC2 não dispara)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import agenda, db
from .triagem import datas, normalizar

VERSAO_PROMPT = "evidencia-v1"

# palavra-chave no documento -> palavra-chave no título da obrigação.
# Vale o nome que aparece primeiro no documento (o título): um RCO cita a DCO, mas começa por "Relatório".
DOCUMENTOS = {
    "ficha de inspecao regular": ("FIR", "fir"),
    "extrato de inspecao regular": ("EIR", "eir"),
    "relatorio de inspecao de seguranca regular": ("RISR", "risr"),
    "declaracao de condicao de estabilidade": ("DCE", "dce"),
    "revisao periodica de seguranca": ("RPSB", "rpsb"),
    "declaracao de conformidade e operacionalidade": ("DCO", "dco"),
    "exercicio simulado": ("Simulado", "simulad"),
    "relatorio de inspecao de seguranca do vaso": ("Inspeção NR-13", "exame externo"),
    "boletim de analise de efluentes": ("Efluentes", "efluentes"),
    "relatorio de conformidade e operacionalidade": ("RCO", "rco"),
    "relatorio conclusivo de inspecao especial": ("RCIE", "ise"),
    "extrato de inspecao especial": ("EIE (registro no SIGBM)", "reportar no sigbm"),
    "relatorio de inspecao de seguranca especial": ("ISE", "ise"),
    "processo de gestao de riscos": ("PGRBM", "pgrbm"),
    "treinamento interno do paebm": ("Treinamento do PAEBM", "treinamento"),
    "treinamento da brigada": ("Treinamento da brigada (NR-22)", "brigadas"),
    "simulacao do plano de emergencia": ("Simulação do plano de emergência (NR-22)", "simulacoes"),
    "seminario orientativo": ("Seminário Orientativo", "seminario"),
    "qualidade das aguas": ("Monitoramento de águas", "qualidade das aguas"),
    "ruido e vibracao": ("Ruído e vibração", "ruido"),
    "recuperacao de areas degradadas": ("PRAD", "prad"),
    "cumprimento das condicionantes": ("Relatório de condicionantes", "cumprimento das condicionantes"),
    "plano de seguranca do paciente": ("Plano de Segurança do Paciente", "plano de seguranca do paciente"),
    "plano de gerenciamento de residuos": ("PGRSS", "plano de gerenciamento de residuos"),
    "capacitacao em riscos biologicos": ("Capacitação em riscos biológicos", "capacitacao trabalhadores expostos"),
    # obra (NR-18 e NR-35, fase B de 7/11/2026)
    "programa de gerenciamento de riscos": ("PGR da obra", "pgr"),
    "treinamento para trabalho em altura": ("Treinamento NR-35", "trabalho em altura"),
    "inspecao periodica do spiq": ("Inspeção do SPIQ", "spiq"),
    "liberacao de uso do andaime": ("Liberação de andaime", "andaime"),
    "comunicacao de acidente de trabalho": ("CAT", "acidente fatal"),
    "termo de embargo": ("Termo de embargo ou interdição", "embargo"),
    "termo de interdicao": ("Termo de embargo ou interdição", "embargo"),
}

# Gatilho -> o termo que acha a obrigação-alvo no título (o mesmo do mapa [eventos] do temas.toml) e a
# norma que o cria. tests/test_eventos_cobertos.py confere os dois lados: gatilho sem obrigação no
# cadastro é teste vermelho, não uma descoberta silenciosa no meio da implementação (o caso NR-3).
GATILHOS = {
    "acidente_fatal": {"obrigacao": "isolar", "norma": "NR-18, 18.16.23"},
    "incidente_ou_anomalia": {"obrigacao": "ise", "norma": "Res. ANM 95/2022 art. 27; Res. ANM 220/2025 art. 42"},
    "registro_no_sigbm": {"obrigacao": "reportar no sigbm", "norma": "Res. ANM 220/2025 art. 38 §4"},
    "embargo_ou_interdicao": {"obrigacao": "embargo", "norma": "NR-3, 3.5.4 e 3.5.5"},
}

SISTEMA = """Você lê documentos de conformidade de uma mineradora (fichas de inspeção, relatórios,
laudos, boletins). Responda só com JSON:
{"ativo": "código do ativo da lista ou null", "documento": "tipo do documento em poucas palavras",
 "data": "AAAA-MM-DD da execução ou inspeção, ou null", "pontuacao_maxima": número ou null}
Use só o que está escrito no documento; se não estiver, use null."""


@dataclass
class Leitura:
    ativo: str | None = None
    empresa_id: int | None = None         # o código do ativo só é único dentro da empresa
    documento: str | None = None
    obrigacao: str | None = None
    apenas_aciona: bool = False           # o documento registra um EVENTO (termo de embargo): abre
                                          # obrigações por gatilho e não dá baixa em nada
    data: str | None = None
    periodo: str | None = None
    pontuacao_maxima: int | None = None
    estado_conservacao: dict[str, int] = field(default_factory=dict)   # {"EC1": 0, "EC3": 5, ...}
    metodo: str = "regra"                 # regra | ia
    problemas: list[str] = field(default_factory=list)     # impedem o registro
    avisos: list[str] = field(default_factory=list)        # não impedem (ex.: entregue com atraso)
    gatilhos: list[str] = field(default_factory=list)
    acionar: list[str] = field(default_factory=list)      # obrigações por evento que o registro abre (ex.: ISE)

    @property
    def completa(self) -> bool:
        if self.apenas_aciona:
            return bool(self.ativo and self.data) and not self.problemas
        return bool(self.ativo and self.obrigacao and self.periodo) and not self.problemas


def texto_pdf(caminho_ou_bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    fonte = BytesIO(caminho_ou_bytes) if isinstance(caminho_ou_bytes, (bytes, bytearray)) else str(caminho_ou_bytes)
    return "\n".join((p.extract_text() or "") for p in PdfReader(fonte).pages)


def por_que_nao_abre(erro: Exception) -> str:
    """O que dizer ao operador quando o arquivo não abre como PDF (sem nome de exceção na tela)."""
    if type(erro).__name__ in ("FileNotDecryptedError", "WrongPasswordError"):
        return "o PDF está protegido por senha: mande uma cópia sem senha"
    return "o arquivo não parece um PDF válido (corrompido ou com outra extensão)"


# tipo no começo do nome, que o documento costuma omitir ("Córrego Fundo" em vez de "Barragem Córrego Fundo")
_TIPO_NO_NOME = re.compile(r"^(?:barragem|vaso|reservatorio|complexo|unidade)\s+")
# código sem parênteses só vale depois de um rótulo: "B3" solto pode ser outra coisa
_ROTULO_DE_CODIGO = r"(?:ativo|barragem|estrutura|equipamento|codigo(?: d[oa] (?:ativo|barragem|equipamento))?)\s*:?\s*"


def _nomes_do_ativo(a: dict) -> list[str]:
    """Como um documento pode chamar o ativo: o nome inteiro, o nome sem o tipo (se sobrar mais de uma
    palavra) e a tag do equipamento ("VP-101"), já normalizados."""
    nome = normalizar(a["nome"])
    nomes = [nome]
    curto = _TIPO_NO_NOME.sub("", nome)
    if curto != nome and len(curto.split()) >= 2:
        nomes.append(curto)
    if tag := re.match(r"[a-z]{1,4}-\d{2,5}\b", nome):
        nomes.append(tag.group(0))
    return nomes


def _ativos_citados(texto_n: str, ativos: list[dict]) -> list[str]:
    """Código explícito ("(B3)" ou "Ativo: B3") vale mais que nome; nome só inteiro ("Serra I" não casa
    "Serra II"), aceito também sem o tipo ("Córrego Fundo") e pela tag do equipamento ("VP-101")."""
    por_codigo = [a["codigo"] for a in ativos
                  if re.search(rf"\(\s*{re.escape(a['codigo'].lower())}\s*\)", texto_n)
                  or re.search(rf"{_ROTULO_DE_CODIGO}{re.escape(a['codigo'].lower())}(?!\w)", texto_n)]
    if por_codigo:
        return por_codigo
    return [a["codigo"] for a in ativos
            if any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", texto_n) for n in _nomes_do_ativo(a))]


def _por_que_sem_ativo(texto_n: str, citados: list[str], ativos: list[dict]) -> str:
    """Diz o motivo, para quem mandou o documento saber o que corrigir."""
    if len(citados) > 1:
        return f"o documento cita mais de um ativo ({', '.join(citados)}): não dá para saber de qual é"
    cadastrados = sorted(a["codigo"] for a in ativos)
    codigo = r"([a-z]{1,2}\d{1,3})(?!\w)"
    vistos = re.findall(rf"\(\s*{codigo}\s*\)", texto_n) + re.findall(rf"{_ROTULO_DE_CODIGO}{codigo}", texto_n)
    estranhos = sorted({m.upper() for m in vistos} - set(cadastrados))
    if estranhos:
        return (f"o documento cita {', '.join(estranhos)}, que não é ativo cadastrado da empresa "
                f"(cadastrados: {', '.join(cadastrados)})")
    return ("não foi possível identificar o ativo: o documento não cita o código, ex.: (B3) ou \"Ativo: B3\", "
            "nem o nome")


# uma data escrita de qualquer jeito que triagem.datas entende: 03/11/2026, 3.11.2026, 3 de novembro de 2026
_UMA_DATA = r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{1,2}º? de [a-zç]+ de \d{4})"


def _data_rotulada(texto: str, rotulos: str) -> date | None:
    """A data logo depois de um rótulo ("Data da inspeção:", "realizada em")."""
    m = re.search(rf"(?:{rotulos})\s*:?\s*{_UMA_DATA}", texto, re.I)
    achadas = datas(m.group(1)) if m else set()
    return next(iter(achadas)) if len(achadas) == 1 else None


def _data(texto: str) -> date | None:
    rotulada = _data_rotulada(
        texto, r"data d[ae] (?:inspe[cç][aã]o|execu[cç][aã]o|realiza[cç][aã]o|coleta)"
               r"|(?:realizad[ao]|executad[ao]|inspecionad[ao]|feit[ao])\s+em")
    if rotulada:
        return rotulada
    ds = sorted(datas(texto))
    return ds[0] if len(ds) == 1 else None


def _atraso(le: "Leitura", texto: str, agenda_ob: str, execucao: date) -> None:
    """Se o documento diz quando foi enviado/protocolado, compara com o prazo do período."""
    envio = _data_rotulada(texto, r"data d[eo] (?:envio|protocolo|entrega)")
    if not envio:
        return
    try:
        prazo = agenda.periodos(agenda_ob, execucao, execucao)[0].vence
    except agenda.AgendaInvalida:
        return          # agenda sem calendário fixo (anos:N, evento...): não há prazo de envio
    if envio > prazo:
        le.avisos.append(f"enviado em {envio:%d/%m/%Y}, {(envio - prazo).days} dias depois do prazo "
                         f"({prazo:%d/%m/%Y}): o período fica comprovado, mas a entrega foi fora do prazo")


def _pontuacao(texto_n: str) -> int | None:
    """'Pontuação máxima: 10', 'Pontuação máxima obtida = 10', 'Maior pontuação: 10'. Sem o 'máxima'/'maior'
    não lê: 'pontuação 6' pode ser a de uma anomalia qualquer."""
    m = re.search(r"(?:pontuacao maxima|maior pontuacao)[^0-9]{0,40}(\d{1,2})", texto_n)
    return int(m.group(1)) if m else None


def _estado_conservacao(texto_n: str) -> dict[str, int]:
    """Colunas de Estado de Conservação do Quadro I.8 (Res. 220): 'EC3 = 5', 'EC 3: 5', 'EC-3 (5)'.
    Errar para menos aqui é perder uma ISE obrigatória, então aceita os jeitos comuns de escrever."""
    return {f"EC{c}": int(v) for c, v in
            re.findall(r"\bec\s?-?\s?([1-5])\s*(?:[=:]\s*|\(\s*)(\d{1,2})\b", texto_n)}


_EC_ISE = ("EC1", "EC3", "EC4", "EC5")      # Res. 220, art. 42: EC2 = 5 não obriga ISE


def _gatilhos(conn, le: Leitura, ativos: list[dict], hoje: date, texto_n: str = "") -> None:
    """A regra de ISE é a da norma que vale hoje para o ativo (a obrigação de ISE vigente diz qual).
    Em obra, a CAT de acidente fatal abre o isolamento do local (NR-18, 18.16.23) e o termo de embargo
    ou interdição abre as obrigações da NR-3 (salários durante a paralisação e segurança na correção).
    Os termos de busca ficam em GATILHOS, conferidos contra o cadastro por teste."""
    if le.ativo and le.documento == "Termo de embargo ou interdição":
        aid = next(a["id"] for a in ativos if a["codigo"] == le.ativo)
        abertas = _obrigacoes(conn, aid, GATILHOS["embargo_ou_interdicao"]["obrigacao"], hoje.isoformat())
        if abertas:
            le.acionar += [o["codigo"] for o in abertas]
            le.gatilhos.append("Embargo ou interdição: manter os salários durante a paralisação e garantir "
                               "a segurança nas atividades de correção (NR-3, 3.5.4 e 3.5.5)")
        return
    if le.ativo and le.documento == "CAT" and re.search(r"\bfatal|\bobito|\bfalecimento", texto_n):
        aid = next(a["id"] for a in ativos if a["codigo"] == le.ativo)
        isolar = _obrigacao(conn, aid, GATILHOS["acidente_fatal"]["obrigacao"], hoje.isoformat())
        if isolar:
            le.acionar.append(isolar["codigo"])
            le.gatilhos.append("Acidente fatal: comunicar por escrito ao órgão regional e isolar o local "
                               "até a liberação (NR-18, 18.16.23)")
        return
    ise = None
    if le.ativo:
        aid = next(a["id"] for a in ativos if a["codigo"] == le.ativo)
        ise = _obrigacao(conn, aid, GATILHOS["incidente_ou_anomalia"]["obrigacao"], hoje.isoformat())
    if ise and "220/2025" in f"{ise.get('fonte')} {ise.get('artigo')}":
        cinco = [c for c in _EC_ISE if le.estado_conservacao.get(c) == 5]
        if cinco:
            # art. 38 §4: registro no SIGBM em 24 h; art. 42: a ISE. São duas obrigações, as duas abrem.
            sigbm = _obrigacao(conn, aid, GATILHOS["registro_no_sigbm"]["obrigacao"], hoje.isoformat())
            le.acionar += [o["codigo"] for o in (sigbm, ise) if o]
            le.gatilhos.append(f"Anomalia com {', '.join(c + ' = 5' for c in cinco)}: Inspeção de Segurança "
                               "Especial obrigatória (Res. ANM 220/2025, art. 42) e registro no SIGBM em até "
                               "24 horas (art. 38 §4)")
        elif le.documento == "FIR" and not le.estado_conservacao:
            le.avisos.append("a FIR não traz as colunas de Estado de Conservação (EC1 a EC5) do Quadro I.8, "
                             "obrigatórias pela Res. ANM 220/2025 (art. 38 §2): não dá para saber se há ISE")
        return
    if le.pontuacao_maxima is not None and le.pontuacao_maxima >= 10:
        if ise:
            le.acionar.append(ise["codigo"])
        le.gatilhos.append("Anomalia com pontuação 10: Inspeção de Segurança Especial obrigatória "
                           "(Res. ANM 95/2022, art. 27) e registro no SIGBM em até 24 horas (art. 21)")


def _obrigacoes(conn, ativo_id: int, chave: str, hoje: str) -> list[dict]:
    """Todas as obrigações vigentes do ativo cujo título casa o termo (um gatilho pode abrir mais de
    uma: no embargo, salários E segurança na correção)."""
    out = []
    for o in db.obrigacoes_do_ativo(conn, ativo_id, em=hoje):
        if o.dados_faltando or not db.vale_em(o.vigente, hoje):
            continue
        if re.search(rf"\b{chave}", normalizar(o.vigente["titulo"])):
            out.append(o.vigente)
    return out


def _obrigacao(conn, ativo_id: int, chave: str, hoje: str) -> dict | None:
    achadas = _obrigacoes(conn, ativo_id, chave, hoje)
    return achadas[0] if achadas else None


def ler(conn, texto: str, empresa_id: int, hoje: date, roteador=None) -> Leitura:
    ativos = db.ativos(conn, empresa_id)
    tn = normalizar(texto)
    le = Leitura(empresa_id=empresa_id)
    if len(tn.split()) < 5:
        le.problemas.append("o PDF não tem texto (parece escaneado): ainda não fazemos OCR")
        return le
    achados = sorted((tn.find(k), nome, chave) for k, (nome, chave) in DOCUMENTOS.items() if k in tn)
    tipo = achados[0][1:] if achados else None
    if tipo and tipo[1] == "exame externo" and re.search(r"tipo de exame\s*:?\s*interno|exame interno", tn) \
            and "exame externo" not in tn:
        tipo = ("Inspeção NR-13 (exame interno)", "exame interno")
    citados = _ativos_citados(tn, ativos)
    if len(citados) > 1 and tipo:
        # desempate: o ativo que tem obrigação vigente desse tipo de documento
        ids = {a["codigo"]: a["id"] for a in ativos}
        citados = [c for c in citados if _obrigacao(conn, ids[c], tipo[1], hoje.isoformat())]
    le.ativo = citados[0] if len(citados) == 1 else None
    d = _data(texto)
    le.pontuacao_maxima = _pontuacao(tn)
    le.estado_conservacao = _estado_conservacao(tn)

    if (le.ativo is None or tipo is None or d is None) and roteador is not None:
        lista = ", ".join(f"{a['codigo']} = {a['nome']}" for a in ativos)
        try:
            r = roteador.pedir_json("evidencia", 2, SISTEMA, f"ATIVOS: {lista}\n\nDOCUMENTO:\n{texto[:12000]}",
                                    VERSAO_PROMPT, max_tokens=800)
            le.metodo = "ia"
            ia = r.dados
            if le.ativo is None and ia.get("ativo") in {a["codigo"] for a in ativos}:
                le.ativo = ia["ativo"]
                # o documento não diz qual é o ativo com todas as letras: quem registra precisa saber que foi dedução
                le.avisos.append(f"o ativo {le.ativo} foi deduzido pela leitura automática, porque o documento não cita o código "
                                 "nem o nome inteiro de um ativo só: confira antes de registrar")
            if d is None and ia.get("data"):
                try:
                    proposta = date.fromisoformat(str(ia["data"]))
                    if proposta in datas(texto):        # a IA não inventa data: tem de estar no texto
                        d = proposta
                    else:
                        le.problemas.append(f"a data {proposta:%d/%m/%Y} indicada pela leitura automática não está no documento")
                except ValueError:
                    pass
            if tipo is None and ia.get("documento"):
                doc = normalizar(str(ia["documento"]))
                tipo = next(((n, c) for k, (n, c) in DOCUMENTOS.items() if c in doc or k in doc), None)
            if le.pontuacao_maxima is None and isinstance(ia.get("pontuacao_maxima"), int):
                le.pontuacao_maxima = ia["pontuacao_maxima"]
        except Exception as e:  # sem IA: segue com o que a regra achou
            le.problemas.append(f"IA indisponível: {str(e)[:80]}")

    if le.ativo is None:
        le.problemas.append(_por_que_sem_ativo(tn, citados, ativos))
    if tipo is None:
        le.problemas.append("tipo de documento não reconhecido")
    if d is None:
        le.problemas.append("data de execução não encontrada")
    if le.ativo and tipo:
        le.documento = tipo[0]
        aid = next(a["id"] for a in ativos if a["codigo"] == le.ativo)
        if tipo[0] == "Termo de embargo ou interdição":
            # o termo documenta o evento: não comprova obrigação nenhuma, só abre as da NR-3 (gatilho)
            le.apenas_aciona = True
            if d:
                le.data = d.isoformat()
                if d > hoje:
                    le.problemas.append("data de execução no futuro")
        elif (ob := _obrigacao(conn, aid, tipo[1], hoje.isoformat())) is None:
            le.problemas.append(f"{le.ativo} não tem obrigação vigente de {tipo[0]}")
        else:
            le.obrigacao = ob["codigo"]
            if d:
                le.data = d.isoformat()
                if d > hoje:
                    le.problemas.append("data de execução no futuro")
                else:
                    le.periodo = agenda.periodo_de(ob["agenda"], d)
                    _atraso(le, texto, ob["agenda"], d)
    _gatilhos(conn, le, ativos, hoje, tn)
    return le


def registrar(conn, leitura: Leitura, arquivo: str, guardado_em: str | None = None) -> int:
    """Grava a evidência. Se a leitura achou um gatilho, abre a obrigação por evento (prazo de 24 h,
    o do registro no SIGBM); se o documento é a evidência de uma obrigação acionada, encerra-a.
    `arquivo` é o nome que as pessoas veem; `guardado_em`, onde o original ficou (pasta ou S3)."""
    if not leitura.completa:
        raise ValueError("leitura incompleta: " + "; ".join(leitura.problemas))
    if leitura.empresa_id is None:
        raise ValueError("leitura sem empresa: não dá para saber de qual empresa é o ativo")
    ativo = db.ativo_por_codigo(conn, leitura.empresa_id, leitura.ativo)
    if ativo is None:
        raise ValueError(f"{leitura.ativo} não é ativo da empresa {leitura.empresa_id}")
    aid = ativo["id"]
    if leitura.data:
        dia = date.fromisoformat(leitura.data)
        if leitura.apenas_aciona:       # o termo de embargo só abre: não encerra nem dá baixa em nada
            for codigo in leitura.acionar:
                db.acionar(conn, aid, codigo, leitura.data, (dia + timedelta(days=1)).isoformat(),
                           "; ".join(leitura.gatilhos), origem=arquivo)
            return 0
        db.encerrar_acionamentos(conn, aid, leitura.obrigacao, leitura.data)
        for codigo in (c for c in leitura.acionar if c != leitura.obrigacao):   # o relatório da ISE não reabre a ISE
            db.acionar(conn, aid, codigo, leitura.data, (dia + timedelta(days=1)).isoformat(),
                       "; ".join(leitura.gatilhos), origem=arquivo)
    return db.registrar_evidencia(conn, aid, leitura.obrigacao, leitura.periodo, arquivo=guardado_em or arquivo,
                                  extraido={"documento": leitura.documento, "data": leitura.data,
                                            "pontuacao_maxima": leitura.pontuacao_maxima,
                                            "estado_conservacao": leitura.estado_conservacao or None,
                                            "metodo": leitura.metodo, "avisos": leitura.avisos})


def exemplo(nome: str) -> Path:
    return db.ROOT / "data" / "exemplos" / nome
