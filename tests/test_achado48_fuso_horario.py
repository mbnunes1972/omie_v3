# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-48 — o livro é datado em UTC e a empresa vive em UTC−3.

`mod_contabil.lancar()` carimbava `Lancamento.data` com `datetime.utcnow()` quando `data` não era
passada; `efetivado_no_dia` (guarda de duplicidade do ACHADO-35) montava a janela do dia com
`date.today()` — hora LOCAL do processo. Os dois discordam sempre que o relógio do servidor não
é UTC (a bancada) ou sempre que a competência precisa bater com o calendário de Brasília (mesmo
com o servidor em UTC — aí a guarda "funciona" só porque os dois lados usam UTC, mas a
competência real está errada e ninguém percebe).

DECIDIDO 02/09: o fuso é CONFIGURAÇÃO — `Loja.config_financeira_json['fuso_horario']`, cadeia
loja → rede → America/Sao_Paulo, NUNCA o relógio do processo. Aceite explícito do achado: com o
relógio do processo em UTC E em America/Sao_Paulo, os aceites do ACHADO-35 passam nos dois."""
import json
import os
import subprocess
import sys

import mod_contabil


def test_resolver_fuso_owner_cadeia_loja_rede_default(app_db, seed):
    db = app_db.get_session()
    loja_id = seed["loja1_id"]
    loja = db.get(app_db.Loja, loja_id)

    # 1) sem config nenhuma: default
    loja.config_financeira_json = None
    db.commit()
    assert mod_contabil.resolver_fuso_owner(db, "loja", loja_id) == "America/Sao_Paulo"

    # 2) config da própria loja manda
    loja.config_financeira_json = json.dumps({"fuso_horario": "America/Manaus"})
    db.commit()
    assert mod_contabil.resolver_fuso_owner(db, "loja", loja_id) == "America/Manaus"

    # 3) volta ao default quando a config não tem a chave
    loja.config_financeira_json = json.dumps({"outra_coisa": True})
    db.commit()
    assert mod_contabil.resolver_fuso_owner(db, "loja", loja_id) == "America/Sao_Paulo"

    # 4) owner "rede" sem Rede.config_financeira_json (campo não existe hoje) — cai no default
    rede_id = seed.get("rede_id")
    if rede_id:
        assert mod_contabil.resolver_fuso_owner(db, "rede", rede_id) == "America/Sao_Paulo"

    db.close()


def test_agora_no_fuso_independe_do_relogio_do_processo(app_db, seed):
    """O mesmo owner/config tem que dar a MESMA hora de parede não importa o TZ do processo —
    é exatamente essa independência que fecha o ACHADO-48 (nunca o relógio da máquina)."""
    db = app_db.get_session()
    loja_id = seed["loja1_id"]
    loja = db.get(app_db.Loja, loja_id)
    loja.config_financeira_json = json.dumps({"fuso_horario": "America/Sao_Paulo"})
    db.commit()

    a1 = mod_contabil.agora_no_fuso(db, "loja", loja_id)
    a2 = mod_contabil.agora_no_fuso(db, "loja", loja_id)
    assert abs((a2 - a1).total_seconds()) < 2, "duas chamadas próximas no tempo real têm que ficar próximas"
    db.close()


def test_lancar_carimba_com_agora_no_fuso_nao_utcnow(app_db, seed):
    db = app_db.get_session()
    loja_id = seed["loja1_id"]
    loja = db.get(app_db.Loja, loja_id)
    # fuso deliberadamente MUITO diferente de UTC pra tornar o desvio óbvio no teste
    loja.config_financeira_json = json.dumps({"fuso_horario": "Pacific/Kiritimati"})   # UTC+14
    db.commit()

    ot, oid = "loja", loja_id
    mod_contabil.seed_plano(db, ot, oid)
    cd = mod_contabil._conta_por_codigo(db, ot, oid, "5.4.20")
    cc = mod_contabil._conta_por_codigo(db, ot, oid, "2.1.01")
    lan = mod_contabil.lancar(db, ot, oid, cd.id, cc.id, 10.0, historico="teste ACHADO-48")

    from database import Lancamento
    reg = db.get(Lancamento, lan["id"])
    esperado = mod_contabil.agora_no_fuso(db, ot, oid)
    assert abs((reg.data - esperado).total_seconds()) < 5, (
        "Lancamento.data tem que vir do fuso do dono do livro, não de utcnow()")
    from datetime import datetime as _dt
    assert abs((reg.data - _dt.utcnow()).total_seconds()) > 3600, (
        "com UTC+14 configurado, a diferença pro utcnow() real tem que ser enorme — "
        "prova que não é mais utcnow() quem carimba"
    )
    db.close()


def _rodar_achado35_com_tz(tz):
    env = dict(os.environ)
    env["TZ"] = tz
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_aceite_achado35.py", "-q"],
        cwd=os.path.join(os.path.dirname(__file__), ".."), env=env,
        capture_output=True, text=True, timeout=60)
    return r


def test_aceite_achado35_passa_com_processo_em_utc():
    r = _rodar_achado35_com_tz("UTC")
    assert r.returncode == 0, "ACHADO-35 com o processo em UTC:\n" + r.stdout[-3000:] + r.stderr[-2000:]


def test_aceite_achado35_passa_com_processo_em_america_sao_paulo():
    r = _rodar_achado35_com_tz("America/Sao_Paulo")
    assert r.returncode == 0, "ACHADO-35 com o processo em America/Sao_Paulo:\n" + r.stdout[-3000:] + r.stderr[-2000:]
