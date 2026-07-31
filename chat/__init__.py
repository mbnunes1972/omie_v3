# -*- coding: utf-8 -*-
"""Pacote `chat/` — Orizon Chat como módulo DESTACÁVEL (spec
_geral/2026-07-31-chat-modulo-destacavel-portas-design.md).

- core.py    — conversas, mensagens, participantes, templates, config (ex-mod_chat.py)
- externo.py — transportes WhatsApp/e-mail, roteamento de entrada, janela 24h (ex-mod_chat_externo.py)
- triagem.py — fila de triagem humana (persistida em externo.processar_entrada)
- ports.py   — contrato host↔chat (Identity/Tenancy/Assunto/Eventos/Storage/Notify)

O chat não importa módulos do host (ratchet em test_arquitetura_modulos); o host registra os
adaptadores em chat_host.py (raiz). Os shims mod_chat.py/mod_chat_externo.py na raiz mantêm os
imports antigos funcionando E fazem o bootstrap das portas."""
