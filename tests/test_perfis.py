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


def test_usuario_dict_inclui_rotulo_e_gerir():
    from auth.auth import _usuario_dict
    from database import Usuario
    d = _usuario_dict(Usuario(id=1, nome="Ana", login="ana", nivel="master"))
    assert d["rotulo"] == "Master" and d["pode_gerir_usuarios"] is True and d["limite_desconto"] == 50.0
    d2 = _usuario_dict(Usuario(id=2, nome="C", login="c", nivel="operador"))
    assert d2["pode_gerir_usuarios"] is False
