# -*- coding: utf-8 -*-
"""chat/ports.py — o CONTRATO entre o módulo chat e o host (spec
_geral/2026-07-31-chat-modulo-destacavel-portas-design.md, decisão 7).

O chat NÃO importa módulos do host (mod_ciclo, mod_equipe, auth, …) — o ratchet em
test_arquitetura_modulos proíbe. O host implementa e REGISTRA os adaptadores aqui
(ver chat_host.py na raiz); o chat consome pelas funções nomeadas abaixo. É isso que
torna o módulo destacável: num cliente externo, outro host registra outras portas.

Portas do contrato (registradas por nome):
- identity.pode(nivel, capacidade) -> bool         [IdentityPort — permissões]
- tenancy.escopo(ator) -> (loja_id, erro)          [TenancyPort — reservada; handlers do host]
- assunto.resolver(tipo, ref) -> {tipo,id,titulo}  [AssuntoPort — reservada; âncora genérica]
- storage.salvar/abrir                             [StoragePort — reservada]
- notify.email(...)                                [NotifyPort — reservada]

EventosPort é o barramento in-process abaixo (assinar/emitir): o host emite
fase_alterada/responsavel_alterado/documento_anexado; o chat emite mensagem_recebida/
triagem_pendente/atendimento_concluido. Handlers são best-effort — evento nunca derruba
a operação que o emitiu."""

_PORTAS = {}
_ASSINANTES = {}


def registrar(nome, impl):
    """Host registra o adaptador de uma porta (ex.: registrar('identity.pode', perfis.pode))."""
    _PORTAS[nome] = impl


def porta(nome):
    impl = _PORTAS.get(nome)
    if impl is None:
        raise RuntimeError(
            "Porta '%s' não registrada — o host precisa registrar os adaptadores do chat "
            "(import de mod_chat/mod_chat_externo, ou chat_host.registrar_portas())." % nome)
    return impl


def identity_pode(nivel, capacidade):
    """IdentityPort: o usuário deste nível tem a capacidade? (no OrizonOne: auth.perfis.pode)"""
    return porta("identity.pode")(nivel, capacidade)


# ── EventosPort: pub/sub in-process simples (sem broker) ─────────────────────

def assinar(evento, fn):
    _ASSINANTES.setdefault(evento, []).append(fn)


def emitir(evento, **dados):
    """Emite um evento aos assinantes. BEST-EFFORT: handler que falha não derruba o emissor
    (mesmo padrão do espelhamento externo). Retorna quantos handlers rodaram sem erro."""
    ok = 0
    for fn in _ASSINANTES.get(evento, []):
        try:
            fn(**dados)
            ok += 1
        except Exception:
            pass
    return ok
