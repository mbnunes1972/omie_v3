from datetime import datetime, timedelta
import mod_cronograma
import mod_provisoes


# ── HTTP: editar data_prevista com reautenticação + auditoria (Gerente+) ─────────
def test_data_prevista_reauth_gerente_edita_e_audita(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # data futura calculada (não fixa): o endpoint agora rejeita reagendar pro passado
    # (achado do usuário 2026-08-25) — uma string fixa "envelheceria" e quebraria o teste.
    nova = (datetime.now() + timedelta(days=20)).replace(hour=0, minute=0, second=0, microsecond=0)
    st, d = c.post("/api/projetos/Proj_L1/ciclo/9/data-prevista",
                   {"login": "dir_l1", "senha": "senha123", "data_prevista": nova.strftime("%Y-%m-%d")})
    assert st == 200 and d.get("ok") is True, d
    db = app_db.get_session()
    try:
        e9 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="9").first()
        assert e9 and e9.data_prevista_conclusao == nova
        log = (db.query(app_db.LogAcaoGerencial)
               .filter_by(projeto_nome="Proj_L1", acao="editar_data_prevista", etapa_alvo="9").first())
        assert log is not None                    # auditado (quem/quando/old→new)
        assert '"valor_novo"' in (log.contexto or "")
    finally:
        db.close()


