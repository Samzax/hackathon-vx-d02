"""Responsáveis técnicos e o dado pessoal: CPF mascarado por padrão, "ver CPF" auditado, LGPD.

Regras exercidas aqui (o resto está em `regulaia/pessoal.py` e `regulaia/responsaveis.py`):
- Quem cadastra e remove responsável é a **própria empresa** (`seguranca.da_empresa`): a plataforma só
  lê os dados da cliente, e dado pessoal não é exceção.
- A listagem devolve **sempre o CPF mascarado**, para qualquer papel. Ver o CPF inteiro é do
  **Regulatório e da TI da própria empresa**, por `GET /responsaveis/{id}/cpf`, e **cada visualização
  vai para a auditoria** com quem viu, de quem e quando.
- Sem `REGULAIA_CHAVE_DADOS` a API sobe, mas guardar CPF responde 503 com o motivo: nada de chave
  padrão no código, que faria a cifra de enfeite.
- LGPD: `GET /empresas/{id}/dados-pessoais` (exportar, com o CPF em claro, direito do titular) e
  `DELETE` (apagar). As duas são da TI da própria empresa e ficam na trilha.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from regulaia import db, pessoal, responsaveis as dominio

from .. import auditoria
from ..banco import conexao
from ..seguranca import Escopo, da_empresa, empresa_visivel, escopo as sessao, ti

rota = APIRouter(tags=["responsáveis"])


class Responsavel(BaseModel):
    id: int
    papel: str = Field(description="responsavel_tecnico, coordenador_paebm, responsavel_ambiental...")
    papel_rotulo: str
    nome: str
    cpf_mascarado: str = Field(description="o CPF como a API devolve por padrão; nunca o inteiro",
                               examples=["***.456.789-**"])
    registro: str | None = Field(description="registro no conselho", examples=["CREA MG-123456"])
    art_numero: str | None
    art_vigencia_ate: str | None = Field(description="ART vencendo vira obrigação")
    unidade: str | None
    ativo_codigo: str | None
    ficticio: bool = Field(description="dado de demonstração (na demo, só CPF fictício)")
    criado_por: str
    criado_em: str


class Novo(BaseModel):
    papel: str = Field(pattern="^(responsavel_tecnico|coordenador_paebm|responsavel_ambiental|responsavel_seguranca)$")
    nome: str = Field(min_length=2, max_length=200)
    cpf: str | None = Field(None, max_length=20, description="guardado cifrado; a API nunca devolve inteiro na lista")
    registro: str | None = Field(None, max_length=60)
    art_numero: str | None = Field(None, max_length=60)
    art_vigencia_ate: str | None = Field(None, description="AAAA-MM-DD")
    unidade: str | None = Field(None, description="a unidade por que responde")
    ativo_codigo: str | None = Field(None, description="ou o ativo")
    ficticio: bool = Field(False, description="dado de demonstração")
    consentimento_para: str | None = Field(None, description=(
        "empreendedor pessoa física: para que a pessoa consentiu em informar os próprios dados"))


class Criado(BaseModel):
    responsavel_id: int
    obrigacao_art: str | None = Field(description="a obrigação de renovar a ART, se havia vigência")


class Cpf(BaseModel):
    cpf: str = Field(description="o CPF inteiro; esta visualização ficou na auditoria")


class Papeis(BaseModel):
    papeis: dict[str, str] = Field(description="{papel: nome para mostrar}")


class DadosPessoais(BaseModel):
    empresa: str
    pessoas: list[dict] = Field(description="o que a plataforma guarda de pessoa, com o CPF em claro")


class Apagados(BaseModel):
    removidos: int


class Ok(BaseModel):
    ok: bool


def _unidades_do_escopo(conn, e: Escopo, empresa_id: int) -> list[str] | None:
    """Os nomes de unidade e os códigos de ativo que a sessão vê, para filtrar os responsáveis. Quem vê
    tudo recebe None (sem filtro). O gestor vê os responsáveis dos ativos dele e os das unidades desses
    ativos: quem responde pela Mina A é responsável das barragens dela."""
    if e.ve_tudo:
        return None
    meus = [a for a in db.ativos(conn, empresa_id) if e.ve_ativo(a)]
    unidades = {a["unidade"] for a in meus if a.get("unidade")} | set(e.unidades)
    return [*sorted(unidades), *(a["codigo"] for a in meus)]


@rota.get("/responsaveis/papeis", response_model=Papeis, summary="Os papéis que um responsável pode ter")
def papeis(e: Escopo = Depends(sessao)):
    return Papeis(papeis=dominio.PAPEIS)


@rota.get("/empresas/{empresa_id}/responsaveis", response_model=list[Responsavel],
          summary="Responsáveis técnicos da empresa, sempre com o CPF mascarado")
def listar(empresa_id: int, e: Escopo = Depends(sessao), conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    unidades = _unidades_do_escopo(conn, e, empresa_id)
    return [Responsavel(**{k: v for k, v in vars(r).items() if k not in ("empresa_id", "consentimento")})
            for r in dominio.responsaveis(conn, empresa_id, unidades)]


@rota.post("/empresas/{empresa_id}/responsaveis", status_code=201, response_model=Criado,
           summary="Cadastrar um responsável técnico (a própria empresa); o CPF entra cifrado")
def criar(empresa_id: int, dados: Novo, request: Request, e: Escopo = Depends(da_empresa),
          conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    consentimento = None
    if dados.consentimento_para:
        consentimento = dominio.consentimento_de(e.assinante, dados.consentimento_para, e.empresa)
    try:
        rid = dominio.registrar_responsavel(
            conn, empresa_id, papel=dados.papel, nome=dados.nome, por=e.assinante, cpf=dados.cpf,
            registro=dados.registro, art_numero=dados.art_numero,
            art_vigencia_ate=dados.art_vigencia_ate, unidade=dados.unidade,
            ativo_codigo=dados.ativo_codigo, consentimento=consentimento, ficticio=dados.ficticio)
    except pessoal.SemChave as erro:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(erro)) from None
    except pessoal.CpfInvalido as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    except dominio.ErroResponsavel as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    # o CPF nunca entra no detalhe da auditoria: fica o que a pessoa fez, não o dado dela
    auditoria.registrar(conn, request, "responsavel_criado", dados.nome,
                        {"papel": dados.papel, "unidade": dados.unidade, "ativo": dados.ativo_codigo,
                         "com_cpf": bool(dados.cpf), "art_vigencia_ate": dados.art_vigencia_ate})
    art = dominio.obrigacao_de_art(conn, empresa_id, rid, e.assinante)
    return Criado(responsavel_id=rid, obrigacao_art=art)


@rota.get("/responsaveis/{responsavel_id}/cpf", response_model=Cpf,
          summary="Ver o CPF inteiro (Regulatório e TI da própria empresa). Fica na auditoria")
def ver_cpf(responsavel_id: int, empresa_id: int, request: Request, e: Escopo = Depends(sessao),
            conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    if e.so_leitura:        # a plataforma acompanha a empresa, mas não vê o dado pessoal dela
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "a equipe RegulaIA não vê o CPF dos responsáveis da empresa")
    if not (e.ve_tudo or e.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "ver o CPF inteiro é do Regulatório, da Diretoria e da TI da empresa")
    r = dominio.responsavel(conn, empresa_id, responsavel_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"responsável {responsavel_id} não existe")
    try:
        cpf = dominio.ver_cpf(conn, empresa_id, responsavel_id)
    except pessoal.SemChave as erro:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(erro)) from None
    except dominio.ErroResponsavel as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    # cada visualização de dado pessoal fica registrada: quem viu, de quem, quando
    auditoria.registrar(conn, request, "cpf_visto", r.nome,
                        {"responsavel_id": responsavel_id, "empresa": emp["nome"]})
    return Cpf(cpf=cpf)


@rota.delete("/responsaveis/{responsavel_id}", response_model=Ok,
             summary="Remover um responsável (a própria empresa)")
def apagar(responsavel_id: int, empresa_id: int, request: Request, e: Escopo = Depends(da_empresa),
           conn=Depends(conexao)):
    empresa_visivel(conn, e, empresa_id)
    r = dominio.responsavel(conn, empresa_id, responsavel_id)
    if r is None or not dominio.apagar(conn, empresa_id, responsavel_id, e.assinante):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"responsável {responsavel_id} não existe")
    auditoria.registrar(conn, request, "responsavel_removido", r.nome, {"responsavel_id": responsavel_id})
    return Ok(ok=True)


# ------------------------------------------------------------------ LGPD


@rota.get("/empresas/{empresa_id}/dados-pessoais", response_model=DadosPessoais,
          summary="LGPD: exportar os dados pessoais da empresa (TI da própria empresa). Fica na auditoria")
def exportar(empresa_id: int, request: Request, e: Escopo = Depends(ti), conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    if e.so_leitura:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "a equipe RegulaIA não exporta o dado pessoal da empresa")
    pessoas = dominio.exportar(conn, empresa_id)
    auditoria.registrar(conn, request, "dados_pessoais_exportados", emp["nome"], {"pessoas": len(pessoas)})
    return DadosPessoais(empresa=emp["nome"], pessoas=pessoas)


@rota.delete("/empresas/{empresa_id}/dados-pessoais", response_model=Apagados,
             summary="LGPD: apagar os dados pessoais da empresa (TI da própria empresa). Fica na auditoria")
def apagar_dados_pessoais(empresa_id: int, request: Request, e: Escopo = Depends(ti),
                          conn=Depends(conexao)):
    emp = empresa_visivel(conn, e, empresa_id)
    if e.so_leitura:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "a equipe RegulaIA não apaga o dado pessoal da empresa")
    n = dominio.apagar_dados_pessoais(conn, empresa_id, e.assinante)
    auditoria.registrar(conn, request, "dados_pessoais_apagados", emp["nome"], {"removidos": n})
    return Apagados(removidos=n)
