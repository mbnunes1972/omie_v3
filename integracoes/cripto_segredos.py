"""cripto_segredos.py — criptografia em repouso de segredos de integração externa (tokens Focus,
D4Sign, etc.). Utilitário GENÉRICO (não é fiscal-exclusivo, apesar de ter nascido em fiscal/ e do
nome da chave/env manter o histórico) — mora em integracoes/ (núcleo, sem depende_de) justamente
pra qualquer domínio poder reusar sem violar o ratchet de fronteira entre módulos.
`fiscal/fiscal_cripto.py` é hoje um shim de compatibilidade em cima deste módulo.

A chave vive FORA do banco (env ORIZON_FISCAL_KEY ou keyfile). Migrar para KMS depois não deve
tocar chamadores. NUNCA loga texto plano nem a chave."""
import os
import logging
from cryptography.fernet import Fernet

try:
    from storage import _BASE_DIR
except ImportError:
    # DOIS dirname: este arquivo vive em integracoes/, e config/ está na RAIZ.
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_KEYFILE = os.path.join(_BASE_DIR, "config", "fiscal.key")


def gerar_chave() -> str:
    """Chave Fernet nova (base64 urlsafe). Utilitário de setup."""
    return Fernet.generate_key().decode()


def _key_bytes():
    env = os.environ.get("ORIZON_FISCAL_KEY")
    if env:
        return env.encode()
    if os.path.exists(_KEYFILE):
        with open(_KEYFILE, "rb") as f:
            return f.read().strip()
    chave = Fernet.generate_key()
    os.makedirs(os.path.dirname(_KEYFILE), exist_ok=True)
    with open(_KEYFILE, "wb") as f:
        f.write(chave)
    try:
        os.chmod(_KEYFILE, 0o600)
    except OSError:
        pass
    logging.getLogger(__name__).warning("chave de segredos gerada em %s", _KEYFILE)
    return chave


def _fernet():
    # Sem cache: lê a chave a cada chamada (barato) → sempre respeita o env atual (testes limpos).
    return Fernet(_key_bytes())


def encrypt(texto):
    """texto plano -> ciphertext (str). '' / None -> None."""
    if not texto:
        return None
    return _fernet().encrypt(texto.encode()).decode()


def decrypt(token):
    """ciphertext -> texto plano. None/'' -> None. Token adulterado levanta InvalidToken."""
    if not token:
        return None
    return _fernet().decrypt(token.encode()).decode()


def token_definido(enc) -> bool:
    return bool(enc)
