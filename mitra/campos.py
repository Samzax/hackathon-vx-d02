"""Os campos do cadastro de um ativo: nome de tela, tipo, valores possíveis e a conferência do valor.

Os nomes dos campos são os das regras de aplicabilidade (`extrator.VOCABULARIO`) e os que o SIGBM traz.
A torre edita o cadastro com isto (`api/cadastro.py`) e a instanciação confere o que chega pelo formulário
ou pela planilha (`instanciacao.py`): valor que não é do tipo do campo volta com o erro, nunca é presumido.
"""

from __future__ import annotations

import re
from datetime import date

from . import sigbm

BOOL, NUMERO, OPCOES, TEXTO, DATA = "booleano", "numero", "opcoes", "texto", "data"
_NIVEIS = ["alto", "medio", "baixo"]

# campo: (nome de tela, tipo, opções, tipos de ativo)
CAMPOS: dict[str, tuple[str, str, list[str] | None, tuple[str, ...]]] = {
    "uf": ("UF", TEXTO, None, ("barragem", "unidade", "obra")),
    "municipio": ("Município", TEXTO, None, ("barragem", "unidade", "obra")),
    "minerio": ("Minério", TEXTO, None, ("barragem",)),
    "sigbm_codigo": ("Código no SIGBM", TEXTO, None, ("barragem",)),
    "altura_m": ("Altura (m)", NUMERO, None, ("barragem",)),
    "volume_m3": ("Volume do reservatório (m³)", NUMERO, None, ("barragem",)),
    "inserida_pnsb": ("Na PNSB", BOOL, None, ("barragem",)),
    "metodo_construtivo": ("Método construtivo", OPCOES, ["montante", "jusante", "linha_de_centro", "etapa_unica"],
                           ("barragem",)),
    "cri": ("Categoria de risco (CRI)", OPCOES, _NIVEIS, ("barragem",)),
    "dpa": ("Dano potencial associado (DPA)", OPCOES, _NIVEIS, ("barragem",)),
    "dpa2": ("Pontuação de perda de vidas do DPA", NUMERO, None, ("barragem",)),
    "potencial_dano_ambiental": ("Potencial de dano ambiental (classificação estadual)", OPCOES, _NIVEIS,
                                 ("barragem",)),
    "situacao_operacional": ("Situação operacional", OPCOES,
                             ["ativa", "inativa", "em_descaracterizacao", "em_construcao"], ("barragem",)),
    "nivel_emergencia": ("Nível de emergência", NUMERO, None, ("barragem",)),
    "trabalhadores_zas": ("Trabalhadores na ZAS", BOOL, None, ("barragem",)),
    "mapa_inundacao_validado": ("Mapa de inundação validado", BOOL, None, ("barragem",)),
    "alteamento_continuo": ("Alteamento contínuo", BOOL, None, ("barragem",)),
    "modificacao_estrutural": ("Modificação estrutural", BOOL, None, ("barragem",)),
    "residuo_perigoso": ("Resíduo perigoso", BOOL, None, ("barragem",)),
    "categoria": ("Tipo de unidade", OPCOES, ["mina", "usina", "pilha", "outra"], ("unidade",)),
    "lavra": ("Lavra", OPCOES, ["ceu_aberto", "subterranea"], ("unidade",)),
    "beneficiamento": ("Beneficiamento mineral", BOOL, None, ("unidade",)),
    "deposito_rejeitos": ("Depósito de estéril ou rejeitos", BOOL, None, ("unidade",)),
    "usa_explosivos": ("Usa explosivos", BOOL, None, ("unidade",)),
    "carvao": ("Mina de carvão", BOOL, None, ("unidade",)),
    "dragas": ("Dragas flutuantes", BOOL, None, ("unidade",)),
    "trabalhadores": ("Trabalhadores", NUMERO, None, ("unidade", "obra")),
    "classe": ("Classe do equipamento", OPCOES, ["vaso_pressao", "caldeira", "tubulacao", "tanque", "maquina",
                                                 "transportador_continuo", "equipamento_guindar", "veiculo"],
               ("equipamento",)),
    "categoria_vaso": ("Categoria do vaso (NR-13)", OPCOES, ["I", "II", "III", "IV", "V"], ("equipamento",)),
    "categoria_caldeira": ("Categoria da caldeira (NR-13)", OPCOES, ["A", "B"], ("equipamento",)),
    "spie": ("SPIE certificado", BOOL, None, ("equipamento",)),
    "em_operacao": ("Em operação", BOOL, None, ("equipamento",)),
    "subsolo": ("Em subsolo", BOOL, None, ("equipamento",)),
    "orgao": ("Órgão emissor", TEXTO, None, ("licenca",)),
    "validade": ("Validade", DATA, None, ("licenca",)),
    # obra (vertical 2, fase A): o suficiente para as regras da NR-18/NR-35 citarem
    "categoria_obra": ("Tipo de obra", OPCOES, ["edificacao", "infraestrutura", "industrial", "demolicao",
                                                "outra"], ("obra",)),
    "fase_obra": ("Fase da obra", OPCOES, ["projeto", "execucao", "paralisada", "concluida"], ("obra",)),
    "trabalho_altura": ("Trabalho em altura (acima de 2 m)", BOOL, None, ("obra",)),
}

