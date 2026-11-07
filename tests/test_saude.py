from datetime import date

from regulaia import agenda, db, demo, torre


def test_prototipo_saude_reusa_torre_sem_mapa_geografico():
    """O segundo setor usa o mesmo cadastro, agenda e evidências, com ativos não geográficos."""
    conn = db.conectar(":memory:")
    ids = demo.montar_saude(conn)
    empresa = next(e for e in db.empresas(conn) if e["setor"] == "saude")
    linhas = torre.painel(conn, empresa["id"], date(2026, 11, 7), date(2026, 1, 1))

    assert {a["tipo"] for a in db.ativos(conn, empresa["id"])} == {"estabelecimento_saude", "abrigo_residuos"}
    assert {l.codigo for l in linhas} >= {"RDC63-01", "RDC36-01", "RDC222-01", "NR32-01"}
    assert next(l for l in linhas if l.codigo == "RDC36-02" and l.ativo == "HSP-01").status == agenda.ATRASADA


def test_dou_identifica_atos_do_setor_saude_sem_mudar_o_parser():
    from collector.xml_dou import XmlAct, atos_do_setor

    comum = dict(id_materia="1", name="", pub_name="DO1", art_type="Resolução", pub_date=date(2026, 8, 1),
                  page="", edition="", pdf_page="", identifica="", ementa="", texto_html="")
    saude = XmlAct(category="Ministério da Saúde/Agência Nacional de Vigilância Sanitária", **comum)
    anm = XmlAct(category="Ministério de Minas e Energia/Agência Nacional de Mineração", **(comum | {"id_materia": "2"}))

    assert atos_do_setor([saude, anm], "saude") == [saude]
    assert atos_do_setor([saude, anm], "mineracao") == [anm]
