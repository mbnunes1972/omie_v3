"""fiscal_cripto.py — shim de compatibilidade: a criptografia de segredos (tokens Focus) foi
generalizada pra integracoes/cripto_segredos.py (2026-08-11), pra outros domínios (ClickSign)
poderem reusar sem violar o ratchet de fronteira entre módulos. Chamadores existentes (main.py,
fiscal/mod_fiscal.py, testes) continuam importando daqui — reexporta 1:1, sem lógica própria."""
from integracoes.cripto_segredos import (   # noqa: F401 — reexport de compatibilidade
    gerar_chave, encrypt, decrypt, token_definido, _KEYFILE, _key_bytes, _fernet,
)
