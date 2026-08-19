import mod_ciclo as mc


def test_etapa_anterior():
    assert mc.etapa_anterior("4") == "3"
    assert mc.etapa_anterior("2") == "1"
    assert mc.etapa_anterior("1") is None
    assert mc.etapa_anterior("11a") is None


def test_etapas_revisao_e_aprovacao_orcamento_removidas():
    # Etapas 5 (Revisão de projeto) e 6 (Aprovação do orçamento pelo cliente) foram
    # eliminadas: o fluxo vai de Orçamento (4) direto para Contrato (7).
    assert "5" not in mc.ETAPAS_PRINCIPAIS
    assert "6" not in mc.ETAPAS_PRINCIPAIS
    assert "5" not in mc.ETAPA_NOME
    assert "6" not in mc.ETAPA_NOME


def test_contrato_vem_logo_apos_orcamento():
    assert mc.etapa_anterior("7") == "4"
    assert mc.pode_avancar("7", {"4": "concluido"}) is True
    assert mc.pode_avancar("7", {"4": "pendente"}) is False


def test_ordenar_codigos_numerico_com_subetapas():
    entrada = ["10", "2", "11a", "11", "3", "1", "17a", "17"]
    assert mc.ordenar_codigos(entrada) == ["1", "2", "3", "10", "11", "11a", "17", "17a"]


def test_pode_avancar_principal_exige_anterior_concluida():
    assert mc.pode_avancar("4", {"3": "concluido"}) is True
    assert mc.pode_avancar("4", {"3": "pendente"}) is False
    assert mc.pode_avancar("4", {}) is False


def test_pode_avancar_aceita_status_conclusivos_alternativos():
    # Etapas da cauda concluem com status alternativos (ex.: 'entregue', 'implantado').
    assert mc.pode_avancar("13", {"12": "implantado"}) is True
    assert mc.pode_avancar("8", {"7": "assinado"}) is True
    assert mc.pode_avancar("4", {"3": "em_andamento"}) is False


def test_pode_avancar_primeira_etapa_sempre_liberada():
    assert mc.pode_avancar("1", {}) is True


def test_etapa_pai():
    assert mc.etapa_pai("11a") == "11"
    assert mc.etapa_pai("11e") == "11"
    assert mc.etapa_pai("17a") == "17"
    assert mc.etapa_pai("11") is None      # principal não tem "pai"
    assert mc.etapa_pai("1") is None


def test_pode_avancar_subetapa_herda_gating_da_mae():
    # Sub-etapa do PE (11x) segue o gating da etapa-mãe 11 (que exige a 10 concluída).
    assert mc.pode_avancar("11a", {"10": "pendente"}) is False
    assert mc.pode_avancar("11a", {}) is False
    assert mc.pode_avancar("11a", {"10": "concluido"}) is True
    # Mesma resposta que a etapa-mãe:
    for st in ({}, {"10": "pendente"}, {"10": "concluido"}, {"10": "entregue"}):
        assert mc.pode_avancar("11a", st) == mc.pode_avancar("11", st)
    # Sub-etapa da Montagem (17a) segue a 17 (que exige a 16 concluída).
    assert mc.pode_avancar("17a", {"16": "pendente"}) is False
    assert mc.pode_avancar("17a", {"16": "entregue"}) is True


def test_codigos_a_resetar_inclui_alvo_e_posteriores_e_subs():
    existentes = ["1", "2", "3", "4", "5", "11", "11a", "11b"]
    resetar = mc.codigos_a_resetar("3", existentes)
    assert set(resetar) == {"3", "4", "5", "11", "11a", "11b"}
    assert "1" not in resetar and "2" not in resetar


def test_reabertura_bloqueada_por_contrato():
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "assinado") is True
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "vigente") is True
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "rascunho") is False
    assert mc.reabertura_bloqueada_por_contrato(["8", "9"], "assinado") is False


def test_af1_e_solicitacao_medicao_saem_dos_principais():
    # Achado do usuário 2026-08-17: viraram gatilhos da etapa 7 (Contrato), não mais etapas
    # próprias do espinhaço principal do ciclo.
    assert "8" not in mc.ETAPAS_PRINCIPAIS
    assert "9" not in mc.ETAPAS_PRINCIPAIS
    assert "7" in mc.ETAPAS_PRINCIPAIS and "10" in mc.ETAPAS_PRINCIPAIS


