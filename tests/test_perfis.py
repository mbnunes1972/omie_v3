from auth import perfis


def test_slugs_sao_os_perfis_novos():
    assert set(perfis.slugs()) == {
        "master", "gerencial", "operador", "super_admin", "admin_rede"}
    assert set(perfis.slugs_loja()) == {"master", "gerencial", "operador"}


def test_desconto_max():
    assert perfis.desconto_max("master") == 50.0
    assert perfis.desconto_max("gerencial") == 20.0
    assert perfis.desconto_max("operador") == 10.0
    assert perfis.desconto_max("suporte") == 10.0          # alias legado -> operador
    assert perfis.desconto_max("inexistente") == 0.0       # default seguro


def test_acesso_matriz_modulos_e_paineis():
    # operacionais: as 3 bases de loja (master/gerencial/operador) acessam — não há mais
    # perfil de loja sem acesso operacional (o antigo "suporte só painéis" foi extinto).
    for p in ("master", "gerencial", "operador"):
        assert perfis.acessa_modulo(p, "comercial") is True
    # Financeiro/Folha: master e gerencial sim; operador não
    for m in ("financeiro", "folha"):
        for p in ("master", "gerencial"):
            assert perfis.acessa_modulo(p, m) is True
        assert perfis.acessa_modulo("operador", m) is False, m
    # Fiscal: master e gerencial acessam; operador NÃO (decisão do usuário 2026-07-24 —
    # este assert estava defasado da mudança e passava por sorte de cache do registro)
    for p in ("master", "gerencial"):
        assert perfis.acessa_modulo(p, "fiscal") is True
    assert perfis.acessa_modulo("operador", "fiscal") is False
    # painéis Admin/Config: só Master
    assert perfis.acessa_painel("master", "admin") and perfis.acessa_painel("master", "config")
    for p in ("gerencial", "operador"):
        assert perfis.acessa_painel(p, "admin") is False
        assert perfis.acessa_painel(p, "config") is False


def test_capacidades_preservadas():
    assert perfis.pode("master", "autorizar") is True
    assert perfis.pode("gerencial", "autorizar") is True
    assert perfis.pode("operador", "autorizar") is False
    assert perfis.pode("master", "aprovar_financeiro") is True
    assert perfis.pode("gerencial", "aprovar_financeiro") is True    # Gerencial GANHOU Financeiro (novo modelo)
    assert perfis.pode("master", "gerir_usuarios") is True
    assert perfis.pode("gerencial", "gerir_usuarios") is False       # Gerencial NÃO gerencia usuários (novo modelo)
    assert perfis.pode("operador", "gerir_usuarios") is False
    # ciclo operacional segue executável (grosseiro) p/ não travar o fluxo
    for p in ("master", "gerencial", "operador"):
        assert perfis.pode(p, "executar_pe") is True
        assert perfis.pode(p, "registrar_medicao") is True
    assert perfis.pode("inexistente", "gerir_usuarios") is False


def test_rotulo_e_existe():
    assert perfis.rotulo("master") == "Master"
    assert perfis.existe("operador") is True
    assert perfis.existe("diretor") is False   # slug-cargo antigo aposentado


def test_usuario_delega_perfis():
    from database import Usuario
    assert Usuario(nome="X", login="x", nivel="gerencial").limite_desconto == 20.0
    assert Usuario(nome="X", login="x", nivel="operador").limite_desconto == 10.0
    assert Usuario(nome="X", login="x", nivel="master").pode_ver_parametros is True
    assert Usuario(nome="X", login="x", nivel="operador").pode_ver_parametros is False


# ── Permissões por CONTA do Gestor de Rede (2026-08-08) ──────────────────────────

def test_capacidades_efetivas_rede_sem_override_usa_o_padrao_do_nivel():
    d = {"nivel": "admin_rede", "capacidades_override": {}}
    efetivas = perfis.capacidades_efetivas_rede(d)
    assert efetivas["gerir_usuarios"] is True     # padrão de admin_rede
    assert efetivas["gerir_perfis"] is False       # padrão de admin_rede


