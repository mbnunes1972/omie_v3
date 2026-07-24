# tests/test_perfis_tenancy.py
from auth import perfis


def test_perfis_novos_existem():
    assert perfis.existe("super_admin") is True
    assert perfis.existe("admin_rede") is True
    assert perfis.rotulo("super_admin") == "Administrador da Plataforma"
    assert perfis.rotulo("admin_rede")  == "Gestor de Rede"


def test_capacidades_administrativas():
    assert perfis.pode("super_admin", "gerir_redes")        is True
    assert perfis.pode("super_admin", "gerir_lojas")        is True
    assert perfis.pode("super_admin", "editar_dados_loja")  is True
    assert perfis.pode("super_admin", "gerir_usuarios")     is True

    assert perfis.pode("admin_rede", "gerir_redes")         is False
    assert perfis.pode("admin_rede", "gerir_lojas")         is True
    assert perfis.pode("admin_rede", "editar_dados_loja")   is True
    assert perfis.pode("admin_rede", "gerir_usuarios")      is True

    assert perfis.pode("diretoria", "editar_dados_loja")      is True
    assert perfis.pode("diretoria", "gerir_lojas")            is False
    assert perfis.pode("diretoria", "gerir_redes")            is False

    assert perfis.pode("consultor", "gerir_redes")          is False
    assert perfis.pode("consultor", "gerir_lojas")          is False
    assert perfis.pode("consultor", "editar_dados_loja")    is False


def test_perfis_novos_sem_poder_operacional():
    # admin_rede (plataforma/rede) NÃO tem poderes operacionais/comerciais.
    assert perfis.desconto_max("admin_rede") == 0.0
    for cap in ("autorizar", "aprovar_financeiro", "registrar_medicao",
                "aprovar_medicao_reprovada", "ver_parametros"):
        assert perfis.pode("admin_rede", cap) is False, cap
    # super_admin é god-mode (decisão 2026-07-16): irrestrito → toda capacidade True.
    # O desconto_max segue 0 (o bypass é só em pode(), não em desconto_max()).
    assert perfis.desconto_max("super_admin") == 0.0
    for cap in ("autorizar", "aprovar_financeiro", "registrar_medicao",
                "aprovar_medicao_reprovada", "ver_parametros"):
        assert perfis.pode("super_admin", cap) is True, cap


def test_usuario_dict_expoe_tenant_e_flags():
    from auth.auth import _usuario_dict
    from database import Usuario
    u = Usuario(id=9, nome="SA", login="sad2026", nivel="super_admin",
                loja_id=None, rede_id=None)
    d = _usuario_dict(u)
    assert d["loja_id"] is None
    assert d["rede_id"] is None
    assert d["pode_gerir_redes"]       is True
    assert d["pode_gerir_lojas"]       is True
    assert d["pode_editar_dados_loja"] is True

    ar = Usuario(id=10, nome="AR", login="ar1", nivel="admin_rede",
                 loja_id=None, rede_id=3)
    da = _usuario_dict(ar)
    assert da["rede_id"] == 3
    assert da["pode_gerir_redes"] is False
    assert da["pode_gerir_lojas"] is True
