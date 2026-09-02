# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-44 — consistência interna do XML de Promob, testada
CONTRA ELE MESMO (nada externo entra na conta). Medido a partir do C1 (docs/db/
TAREFA_PERCURSO_0209.md): um arquivo de PE editado à mão (o `TOTAL` de itens forçado, sem
recalcular o grand-total que o próprio arquivo declara em `TOTALPRICES`) atravessou o ciclo
inteiro sem ninguém notar — bastava conferir o arquivo contra ele mesmo.

Medição antes de travar: `pool_ambientes` (contrato) — 0/12 falham em homologação; `arquivo_pe`
(xml_pe) — 12/12 falham, porque são todos arquivos de teste do próprio Marcelo, editados à mão de
propósito. A trava é NO UPLOAD (prospectiva) — nada retroativo; os 12 arquivos já em base
continuam exatamente como estão."""
import os
import re

import pytest

from integracoes.promob_grupos import ler_xml_str, consistencia_interna

CAMINHO = "PROJETOS/Casa_Nova/xmls/Cozinha.xml"


def _conteudo_real():
    if not os.path.exists(CAMINHO):
        pytest.skip("XML de exemplo ausente")
    with open(CAMINHO, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def _conteudo_adulterado():
    """Mesma técnica que o Marcelo relatou: força o TOTAL de um item, sem tocar em
    TOTALPRICES (o grand-total declarado do arquivo) — a mesma assinatura do C1."""
    conteudo = _conteudo_real()
    m = re.search(r'<ORDER UNIT="([^"]*)" TOTAL="([^"]*)"', conteudo)
    assert m, "não achei um <ORDER UNIT=.. TOTAL=..> pra adulterar"
    unit, total = m.group(1), m.group(2)
    novo_total = round(float(total) + 1000.0, 2)
    alvo = m.group(0)
    substituto = '<ORDER UNIT="%s" TOTAL="%s"' % (unit, novo_total)
    assert conteudo.count(alvo) >= 1
    return conteudo.replace(alvo, substituto, 1)


def test_arquivo_integro_fecha_a_conta_consigo_mesmo():
    amb = ler_xml_str("Cozinha.xml", _conteudo_real())
    ok, problemas = consistencia_interna(amb)
    assert ok is True and problemas == []


def test_arquivo_adulterado_nao_fecha_a_conta():
    amb = ler_xml_str("Cozinha.xml", _conteudo_adulterado())
    ok, problemas = consistencia_interna(amb)
    assert ok is False
    assert len(problemas) == 1 and "custo de fábrica" in problemas[0]


def test_declarado_order_e_budget_extraidos_do_totalprices():
    amb = ler_xml_str("Cozinha.xml", _conteudo_real())
    assert amb["declarado_order"] is not None
    assert amb["declarado_budget"] is not None
    assert amb["declarado_budget"] == amb["total"]


def test_arquivo_sem_totalprices_nao_tem_o_que_conferir():
    """Formato antigo/sem a seção — não trava (nada a conferir, não é o mesmo achado)."""
    amb = {"grupos": [], "total": 100.0, "declarado_order": None, "declarado_budget": None}
    ok, problemas = consistencia_interna(amb)
    assert ok is True and problemas == []
