# -*- coding: utf-8 -*-
"""perfil_store.py — leitura/escrita ORM de PerfilAcesso e seed idempotente por loja."""
import json
from database import PerfilAcesso
from . import mod_perfis

# Definição dos 3 perfis padrão (rev3 §2). base == slug para os de sistema.
_OPERACIONAIS = ["captacao", "cadastro", "comercial",
                 "estoque", "expedicao", "montagem", "assistencias"]
# Padronização dos títulos (decisão do usuário, 2026-07-22): Master (acesso a tudo — é o
# perfil do diretor/dono da loja), Gerente (acesso geral, por enquanto) e Operador (acesso ao
# seu escopo de trabalho). O slug 'gerencial' NÃO muda (usuários existentes apontam pra ele);
# só o rótulo visível virou "Gerente" — bases antigas: backfill_perfis_todas_lojas.
PERFIS_PADRAO = [
    {"slug": "master", "nome": "Master", "base": "master",
     "modulos": _OPERACIONAIS + ["fiscal", "financeiro", "folha", "admin", "config"]},
    {"slug": "gerencial", "nome": "Gerente", "base": "gerencial",
     "modulos": _OPERACIONAIS + ["fiscal", "financeiro", "folha"]},
    # 2026-07-24 (decisão do usuário): Operador SEM o módulo Fiscal (e sem Financeiro/Folha,
    # como sempre) — o backfill remove o fiscal dos operadores de sistema já semeados.
    {"slug": "operador", "nome": "Operador", "base": "operador",
     "modulos": _OPERACIONAIS},
]


def seed_perfis_loja(db, loja_id):
    """Semeia os 3 perfis padrão na loja. Idempotente por (loja_id, slug). Retorna nº criados."""
    if loja_id is None:
        return 0
    existentes = {p.slug for p in db.query(PerfilAcesso).filter_by(loja_id=loja_id).all()}
    criados = 0
    for spec in PERFIS_PADRAO:
        if spec["slug"] in existentes:
            continue
        db.add(PerfilAcesso(loja_id=loja_id, slug=spec["slug"], nome=spec["nome"],
                            base=spec["base"], modulos_json=json.dumps(spec["modulos"]),
                            sistema=1))
        criados += 1
    db.commit()
    if criados:
        from auth import perfis as _perfis    # import local: evita ciclo no load do módulo
        _perfis.recarregar()
    return criados


def backfill_perfis_todas_lojas(db):
    """Roda no start (idempotente): garante os perfis padrão em TODAS as lojas e aplica a
    padronização de títulos de 2026-07-22 ('Gerencial' → 'Gerente' — só quem ainda tem o
    nome do seed antigo; nome customizado no painel de Perfis não é sobrescrito)."""
    from database import Loja
    criados = renomeados = 0
    for (lid,) in db.query(Loja.id).all():
        criados += seed_perfis_loja(db, lid)
    for p in db.query(PerfilAcesso).filter_by(slug="gerencial", nome="Gerencial").all():
        p.nome = "Gerente"
        renomeados += 1
    # 2026-07-24: operador de SISTEMA perde o módulo fiscal (perfil custom não é tocado)
    ajustados = 0
    for p in db.query(PerfilAcesso).filter_by(slug="operador", sistema=1).all():
        mods = json.loads(p.modulos_json or "[]")
        if "fiscal" in mods:
            p.modulos_json = json.dumps([m for m in mods if m != "fiscal"])
            ajustados += 1
    renomeados += ajustados
    db.commit()
    if criados or renomeados:
        from auth import perfis as _perfis
        _perfis.recarregar()
    return {"criados": criados, "renomeados": renomeados}


def perfis_da_loja(db, loja_id):
    """Lista os PerfilAcesso de uma loja (ordenados: sistema primeiro, depois por nome)."""
    return (db.query(PerfilAcesso).filter_by(loja_id=loja_id)
            .order_by(PerfilAcesso.sistema.desc(), PerfilAcesso.nome).all())


def criar_perfil(db, loja_id, nome, base, modulos, capacidades=None):
    base = base or "operador"   # 'base' é detalhe interno (fonte do desconto_max, diferido); não aparece na UI
    ok, err = mod_perfis.validar_nome(nome)
    if not ok: return None, err
    ok, err = mod_perfis.validar_base(base)
    if not ok: return None, err
    ok, err = mod_perfis.validar_modulos(modulos)
    if not ok: return None, err
    ok, caps = mod_perfis.validar_capacidades(capacidades)
    if not ok: return None, caps
    existentes = {p.slug for p in db.query(PerfilAcesso).all()}   # slug único GLOBAL
    slug = mod_perfis.gerar_slug(nome, existentes)
    p = PerfilAcesso(loja_id=loja_id, slug=slug, nome=nome.strip(), base=base,
                     modulos_json=json.dumps(list(modulos)),
                     capacidades_json=json.dumps(caps), sistema=0)
    db.add(p); db.commit()
    # invalida o cache AQUI (não só na rota): quem criar perfil por outro caminho — teste,
    # seed futuro — deixava slugs_da_loja/rotulo() servindo o registro velho (bug 2026-07-22)
    from auth import perfis as _perfis
    _perfis.recarregar()
    return p, ""


def editar_perfil(db, loja_id, slug, nome=None, modulos=None, capacidades=None):
    p = db.query(PerfilAcesso).filter_by(loja_id=loja_id, slug=slug).first()
    if not p: return None, "perfil não encontrado"
    if p.sistema: return None, "perfil de sistema não é editável"
    if nome is not None:
        ok, err = mod_perfis.validar_nome(nome)
        if not ok: return None, err
        p.nome = nome.strip()
    if modulos is not None:
        ok, err = mod_perfis.validar_modulos(modulos)
        if not ok: return None, err
        p.modulos_json = json.dumps(list(modulos))
    if capacidades is not None:
        ok, caps = mod_perfis.validar_capacidades(capacidades)
        if not ok: return None, caps
        p.capacidades_json = json.dumps(caps)
    db.commit()
    return p, ""