def test_data_prevista_consultor_barrado(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # autorizador é consultor (sem 'autorizar') → 403, mesmo com senha correta
    st, d = c.post("/api/projetos/Proj_L1/ciclo/10/data-prevista",
                   {"login": "cons_l1", "senha": "senha123", "data_prevista": "2026-08-20"})
    assert st == 403 and d.get("ok") is False


def test_data_prevista_senha_errada_barrada(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/Proj_L1/ciclo/10/data-prevista",
                   {"login": "dir_l1", "senha": "errada", "data_prevista": "2026-08-20"})
    assert st == 403 and d.get("ok") is False


# Achado do usuário (2026-08-25, testando o arrastar-para-reagendar da Agenda): nada impedia
# reagendar pro passado, nem pra antes da etapa que precede esta no ciclo.
def test_data_prevista_rejeita_data_passada(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    st, d = c.post("/api/projetos/Proj_L1/ciclo/9/data-prevista",
                   {"login": "dir_l1", "senha": "senha123", "data_prevista": ontem})
    assert st == 400 and d.get("ok") is False
    assert "passada" in d.get("erro", "")


# Achado do usuário (2026-08-25, testando ao vivo): a trava acima barrava também CORRIGIR um
# evento que JÁ estava atrasado (data prevista antiga < hoje, não concluído) — "o evento, se não
# concluído, estava atrasado, deveria aceitar reagendamento". Só barra ir pro passado quando a
# etapa ainda NÃO estava atrasada (sem data prevista, ou data prevista futura).
def test_data_prevista_aceita_correcao_de_atraso_para_data_ainda_passada(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    antiga = datetime.now() - timedelta(days=10)
    db = app_db.get_session()
    try:
        # "18" (não usada por outro teste deste arquivo) — evita colidir com a linha de "9"
        # já criada por test_data_prevista_reauth_gerente_edita_e_audita (mesma fixture app_db).
        db.add(app_db.CicloEtapa(projeto_nome="Proj_L1", etapa_codigo="18", data_prevista_conclusao=antiga))
        db.commit()
    finally:
        db.close()
    nova = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")   # ainda passada, mas > antiga
    st, d = c.post("/api/projetos/Proj_L1/ciclo/18/data-prevista",
                   {"login": "dir_l1", "senha": "senha123", "data_prevista": nova})
    assert st == 200 and d.get("ok") is True, d


def test_data_prevista_rejeita_antes_do_predecessor(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    base = (datetime.now() + timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    db = app_db.get_session()
    try:
        # "14" (Recebimento do Pedido) depende de "13" (Produção) via PREDECESSOR_OVERRIDE.
        db.add(app_db.CicloEtapa(projeto_nome="Proj_L1", etapa_codigo="13", data_prevista_conclusao=base))
        db.commit()
    finally:
        db.close()
    antes = (base - timedelta(days=5)).strftime("%Y-%m-%d")
    st, d = c.post("/api/projetos/Proj_L1/ciclo/14/data-prevista",
                   {"login": "dir_l1", "senha": "senha123", "data_prevista": antes})
    assert st == 400 and d.get("ok") is False
    assert "Produção" in d.get("erro", "")


# ── v12: funcionário responsável filtrado pela função exigida pela fase ──────────
def test_responsavel_funcionario_restrito_a_funcao(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fmed = app_db.Funcao(loja_id=loja, nome="Medidor")
    fmont = app_db.Funcao(loja_id=loja, nome="Montador")
    db.add_all([fmed, fmont]); db.flush()
    medidor = app_db.Funcionario(loja_id=loja, nome="Ana Medidora", funcao_id=fmed.id, status="ativo")
    montador = app_db.Funcionario(loja_id=loja, nome="Beto Montador", funcao_id=fmont.id, status="ativo")
    db.add_all([medidor, montador])
    et = app_db.CicloEtapa(projeto_nome="Proj_L1", etapa_codigo="10", funcao_responsavel_id=fmed.id)
    db.add(et); db.commit()
    fmed_id, med_id, mont_id = fmed.id, medidor.id, montador.id
    db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    # função errada (Montador numa fase de Medidor) → barrado
    st, d = c.post("/api/projetos/Proj_L1/ciclo/10/responsavel", {"funcionario_id": mont_id})
    assert st == 400 and d.get("ok") is False, d
    # função certa → aceito
    st2, d2 = c.post("/api/projetos/Proj_L1/ciclo/10/responsavel", {"funcionario_id": med_id})
    assert st2 == 200 and d2.get("ok") is True, d2
    # o /ciclo passa a expor a função exigida e o funcionário escolhido
    _, cic = c.get("/api/projetos/Proj_L1/ciclo")
    e10 = next(x for x in cic["ciclo"] if x["etapa_codigo"] == "10")
    assert e10["funcao_responsavel_nome"] == "Medidor"
    assert e10["responsavel_funcionario_nome"] == "Ana Medidora"
    # dropdown filtrado por função lista só o medidor
    _, lst = c.get("/api/funcionarios?funcao_id=%d" % fmed_id)
    nomes = {x["nome"] for x in lst["itens"]}
    assert "Ana Medidora" in nomes and "Beto Montador" not in nomes


def test_usuarios_loja_expoe_funcao_do_funcionario(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fcon = app_db.Funcao(loja_id=loja, nome="Consultor de Vendas"); db.add(fcon); db.flush()
    func = app_db.Funcionario(loja_id=loja, nome="Carla Vendas", funcao_id=fcon.id, status="ativo")
    db.add(func); db.flush()
    u = app_db.Usuario(nome="Carla Vendas", login="carla@loja.com", nivel="consultor",
                       loja_id=loja, ativo=1, funcionario_id=func.id)
    u.set_senha("x"); db.add(u); db.commit()
    db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/admin/usuarios")
    carla = next(x for x in d["usuarios"] if x["login"] == "carla@loja.com")
    assert carla["funcao_nome"] == "Consultor de Vendas"   # Função herdada do Funcionário
    assert carla["nivel"] == "consultor"                   # Perfil (acesso) inalterado


def _cfg(fases):
    cfg = mod_provisoes.config_financeira_default()
    cfg["cronograma_padrao"] = fases
    return cfg


def test_config_default_inclui_cronograma():
    cfg = mod_provisoes.config_financeira_default()
    assert "cronograma_padrao" in cfg
    assert any(f["codigo"] == "8" for f in cfg["cronograma_padrao"])


def test_default_cronograma_em_duracoes_e_formato_2():
    cfg = mod_provisoes.config_financeira_default()
    assert cfg.get("cronograma_formato") == 2                      # nasce em durações
    fases = cfg["cronograma_padrao"]
    # durações (não acumulado): nenhuma etapa isolada dura mais que o ciclo inteiro
    total = sum(int(f["prazo_dias"]) for f in fases)
    assert total <= 90                                             # ~50 dias úteis ≈ ~72 corridos
    assert all(int(f["prazo_dias"]) <= 30 for f in fases)          # nenhuma etapa vira o acumulado antigo (55,70…)


def test_cronograma_padrao_normaliza_e_ignora_invalido():
    fases = mod_cronograma.cronograma_padrao(_cfg([
        {"codigo": "9", "prazo_dias": "5", "funcao_id": "7"},   # strings viram int
        {"codigo": "", "prazo_dias": 3},      # sem código → ignorado
        {"codigo": "10", "prazo_dias": -4},   # negativo → 0; sem funcao_id → None
    ]))
    by = {f["codigo"]: f for f in fases}
    assert by["9"] == {"codigo": "9", "prazo_dias": 5, "funcao_id": 7}
    assert by["10"] == {"codigo": "10", "prazo_dias": 0, "funcao_id": None}
    assert all(f["codigo"] for f in fases)


def test_gerar_cronograma_herda_funcao_responsavel(app_db):
    db = app_db.get_session()
    # funcao_responsavel_id é FK real (funcoes.id) — cria a função de verdade em vez de um
    # literal fabricado (Postgres valida FK; SQLite não).
    funcao = app_db.Funcao(nome="Funcao Cronograma", status="ativo")
    db.add(funcao); db.flush()
    d0 = datetime(2026, 7, 1)
    cfg = _cfg([{"codigo": "10", "prazo_dias": 10, "funcao_id": funcao.id}])
    mod_cronograma.gerar_cronograma_projeto(db, "ProjFn", cfg, d0); db.commit()
    e10 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjFn", etapa_codigo="10").first()
    assert e10.funcao_responsavel_id == funcao.id         # função herdada do padrão no D0
    assert e10.responsavel_funcionario_id is None         # funcionário nasce vazio
    db.close()


def test_gerar_cronograma_define_data_prevista_acumulado(app_db):
    db = app_db.get_session()
    d0 = datetime(2026, 7, 1, 12, 0, 0)
    # prazo_dias = DURAÇÃO por etapa; data_prevista = D0 + Σ durações até a etapa (inclusive)
    cfg = _cfg([{"codigo": "9", "prazo_dias": 5}, {"codigo": "13", "prazo_dias": 45}])
    mod_cronograma.gerar_cronograma_projeto(db, "ProjX", cfg, d0); db.commit()
    e9 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjX", etapa_codigo="9").first()
    e13 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjX", etapa_codigo="13").first()
    assert e9.data_prevista_conclusao == d0 + timedelta(days=5)        # 1ª etapa: só a própria duração
    assert e13.data_prevista_conclusao == d0 + timedelta(days=50)      # 5 + 45 acumulado
    assert e9.concluido_em is None
    db.close()


def test_gerar_cronograma_de_config_legada_reproduz_offsets_originais(app_db):
    # Regressão: config LEGADA (acumulado) normalizada → durações e então acumulada por
    # gerar_cronograma_projeto deve reproduzir EXATAMENTE os offsets acumulados originais.
    # Ou seja: normalizar + acumular = identidade sobre o dado legado (loja antiga não muda de data).
    d0 = datetime(2026, 7, 1)
    legado = {"cronograma_padrao": [
        {"codigo": "9", "prazo_dias": 5}, {"codigo": "10", "prazo_dias": 10},
        {"codigo": "16", "prazo_dias": 55}]}          # acumulado (dias desde D0), sem cronograma_formato
    cfg = mod_provisoes.normalizar_cronograma_formato(legado)   # vira durações (5, 5, 45)
    db = app_db.get_session()
    mod_cronograma.gerar_cronograma_projeto(db, "ProjLeg", cfg, d0); db.commit()
    by = {e.etapa_codigo: e.data_prevista_conclusao
          for e in db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjLeg").all()}
    assert by["9"]  == d0 + timedelta(days=5)     # offsets ACUMULADOS originais reproduzidos
    assert by["10"] == d0 + timedelta(days=10)
    assert by["16"] == d0 + timedelta(days=55)
    db.close()


def test_normalizar_cronograma_formato_converte_legado():
    # config legada: acumulado (dias desde D0), sem marcador de formato
    legado = {"cronograma_padrao": [
        {"codigo": "8", "prazo_dias": 2}, {"codigo": "9", "prazo_dias": 5},
        {"codigo": "10", "prazo_dias": 10}, {"codigo": "16", "prazo_dias": 55},
    ]}
    out = mod_provisoes.normalizar_cronograma_formato(legado)
    by = {f["codigo"]: f["prazo_dias"] for f in out["cronograma_padrao"]}
    assert by == {"8": 2, "9": 3, "10": 5, "16": 45}   # diferenças = durações
    assert out["cronograma_formato"] == 2


def test_normalizar_cronograma_formato_idempotente():
    ja = {"cronograma_formato": 2, "cronograma_padrao": [{"codigo": "8", "prazo_dias": 2}]}
    out = mod_provisoes.normalizar_cronograma_formato(ja)
    assert out["cronograma_padrao"][0]["prazo_dias"] == 2   # não converte de novo
    assert out["cronograma_formato"] == 2


def test_normalizar_cronograma_formato_sem_cronograma_nao_inventa():
    # config antiga sem a chave → não cria lista vazia (o merge com default é quem preenche)
    out = mod_provisoes.normalizar_cronograma_formato({"provisoes": {}})
    assert "cronograma_padrao" not in out


def test_normalizar_cronograma_formato_valor_invalido_nao_quebra():
    # config real de loja pode vir malformada (None/"" no meio da lista) → não pode dar 500 no read
    legado = {"cronograma_padrao": [
        {"codigo": "8", "prazo_dias": 2}, {"codigo": "9", "prazo_dias": None},
        {"codigo": "10", "prazo_dias": ""}, {"codigo": "11", "prazo_dias": 10},
    ]}
    out = mod_provisoes.normalizar_cronograma_formato(legado)
    for f in out["cronograma_padrao"]:
        assert isinstance(f["prazo_dias"], int) and f["prazo_dias"] >= 0
    assert out["cronograma_formato"] == 2


def test_normalizar_cronograma_formato_lista_vazia():
    out = mod_provisoes.normalizar_cronograma_formato({"cronograma_padrao": []})
    assert out["cronograma_padrao"] == []
    assert out["cronograma_formato"] == 2


def test_normalizar_cronograma_formato_item_nao_dict_ignora():
    out = mod_provisoes.normalizar_cronograma_formato(
        {"cronograma_padrao": [{"codigo": "8", "prazo_dias": 2}, "lixo", None]})
    cods = [f["codigo"] for f in out["cronograma_padrao"]]
    assert cods == ["8"]                     # itens não-dict ignorados, sem exceção
    assert out["cronograma_formato"] == 2


def test_cfg_loja_converte_cronograma_legado_na_leitura(http_client_factory, seed, app_db):
    # grava no config da loja o formato-legado acumulado (sem cronograma_formato)
    db = app_db.get_session()
    import json as _json
    loja = db.query(app_db.Loja).filter_by(id=db.query(app_db.Usuario)
              .filter_by(login="dir_l1").first().loja_id).first()
    loja.config_financeira_json = _json.dumps({"cronograma_padrao": [
        {"codigo": "10", "prazo_dias": 10}, {"codigo": "16", "prazo_dias": 55}]})
    db.commit(); loja_id = loja.id; db.close()
    # GET config-financeira deve devolver durações (10→10, 16→45), não o acumulado
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/admin/lojas/%d/config-financeira" % loja_id)
    assert st == 200
    by = {f["codigo"]: f["prazo_dias"] for f in d["config"]["cronograma_padrao"]}
    assert by["10"] == 10 and by["16"] == 45
    assert d["config"]["cronograma_formato"] == 2


def test_gerar_cronograma_idempotente_e_preserva_conclusao(app_db):
    db = app_db.get_session()
    d0 = datetime(2026, 7, 1)
    cfg = _cfg([{"codigo": "9", "prazo_dias": 5}])
    mod_cronograma.gerar_cronograma_projeto(db, "ProjY", cfg, d0); db.commit()
    # etapa concluída manualmente (data_conclusao preenchida)
    e9 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjY", etapa_codigo="9").first()
    e9.status = "concluido"; e9.concluido_em = datetime(2026, 7, 3); db.commit()
    # reexecuta o cronograma → recomputa data_prevista, NÃO duplica nem apaga a conclusão
    mod_cronograma.gerar_cronograma_projeto(db, "ProjY", cfg, d0 + timedelta(days=1)); db.commit()
    regs = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjY", etapa_codigo="9").all()
    assert len(regs) == 1
    assert regs[0].data_prevista_conclusao == d0 + timedelta(days=6)   # recomputado do novo D0
    assert regs[0].concluido_em == datetime(2026, 7, 3)                # conclusão preservada
    db.close()


def test_projeto_tem_previsao_medicao_e_venda_programada(app_db):
    from datetime import datetime
    db = app_db.get_session()
    p = app_db.Projeto(nome_safe="ProjVP", previsao_medicao=datetime(2026, 8, 1), venda_programada=1)
    db.add(p); db.commit()
    got = db.get(app_db.Projeto, "ProjVP")
    assert got.previsao_medicao == datetime(2026, 8, 1)
    assert got.venda_programada == 1
    db.close()