def test_af1_e_medicao_liberam_em_paralelo_so_por_contrato_assinado():
    # As duas dependem SÓ de "7" concluída — nenhuma depende da outra.
    assert mc.pode_avancar("8", {"7": "assinado"}) is True
    assert mc.pode_avancar("9", {"7": "assinado"}) is True
    assert mc.pode_avancar("8", {"7": "pendente"}) is False
    assert mc.pode_avancar("9", {"7": "pendente"}) is False
    # "9" concluída não é pré-requisito de "8", nem vice-versa.
    assert mc.pode_avancar("8", {"7": "assinado", "9": "pendente"}) is True
    assert mc.pode_avancar("9", {"7": "assinado", "8": "pendente"}) is True


def test_medicao_10_continua_exigindo_solicitacao_9_concluida():
    # "10" NÃO libera só com o contrato assinado — precisa especificamente de "9" concluída,
    # mesmo "9" não sendo mais o predecessor posicional de "10" em ETAPAS_PRINCIPAIS.
    assert mc.etapa_anterior("10") == "9"
    assert mc.pode_avancar("10", {"7": "assinado", "9": "pendente"}) is False
    assert mc.pode_avancar("10", {"7": "assinado", "9": "concluido"}) is True
    # "8" (AF1) concluída ou não não interfere em "10".
    assert mc.pode_avancar("10", {"7": "assinado", "8": "pendente", "9": "concluido"}) is True


def test_predecessor_de_8_e_9_e_explicitamente_7():
    assert mc.etapa_anterior("8") == "7"
    assert mc.etapa_anterior("9") == "7"


def test_grupo_logistica_e_expedicao_sai_dos_principais():
    # Achado do usuário 2026-08-18: 14/15/16 saem de ETAPAS_PRINCIPAIS — "13" representa o
    # grupo "Logística e Expedição" sozinha.
    assert "13" in mc.ETAPAS_PRINCIPAIS
    for cod in ("14", "15", "16"):
        assert cod not in mc.ETAPAS_PRINCIPAIS


def test_grupo_logistica_cadeia_sequencial_preservada():
    # A cadeia real 13→14→15→16→17 continua exigindo a etapa anterior concluída — só deixou
    # de ser posicional em ETAPAS_PRINCIPAIS, passou a ser explícita.
    assert mc.etapa_anterior("14") == "13"
    assert mc.etapa_anterior("15") == "14"
    assert mc.etapa_anterior("16") == "15"
    assert mc.etapa_anterior("17") == "16"   # sem o override, viraria "13" (pularia o grupo)
    assert mc.pode_avancar("14", {"13": "pendente"}) is False
    assert mc.pode_avancar("14", {"13": "concluido"}) is True
    assert mc.pode_avancar("17", {"13": "concluido", "16": "pendente"}) is False
    assert mc.pode_avancar("17", {"13": "concluido", "16": "concluido"}) is True


def test_etapa_seguinte_percorre_o_grupo_logistica():
    # Achado 2026-08-18: a notificação de passagem de fase precisa continuar avisando o
    # próximo responsável em cada handoff dentro do grupo (diferente de 8/9, que perderam
    # essa notificação de propósito por virarem paralelas).
    assert mc.etapa_seguinte("13") == "14"
    assert mc.etapa_seguinte("14") == "15"
    assert mc.etapa_seguinte("15") == "16"
    assert mc.etapa_seguinte("16") == "17"


def test_etapa_concluida_agregada_grupo_parcial_nao_conta():
    st_parcial = {"13": "concluido", "14": "concluido", "15": "pendente", "16": "pendente"}
    assert mc.etapa_concluida_agregada("13", st_parcial) is False
    st_total = {"13": "concluido", "14": "concluido", "15": "emitida", "16": "concluido"}
    assert mc.etapa_concluida_agregada("13", st_total) is True


def test_etapa_concluida_agregada_codigo_fora_de_grupo_comportamento_normal():
    assert mc.etapa_concluida_agregada("4", {"4": "concluido"}) is True
    assert mc.etapa_concluida_agregada("4", {"4": "pendente"}) is False
    assert mc.etapa_concluida_agregada("4", {}) is False


