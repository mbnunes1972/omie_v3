# -*- coding: utf-8 -*-
"""tests/test_loja_logo.py — upload/remoção da logo própria da loja (Frente 2, 2026-08-20).

Sobe o servidor real (fixtures de conftest.py) e bate via HTTP, como test_documentos_api.py —
upload multipart precisa da composição real (login+escopo+multipart+disco), não só do módulo.
"""
import os

import pytest


def _login(factory, who):
    c = factory()
    status, body = c.login(who, "senha123")
    assert status == 200, body
    return c


PNG_FAKE = b"\x89PNG\r\n\x1a\nconteudo fake de teste, nao precisa ser um PNG real"


@pytest.fixture
def logos_dir(monkeypatch, tmp_path):
    import mod_contrato
    d = str(tmp_path / "logos_loja")
    monkeypatch.setattr(mod_contrato, "LOGOS_LOJA_DIR", d)
    return d


def test_upload_logo_sem_permissao_403(seed, http_client_factory, logos_dir):
    c = _login(http_client_factory, "cons_l1")   # operador: sem editar_dados_loja
    status, body = c.post_multipart(
        "/api/admin/lojas/%d/logo" % seed["loja1_id"],
        {"arquivo": ("logo.png", PNG_FAKE)})
    assert status == 403, body


def test_upload_logo_extensao_invalida_400(seed, http_client_factory, logos_dir):
    c = _login(http_client_factory, "dir_l1")
    status, body = c.post_multipart(
        "/api/admin/lojas/%d/logo" % seed["loja1_id"],
        {"arquivo": ("logo.gif", PNG_FAKE)})
    assert status == 400, body
    assert "PNG" in body["erro"] or "JPG" in body["erro"]


def test_upload_logo_excede_tamanho_400(seed, http_client_factory, logos_dir):
    c = _login(http_client_factory, "dir_l1")
    grande = b"x" * (3 * 1024 * 1024 + 1)
    status, body = c.post_multipart(
        "/api/admin/lojas/%d/logo" % seed["loja1_id"],
        {"arquivo": ("logo.png", grande)})
    assert status == 400, body
    assert "3 MB" in body["erro"] or "maior" in body["erro"].lower()


def test_upload_logo_feliz_grava_arquivo_e_atualiza_loja(app_db, seed, http_client_factory, logos_dir):
    c = _login(http_client_factory, "dir_l1")
    status, body = c.post_multipart(
        "/api/admin/lojas/%d/logo" % seed["loja1_id"],
        {"arquivo": ("logo.png", PNG_FAKE)})
    assert status == 200, body
    assert body["ok"] is True
    assert body["logo_url"] == "/api/admin/lojas/%d/logo" % seed["loja1_id"]

    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        assert loja.logo_arquivo
        caminho = os.path.join(logos_dir, str(seed["loja1_id"]), loja.logo_arquivo)
        assert os.path.isfile(caminho)
    finally:
        db.close()

    # GET serve o arquivo de volta
    status, body = c.get("/api/admin/lojas/%d/logo" % seed["loja1_id"])
    assert status == 200


def test_remover_logo_volta_para_padrao(app_db, seed, http_client_factory, logos_dir):
    c = _login(http_client_factory, "dir_l1")
    status, _ = c.post_multipart(
        "/api/admin/lojas/%d/logo" % seed["loja1_id"],
        {"arquivo": ("logo.png", PNG_FAKE)})
    assert status == 200

    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        caminho_antigo = os.path.join(logos_dir, str(seed["loja1_id"]), loja.logo_arquivo)
    finally:
        db.close()
    assert os.path.isfile(caminho_antigo)

    status, body = c.post("/api/admin/lojas/%d/logo/remover" % seed["loja1_id"])
    assert status == 200, body
    assert body["ok"] is True

    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        assert not loja.logo_arquivo
    finally:
        db.close()
    assert not os.path.isfile(caminho_antigo)


def test_gerar_pdf_contrato_usa_logo_da_loja_quando_definido(app_db, seed, http_client_factory, logos_dir):
    import mod_contrato
    import tempfile

    c = _login(http_client_factory, "dir_l1")
    status, _ = c.post_multipart(
        "/api/admin/lojas/%d/logo" % seed["loja1_id"],
        {"arquivo": ("logo.png", PNG_FAKE)})
    assert status == 200

    db = app_db.get_session()
    try:
        loja_dict = {
            "id": seed["loja1_id"], "nome": "Loja", "logo_arquivo": None, "logo_loja_id": None,
        }
        loja = db.get(app_db.Loja, seed["loja1_id"])
        loja_dict["logo_arquivo"] = loja.logo_arquivo
        loja_dict["logo_loja_id"] = loja.id
    finally:
        db.close()

    html = mod_contrato._html_capa(
        {"loja": loja_dict, "_ambientes": [], "_pag": {}, "num_contrato": "X", "data_contrato": "1"})
    assert "logo_dalmobile.png" not in html
    assert "file://" in html


def test_gerar_pdf_sem_logo_cai_no_padrao(logos_dir):
    import mod_contrato
    html = mod_contrato._html_capa(
        {"loja": {"id": 1}, "_ambientes": [], "_pag": {}, "num_contrato": "X", "data_contrato": "1"})
    assert 'src="logo_dalmobile.png"' in html
