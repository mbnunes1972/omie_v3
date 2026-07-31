# -*- coding: utf-8 -*-
"""chat_host.py — adaptadores do HOST (OrizonOne) para as portas do módulo chat
(spec _geral/2026-07-31-chat-modulo-destacavel-portas-design.md). Direção permitida:
host → chat. O módulo chat nunca importa daqui — ele consome via chat/ports.py."""
from chat import ports


def registrar_portas():
    """Idempotente: liga as portas do chat às implementações do OrizonOne."""
    from auth import perfis
    ports.registrar("identity.pode", perfis.pode)


registrar_portas()