def test_codigos_relevantes_fase_inclui_o_grupo_escondido():
    rel = mc.codigos_relevantes_fase()
    assert set(mc.ETAPAS_PRINCIPAIS) <= set(rel)
    assert {"14", "15", "16"} <= set(rel)


def test_chave_ordenacao():
    assert mc.chave_ordenacao("11a") == (11, "a")
    assert mc.chave_ordenacao("2") == (2, "")


def test_etapa_nome_em_sincronia_com_principais():
    # Toda etapa principal tem nome. "8"/"9" (achado 2026-08-17, gatilhos da etapa 7) e
    # "14"/"15"/"16" (achado 2026-08-18, grupo "Logística e Expedição" representado por "13")
    # são as exceções conhecidas — saíram de ETAPAS_PRINCIPAIS mas continuam com nome em
    # ETAPA_NOME, ainda precisam de rótulo pros botões/sub-abas e pras mensagens de erro de
    # gating (ver PREDECESSOR_OVERRIDE).
    assert set(mc.ETAPAS_PRINCIPAIS) <= set(mc.ETAPA_NOME)
    assert set(mc.ETAPA_NOME) - set(mc.ETAPAS_PRINCIPAIS) == {"8", "9", "14", "15", "16"}


def test_exige_aprovacao_financeira():
    assert mc.exige_aprovacao_financeira("8") is True
    assert mc.exige_aprovacao_financeira("11d") is True
    assert mc.exige_aprovacao_financeira("7") is False
    assert mc.exige_aprovacao_financeira("11") is False
    assert mc.exige_aprovacao_financeira("9") is False


def test_etapa10_renomeada_medicao():
    assert mc.ETAPA_NOME["10"] == "Medição"


def test_etapa_4_renomeada_para_orcamento():
    assert mc.ETAPA_NOME["4"] == "Orçamento"


def test_tipo_doc_de():
    assert mc.tipo_doc_de("11a") == "pe_planta_pontos"
    assert mc.tipo_doc_de("11c") == "pe_projeto_executivo"
    assert mc.tipo_doc_de("11d") is None   # 11d não é subfase enriquecida
    assert mc.tipo_doc_de("99z") is None

def test_guarda_conclusao_exige_documento():
    ok, erro = mc.guarda_conclusao("11a", set(), {})
    assert ok is False and "Carregue" in erro
    ok, erro = mc.guarda_conclusao("11a", {"pe_planta_pontos"}, {})
    assert ok is True and erro == ""

def test_guarda_conclusao_11e_exige_anteriores():
    tipos = {"pe_pe_assinado"}
    # 11a-11c concluídas, 11d pendente → barra
    st = {"11a": "concluido", "11b": "concluido", "11c": "concluido", "11d": "pendente"}
    ok, erro = mc.guarda_conclusao("11e", tipos, st)
    assert ok is False and "11d" in erro
    # todas concluídas → libera
    st["11d"] = "aprovado"
    ok, erro = mc.guarda_conclusao("11e", tipos, st)
    assert ok is True

def test_versao_atual():
    from datetime import datetime
    docs = [
        {"tipo": "pe_projeto_executivo", "enviado_em": datetime(2026, 7, 10), "id": 1},
        {"tipo": "pe_projeto_executivo", "enviado_em": datetime(2026, 7, 12), "id": 2},
        {"tipo": "pe_planta_pontos",     "enviado_em": datetime(2026, 7, 9),  "id": 3},
    ]
    assert mc.versao_atual(docs, "pe_projeto_executivo")["id"] == 2
    assert mc.versao_atual(docs, "inexistente") is None


def test_tipo_doc_operacional():
    assert mc.tipo_doc_operacional("12") == "implantacao_pedido_xml"
    assert mc.tipo_doc_operacional("13") is None   # 13 não aceita upload
    assert mc.tipo_doc_operacional("14") is None
    assert mc.tipo_doc_operacional("11a") is None


def test_guarda_operacional_12_exige_xml():
    ok, erro = mc.guarda_conclusao_operacional("12", False, None, None)
    assert ok is False and "XML" in erro
    ok, erro = mc.guarda_conclusao_operacional("12", True, None, None)
    assert ok is True and erro == ""


def test_guarda_operacional_13_exige_numeros():
    ok, erro = mc.guarda_conclusao_operacional("13", False, "   \n  ", None)
    assert ok is False and "número" in erro.lower()
    ok, erro = mc.guarda_conclusao_operacional("13", False, "P-1001\nP-1002", None)
    assert ok is True and erro == ""


