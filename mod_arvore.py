# -*- coding: utf-8 -*-
"""mod_arvore.py — Visão estrutural (árvore) para papéis administrativos.

Leitura SEM PII: recebe (db, ator, ...) e devolve listas de dicts com
estrutura/indicadores (nunca cliente/cpf/contato/valores). Escopo validado via
mod_tenancy.pode_ver_loja. Erros viram exceções que a rota traduz em HTTP:
  PermissionError -> 403   |   LookupError -> 404
"""

import mod_ciclo
import mod_tenancy
from database import Loja, Projeto, CicloEtapa


def _loja_no_escopo(db, ator, loja_id):
    loja = db.get(Loja, loja_id)
    if loja is None:
        raise LookupError("Loja não encontrada.")
    if not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
        raise PermissionError("Sem acesso a esta loja.")
    return loja


def projetos_estruturais(db, ator, loja_id):
    """Lista estrutural dos projetos de uma loja (sem PII)."""
    _loja_no_escopo(db, ator, loja_id)
    projetos = (db.query(Projeto)
                  .filter(Projeto.loja_id == loja_id)
                  .order_by(Projeto.nome_safe)
                  .all())
    nomes = [p.nome_safe for p in projetos]
    etapas = (db.query(CicloEtapa)
                .filter(CicloEtapa.projeto_nome.in_(nomes)).all()) if nomes else []
    status_por_projeto = {}
    for e in etapas:
        status_por_projeto.setdefault(e.projeto_nome, {})[e.etapa_codigo] = e.status

    out = []
    for p in projetos:
        por_codigo = status_por_projeto.get(p.nome_safe, {})
        # etapa_concluida_agregada (achado 2026-08-18): "13" só conta como concluída quando
        # TODO o grupo "Logística e Expedição" (13-16) está.
        concluidas = sum(
            1 for cod in mod_ciclo.ETAPAS_PRINCIPAIS
            if mod_ciclo.etapa_concluida_agregada(cod, por_codigo))
        atual = next(
            (cod for cod in mod_ciclo.ETAPAS_PRINCIPAIS
             if not mod_ciclo.etapa_concluida_agregada(cod, por_codigo)), None)
        out.append({
            "nome_safe": p.nome_safe,
            "status": p.status,
            "etapa_atual_codigo": atual,
            "etapa_atual_nome": mod_ciclo.ETAPA_NOME.get(atual) if atual else None,
            "total_etapas": len(mod_ciclo.ETAPAS_PRINCIPAIS),
            "etapas_concluidas": concluidas,
        })
    return out


def etapas_do_projeto(db, ator, nome_safe):
    """Etapas do ciclo de um projeto (sem PII)."""
    proj = db.get(Projeto, nome_safe)
    if proj is None:
        raise LookupError("Projeto não encontrado.")
    loja = db.get(Loja, proj.loja_id) if proj.loja_id is not None else None
    rede_id = loja.rede_id if loja is not None else None
    if not mod_tenancy.pode_ver_loja(ator, {"id": proj.loja_id, "rede_id": rede_id}):
        raise PermissionError("Sem acesso a este projeto.")
    etapas = (db.query(CicloEtapa)
                .filter(CicloEtapa.projeto_nome == nome_safe).all())
    etapas.sort(key=lambda e: mod_ciclo.chave_ordenacao(e.etapa_codigo))
    return [{
        "etapa_codigo": e.etapa_codigo,
        "etapa_nome": mod_ciclo.ETAPA_NOME.get(e.etapa_codigo, e.etapa_codigo),
        "status": e.status,
        "concluido_em": e.concluido_em.isoformat() if e.concluido_em else None,
    } for e in etapas]
