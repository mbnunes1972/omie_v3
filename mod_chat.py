# -*- coding: utf-8 -*-
"""Shim de compatibilidade (empacotamento 2026-07-31): o código vive em chat/core.py.
Importar `mod_chat` (main.py, testes) continua funcionando — este shim faz o BOOTSTRAP das
portas do host (chat_host) e entrega o módulo real no lugar deste."""
import sys as _sys

import chat_host  # noqa: F401  (registra as portas host→chat antes de qualquer uso)
from chat import core as _core

_sys.modules[__name__] = _core