def test_guarda_operacional_14_exige_relatorio():
    ok, erro = mc.guarda_conclusao_operacional("14", False, None, "   ")
    assert ok is False and "Relatório" in erro
    ok, erro = mc.guarda_conclusao_operacional("14", False, None, "1 porta avariada")
    assert ok is True and erro == ""


def test_guarda_operacional_codigo_desconhecido():
    ok, erro = mc.guarda_conclusao_operacional("99", False, None, None)
    assert ok is False and "desconhecida" in erro.lower()


def test_etapas_operacionais_registradas():
    assert set(mc.ETAPAS_OPERACIONAIS) == {"12", "13", "14"}
    # nomes em sincronia com ETAPA_NOME (fonte canônica)
    for cod in mc.ETAPAS_OPERACIONAIS:
        assert mc.ETAPAS_OPERACIONAIS[cod]["nome"] == mc.ETAPA_NOME[cod]


def test_modelos_ciclo_documento_e_revisao(db_pg_limpo):
    database = db_pg_limpo
    s = database.Session()
    d = database.CicloDocumento(projeto_nome="P", etapa_codigo="11a",
                                tipo="pe_planta_pontos", arquivo_path="ciclo/11a/x.pdf",
                                nome_original="x.pdf")
    s.add(d); s.commit()
    r = database.CicloRevisao(projeto_nome="P", etapa_codigo="11b", relatorio_doc_id=d.id)
    s.add(r); s.commit()
    assert s.query(database.CicloDocumento).count() == 1
    assert s.query(database.CicloRevisao).first().etapa_codigo == "11b"
    s.close()


def test_guarda_conclusao_11c_pe_por_ambiente():
    # 2026-07-21: o documento único da 11c foi substituído na UI pelo PE POR AMBIENTE
    # (tabela de comparação). Todos os ambientes com PE → conclui sem o documento antigo.
    ok, erro = mc.guarda_conclusao("11c", set(), {}, pe_ambientes=(3, 3))
    assert ok is True and erro == ""
    # faltando ambiente → barra, com contagem
    ok, erro = mc.guarda_conclusao("11c", set(), {}, pe_ambientes=(3, 1))
    assert ok is False and "1/3" in erro
    # retrocompat: documento único da subfase (projeto legado) ainda satisfaz
    ok, erro = mc.guarda_conclusao("11c", {"pe_projeto_executivo"}, {}, pe_ambientes=(3, 0))
    assert ok is True
    # pool vazio → barra (nada a revisar não é conclusão)
    ok, erro = mc.guarda_conclusao("11c", set(), {}, pe_ambientes=(0, 0))
    assert ok is False
    # chamador antigo (sem pe_ambientes) → regra antiga do documento
    ok, erro = mc.guarda_conclusao("11c", set(), {})
    assert ok is False and "Carregue" in erro


def test_guarda_conclusao_11e_por_aprovacao_assinada():
    # Correção Fatia 3 (2026-07-21): a 11e conclui com a APROVAÇÃO DO PE assinada (documento
    # do sistema), não mais com upload de "PE Assinado". Doc legado segue valendo (retrocompat).
    st_ok = {"11a": "concluido", "11b": "concluido", "11c": "concluido", "11d": "aprovado"}
    ok, erro = mc.guarda_conclusao("11e", set(), st_ok, aprovacao_pe=True)
    assert ok is True and erro == ""
    ok, erro = mc.guarda_conclusao("11e", set(), st_ok, aprovacao_pe=False)
    assert ok is False and "Aprova" in erro
    # legado: doc pe_pe_assinado ainda satisfaz mesmo sem aprovação
    ok, erro = mc.guarda_conclusao("11e", {"pe_pe_assinado"}, st_ok, aprovacao_pe=False)
    assert ok is True
    # pré-requisitos 11a-11d continuam valendo mesmo com aprovação assinada
    st_falta = dict(st_ok, **{"11d": "pendente"})
    ok, erro = mc.guarda_conclusao("11e", set(), st_falta, aprovacao_pe=True)
    assert ok is False and "11d" in erro
    # chamador antigo (sem aprovacao_pe) → regra antiga do documento
    ok, erro = mc.guarda_conclusao("11e", set(), st_ok)
    assert ok is False and "Carregue" in erro
