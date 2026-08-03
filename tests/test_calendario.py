"""mod_calendario — utilitário GENÉRICO de dias úteis (Agenda da Loja, Fatia 0).

Spec: docs/superpowers/specs/agenda/2026-08-03-agenda-da-loja-design.md §7.
cfg = seção `agenda` da config da loja: {"sabado_util": bool, "feriados": ["AAAA-MM-DD", ...]}.
Default: seg–sex úteis, sem feriados. `espalhar` reparte um valor em N dias úteis com a última
fatia absorvendo o resíduo (Σ exata ao centavo — padrão da casa)."""
from datetime import date

import mod_calendario as cal

# 2026-08-03 = segunda; 2026-08-08 = sábado; 2026-08-09 = domingo
SEG, TER, SEX = date(2026, 8, 3), date(2026, 8, 4), date(2026, 8, 7)
SAB, DOM, SEG2 = date(2026, 8, 8), date(2026, 8, 9), date(2026, 8, 10)


def test_eh_dia_util_semana_e_fds():
    assert cal.eh_dia_util(SEG) and cal.eh_dia_util(SEX)
    assert not cal.eh_dia_util(SAB)
    assert not cal.eh_dia_util(DOM)


def test_sabado_util_configuravel():
    cfg = {"sabado_util": True}
    assert cal.eh_dia_util(SAB, cfg)
    assert not cal.eh_dia_util(DOM, cfg)


def test_feriado_nao_e_util():
    cfg = {"feriados": ["2026-08-04"]}
    assert not cal.eh_dia_util(TER, cfg)
    assert cal.eh_dia_util(SEG, cfg)


def test_proximo_dia_util():
    assert cal.proximo_dia_util(SEG) == SEG                      # já útil → o próprio
    assert cal.proximo_dia_util(SAB) == SEG2                     # fds → segunda
    assert cal.proximo_dia_util(SAB, {"sabado_util": True}) == SAB
    assert cal.proximo_dia_util(TER, {"feriados": ["2026-08-04"]}) == date(2026, 8, 5)


def test_adicionar_dias_uteis():
    assert cal.adicionar_dias_uteis(SEG, 0) == SEG               # 0 = o próprio (normalizado a útil)
    assert cal.adicionar_dias_uteis(SEG, 4) == SEX
    assert cal.adicionar_dias_uteis(SEX, 1) == SEG2              # pula o fim de semana
    assert cal.adicionar_dias_uteis(SAB, 0) == SEG2              # começa no próximo útil
    assert cal.adicionar_dias_uteis(SEG, 2, {"feriados": ["2026-08-05"]}) == date(2026, 8, 6)


def test_dias_uteis_entre_inclusivo():
    assert cal.dias_uteis_entre(SEG, SEX) == 5
    assert cal.dias_uteis_entre(SEG, SEG2) == 6                  # fds não conta
    assert cal.dias_uteis_entre(SEG, SEG2, {"sabado_util": True}) == 7
    assert cal.dias_uteis_entre(SEG, SEX, {"feriados": ["2026-08-05"]}) == 4
    assert cal.dias_uteis_entre(SEX, SEG) == 0                   # invertido → 0
    assert cal.dias_uteis_entre(SAB, DOM) == 0


def test_espalhar_soma_exata_e_pula_fds():
    fatias = cal.espalhar(10000.0, SEX, 3)
    assert list(fatias.keys()) == [SEX, SEG2, date(2026, 8, 11)]  # sex, seg, ter
    assert round(sum(fatias.values()), 2) == 10000.0
    assert fatias[SEX] == 3333.33 and fatias[date(2026, 8, 11)] == 3333.34  # última absorve


def test_espalhar_inicio_nao_util_rola_pra_frente():
    fatias = cal.espalhar(300.0, SAB, 2)
    assert list(fatias.keys()) == [SEG2, date(2026, 8, 11)]
    assert sum(fatias.values()) == 300.0


def test_espalhar_casos_degenerados():
    assert cal.espalhar(500.0, SEG, 1) == {SEG: 500.0}
    assert cal.espalhar(500.0, SEG, 0) == {SEG: 500.0}            # n<1 tratado como 1
    assert cal.espalhar(0.0, SEG, 3) == {SEG: 0.0, TER: 0.0, date(2026, 8, 5): 0.0}


def test_feriados_invalidos_sao_ignorados():
    cfg = {"feriados": ["não-é-data", None, "2026-08-04"]}
    assert not cal.eh_dia_util(TER, cfg)
    assert cal.eh_dia_util(SEG, cfg)


# ── config "Agenda e Capacidade" (defaults + validação em mod_provisoes) ────────────────────

def test_config_default_tem_secao_agenda():
    import mod_provisoes
    ag = mod_provisoes.config_financeira_default().get("agenda")
    assert ag is not None
    assert ag["produtividade_montagem_rs_dupla_dia"] == 7000.0
    assert ag["duplas_disponiveis"] == 2
    assert ag["produtividade_pe_rs_dia"] == 20000.0
    assert ag["sabado_util"] is False
    assert ag["feriados"] == []
    assert ag["horizonte_capacidade_semanas"] == 6
    # rev 2026-08-03: SEM teto artificial — a janela vem do cronograma do projeto
    assert "teto_dias_montagem" not in ag


def test_validar_config_agenda():
    import mod_provisoes
    base = mod_provisoes.config_financeira_default()
    ok = dict(base, agenda=dict(base["agenda"], feriados=["2026-12-25"]))
    assert mod_provisoes.validar_config_financeira(ok) == []
    ruim = dict(base, agenda=dict(base["agenda"], produtividade_montagem_rs_dupla_dia=0))
    assert any("produtividade" in e.lower() for e in mod_provisoes.validar_config_financeira(ruim))
    ruim2 = dict(base, agenda=dict(base["agenda"], feriados=["31/12/2026"]))
    assert any("feriado" in e.lower() for e in mod_provisoes.validar_config_financeira(ruim2))
    ruim3 = dict(base, agenda=dict(base["agenda"], duplas_disponiveis=-1))
    assert any("dupla" in e.lower() for e in mod_provisoes.validar_config_financeira(ruim3))
    ruim4 = dict(base, agenda=dict(base["agenda"], produtividade_pe_rs_dia=0))
    assert any("projeto executivo" in e.lower() for e in mod_provisoes.validar_config_financeira(ruim4))
