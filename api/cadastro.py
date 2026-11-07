"""O cadastro do ativo para quem preenche: nome de tela, tipo do campo e valores possíveis.

Os nomes dos campos são os das regras (`regulaia/extrator.py`, VOCABULARIO); aqui fica só como cada um
aparece e se edita no front. Campo fora desta lista continua editável como texto."""

from __future__ import annotations

from regulaia import sigbm, torre

BOOL, NUMERO, OPCOES, TEXTO, DATA = "booleano", "numero", "opcoes", "texto", "data"
_NIVEIS = ["alto", "medio", "baixo"]

# campo: (nome de tela, tipo, opções, tipos de ativo)
CAMPOS: dict[str, tuple[str, str, list[str] | None, tuple[str, ...]]] = {
    "uf": ("UF", TEXTO, None, ("barragem", "unidade")),
    "municipio": ("Município", TEXTO, None, ("barragem",)),
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
    "situacao_operacional": ("Situação operacional", OPCOES,
                             ["ativa", "inativa", "em_descaracterizacao", "em_construcao"], ("barragem",)),
    "nivel_emergencia": ("Nível de emergência", NUMERO, None, ("barragem",)),
    "trabalhadores_zas": ("Trabalhadores na ZAS", BOOL, None, ("barragem",)),
    "mapa_inundacao_validado": ("Mapa de inundação validado", BOOL, None, ("barragem",)),
    "alteamento_continuo": ("Alteamento contínuo", BOOL, None, ("barragem",)),
    "modificacao_estrutural": ("Modificação estrutural", BOOL, None, ("barragem",)),
    "residuo_perigoso": ("Resíduo perigoso", BOOL, None, ("barragem",)),
    "lavra": ("Lavra", OPCOES, ["ceu_aberto", "subterranea"], ("unidade",)),
    "beneficiamento": ("Beneficiamento mineral", BOOL, None, ("unidade",)),
    "deposito_rejeitos": ("Depósito de estéril ou rejeitos", BOOL, None, ("unidade",)),
    "usa_explosivos": ("Usa explosivos", BOOL, None, ("unidade",)),
    "carvao": ("Mina de carvão", BOOL, None, ("unidade",)),
    "dragas": ("Dragas flutuantes", BOOL, None, ("unidade",)),
    "trabalhadores": ("Trabalhadores", NUMERO, None, ("unidade",)),
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
}

VALORES = {"etapa_unica": "etapa única", "linha_de_centro": "linha de centro", "medio": "médio",
           "em_descaracterizacao": "em descaracterização", "em_construcao": "em construção",
           "ceu_aberto": "céu aberto", "subterranea": "subterrânea", "vaso_pressao": "vaso de pressão",
           "transportador_continuo": "transportador contínuo", "equipamento_guindar": "equipamento de guindar",
           "tubulacao": "tubulação", "maquina": "máquina", "veiculo": "veículo"}


def pergunta(campo: str) -> str:
    """O que perguntar a quem preenche: a pergunta do SIGBM, se houver; senão, o vocabulário das regras."""
    return sigbm.FALTAM_NO_SIGBM.get(campo) or torre.campo_legivel(campo)


def valor(v) -> str:
    return VALORES.get(v, str(v).replace("_", " ")) if isinstance(v, str) else str(v)
