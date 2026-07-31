# -*- coding: utf-8 -*-
"""Shim de compatibilidade (empacotamento 2026-07-31): o código vive em chat/externo.py
(+ chat/triagem.py, reexportada lá). Ver mod_chat.py — mesmo padrão de bootstrap."""
import sys as _sys

import chat_host  # noqa: F401  (registra as portas host→chat antes de qualquer uso)
from chat import externo as _externo

_sys.modules[__name__] = _externo