def test_capacidades_efetivas_rede_com_override():
    d = {"nivel": "admin_rede", "capacidades_override": {"gerir_usuarios": False}}
    efetivas = perfis.capacidades_efetivas_rede(d)
    assert efetivas["gerir_usuarios"] is False                    # override venceu
    assert efetivas["editar_dados_loja"] is True                  # não mexido, segue o padrão


def test_capacidades_efetivas_rede_outro_nivel_devolve_padrao_puro():
    assert perfis.capacidades_efetivas_rede({"nivel": "master"})["gerir_usuarios"] is True


def test_pode_usuario_sem_override_igual_a_pode():
    d = {"nivel": "admin_rede", "capacidades_override": {}}
    for cap in perfis.CAPACIDADES_OVERRIDAVEIS_REDE:
        assert perfis.pode_usuario(d, cap) == perfis.pode("admin_rede", cap)


def test_pode_usuario_com_override():
    d = {"nivel": "admin_rede", "capacidades_override": {"editar_dados_loja": False}}
    assert perfis.pode_usuario(d, "editar_dados_loja") is False
    assert perfis.pode("admin_rede", "editar_dados_loja") is True   # a base não muda, só a conta


def test_pode_usuario_nao_afeta_capacidade_fora_da_allowlist():
    """gerir_redes/gerir_lojas NÃO são overridáveis — são as capacidades que
    mod_tenancy._eh_super_admin/_eh_admin_rede usam pra reconhecer a identidade do nível."""
    assert "gerir_redes" not in perfis.CAPACIDADES_OVERRIDAVEIS_REDE
    assert "gerir_lojas" not in perfis.CAPACIDADES_OVERRIDAVEIS_REDE
    d = {"nivel": "admin_rede", "capacidades_override": {"gerir_redes": True, "gerir_lojas": False}}
    assert perfis.pode_usuario(d, "gerir_redes") is False     # ignora o override, fica na base (False)
    assert perfis.pode_usuario(d, "gerir_lojas") is True      # idem (base é True)


def test_pode_usuario_super_admin_sempre_pleno_mesmo_com_override_no_banco():
    """God-mode: mesmo que capacidades_override_json tenha algo gravado (não deveria, mas por
    segurança), super_admin não passa pelo override — pode() já barra isso antes."""
    d = {"nivel": "super_admin", "capacidades_override": {"gerir_usuarios": False}}
    assert perfis.pode_usuario(d, "gerir_usuarios") is True


def test_acessa_painel_usuario_override():
    d = {"nivel": "admin_rede", "capacidades_override": {"acesso_admin": False}}
    assert perfis.acessa_painel_usuario(d, "admin") is False
    assert perfis.acessa_painel("admin_rede", "admin") is True   # base intocada


def test_usuario_orm_capacidades_override_json():
    """capacidades_efetivas_rede/pode_usuario aceitam o objeto Usuario direto (não só dict) —
    lê capacidades_override_json (string JSON crua) em vez de capacidades_override (já parseado)."""
    from database import Usuario
    import json
    u = Usuario(nome="X", login="x", nivel="admin_rede",
               capacidades_override_json=json.dumps({"gerir_usuarios": False}))
    assert perfis.pode_usuario(u, "gerir_usuarios") is False
    assert perfis.pode_usuario(u, "editar_dados_loja") is True


def test_usuario_orm_capacidades_override_json_vazio_ou_invalido():
    from database import Usuario
    u1 = Usuario(nome="X", login="x", nivel="admin_rede", capacidades_override_json=None)
    assert perfis.pode_usuario(u1, "gerir_usuarios") is True   # padrão do nível
    u2 = Usuario(nome="X", login="x", nivel="admin_rede", capacidades_override_json="não é json")
    assert perfis.pode_usuario(u2, "gerir_usuarios") is True   # inválido -> ignora, cai no padrão


def test_usuario_dict_inclui_rotulo_e_gerir():
    from auth.auth import _usuario_dict
    from database import Usuario
    d = _usuario_dict(Usuario(id=1, nome="Ana", login="ana", nivel="master"))
    assert d["rotulo"] == "Master" and d["pode_gerir_usuarios"] is True and d["limite_desconto"] == 50.0
    d2 = _usuario_dict(Usuario(id=2, nome="C", login="c", nivel="operador"))
    assert d2["pode_gerir_usuarios"] is False