VALORES = {"etapa_unica": "etapa única", "linha_de_centro": "linha de centro", "medio": "médio",
           "em_descaracterizacao": "em descaracterização", "em_construcao": "em construção",
           "ceu_aberto": "céu aberto", "subterranea": "subterrânea", "vaso_pressao": "vaso de pressão",
           "transportador_continuo": "transportador contínuo", "equipamento_guindar": "equipamento de guindar",
           "tubulacao": "tubulação", "maquina": "máquina", "veiculo": "veículo",
           "edificacao": "edificação", "demolicao": "demolição", "execucao": "execução"}

_SIM = {"sim", "s", "verdadeiro", "true", "1", "x"}
_NAO = {"nao", "não", "n", "falso", "false", "0"}


class ValorInvalido(ValueError):
    pass


def do_tipo(tipo_ativo: str) -> dict[str, tuple]:
    """Os campos que se preenchem num ativo deste tipo."""
    return {c: d for c, d in CAMPOS.items() if tipo_ativo in d[3]}


def pergunta(campo: str) -> str:
    """O que perguntar a quem preenche: a pergunta do SIGBM, se houver; senão, o vocabulário das regras."""
    from . import torre

    return sigbm.FALTAM_NO_SIGBM.get(campo) or torre.campo_legivel(campo)


def valor_legivel(v) -> str:
    return VALORES.get(v, str(v).replace("_", " ")) if isinstance(v, str) else str(v)


def converter(campo: str, bruto):
    """O valor digitado (formulário ou célula da planilha) no tipo do campo. Vazio: None (não informado).
    Valor que não serve levanta ValorInvalido com o que se esperava."""
    if bruto is None or (isinstance(bruto, str) and not bruto.strip()):
        return None
    rotulo, tipo, opcoes, _ = CAMPOS[campo]
    if tipo == BOOL:
        if isinstance(bruto, bool):
            return bruto
        t = str(bruto).strip().lower()
        if t in _SIM:
            return True
        if t in _NAO:
            return False
        raise ValorInvalido(f"{rotulo}: {bruto!r} não é sim ou não")
    if tipo == NUMERO:
        if isinstance(bruto, bool):
            raise ValorInvalido(f"{rotulo}: {bruto!r} não é número")
        if isinstance(bruto, (int, float)):
            return bruto
        t = str(bruto).strip().replace(" ", "")
        if re.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?", t):      # 2.980.000,5 (planilha em português)
            t = t.replace(".", "")
        try:
            n = float(t.replace(",", "."))
        except ValueError:
            raise ValorInvalido(f"{rotulo}: {bruto!r} não é número") from None
        return int(n) if n.is_integer() else n
    if tipo == OPCOES:
        t = str(bruto).strip()
        achado = next((o for o in opcoes or [] if t.lower() in (o.lower(), valor_legivel(o).lower())), None)
        if achado is None:
            raise ValorInvalido(f"{rotulo}: {bruto!r} não é uma das opções ({', '.join(opcoes or [])})")
        return achado
    if tipo == DATA:
        t = str(bruto).strip()
        if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t):
            t = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        try:
            return date.fromisoformat(t).isoformat()
        except ValueError:
            raise ValorInvalido(f"{rotulo}: {bruto!r} não é data (AAAA-MM-DD ou DD/MM/AAAA)") from None
    t = str(bruto).strip()
    if campo == "uf":
        t = t.upper()
        if not re.fullmatch(r"[A-Z]{2}", t):
            raise ValorInvalido(f"{rotulo}: {bruto!r} não é uma UF (duas letras)")
    return t


def conferir(tipo_ativo: str, atributos: dict, livres: bool = False) -> dict:
    """Os atributos de um ativo do tipo, convertidos; campo que não é desse tipo ou valor que não serve: erro.
    O que vier vazio fica de fora (é dado faltando, não falso nem zero).
    `livres`: campo que não está em CAMPOS passa como veio (a edição do cadastro aceita campo fora da
    lista como texto livre); campo de outro tipo de ativo continua erro."""
    validos = do_tipo(tipo_ativo)
    erros, out = [], {}
    for campo, bruto in (atributos or {}).items():
        if campo not in validos:
            if livres and campo not in CAMPOS:
                out[campo] = bruto
            else:
                erros.append(f"{campo}: não é campo do cadastro de {tipo_ativo}")
            continue
        try:
            v = converter(campo, bruto)
        except ValorInvalido as e:
            erros.append(str(e))
            continue
        if v is not None:
            out[campo] = v
    if erros:
        raise ValorInvalido("; ".join(erros))
    return out
