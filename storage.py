"""
storage.py — Camada de armazenamento, configuração, perfis e sessão.
Para migrar para nuvem: substituir apenas as funções storage_*() e session_*().
"""
import os, json, re, hashlib, unicodedata
import sys

# == CONSTANTES E CAMINHOS ==
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE       = os.path.join(_BASE_DIR, "omie_config.json")
GRUPOS_CACHE_FILE = os.path.join(_BASE_DIR, "omie_grupos_cache.json")
PROJETOS_DIR      = os.path.join(_BASE_DIR, "PROJETOS")
PERFIS_FILE       = os.path.join(_BASE_DIR, "perfis_config.json")
CPF_CORINGA       = "00000000191"

# == STORAGE LAYER ==
# Camada de abstração de armazenamento.
# Backend local: lê/escreve em disco.
# Para nuvem: substituir apenas estas funções por S3/GCS/Supabase Storage.
# NUNCA usar open(), os.makedirs() ou shutil fora desta seção.

STORAGE_BACKEND = "local"

def storage_ler_json(caminho: str) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)

def storage_salvar_json(caminho: str, dados: dict) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def storage_salvar_texto(caminho: str, conteudo: str) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)

def storage_salvar_binario(caminho: str, conteudo: bytes) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(conteudo)

def storage_ler_texto(caminho: str) -> str:
    with open(caminho, encoding="utf-8") as f:
        return f.read()

def storage_ler_binario(caminho: str) -> bytes:
    with open(caminho, "rb") as f:
        return f.read()

def storage_deletar(caminho: str) -> None:
    if os.path.exists(caminho):
        os.remove(caminho)

def storage_listar(pasta: str) -> list:
    """Retorna lista de nomes de itens (pastas ou arquivos) diretos em pasta."""
    if not os.path.isdir(pasta):
        return []
    return sorted(os.listdir(pasta))

def storage_existe(caminho: str) -> bool:
    return os.path.exists(caminho)

# == CONFIG LAYER ==
# Configurações do aplicativo (credenciais, intervalo de API).
# Em produção local: arquivo omie_config.json em disco.
# Para nuvem: substituir por os.environ ou serviço de segredos.
# NUNCA commitar omie_config.json — adicioná-lo ao .gitignore.

def config_carregar() -> dict:
    padrao = {"app_key": "", "app_secret": "", "intervalo": 0.5}
    if storage_existe(CONFIG_FILE):
        return storage_ler_json(CONFIG_FILE)
    # Cria o arquivo com valores vazios na primeira execução
    storage_salvar_json(CONFIG_FILE, padrao)
    return padrao

def config_salvar(cfg: dict) -> None:
    storage_salvar_json(CONFIG_FILE, cfg)

# == PERFIS DE ACESSO E LIMITES ==
# Controle de permissões por perfil de usuário.
# Local: arquivo perfis_config.json em disco.
# Para nuvem: substituir por banco de dados com autenticação JWT/OAuth.
# Os perfis definem limites máximos de desconto por nível hierárquico.
# Estrutura preparada para multi-usuário em nuvem — cada sessão terá
# um perfil associado via token de autenticação.

PERFIS_FILE = os.path.join(_BASE_DIR, "perfis_config.json")

PERFIS_PADRAO = {
    "perfil_ativo": "consultor",   # perfil em uso (local: único usuário)
    "perfis": {
        "consultor": {
            "nome":              "Consultor de Vendas",
            "desconto_max_pct":  10.0,   # desconto máximo permitido (global + individual)
            "pode_editar_total": True,   # pode editar o Total do Contrato diretamente
            "pode_ver_margens":  False,  # vê o painel de apoio (margens internas)
            "cor":               "#19c9a0"
        },
        "gerente": {
            "nome":              "Gerente de Vendas",
            "desconto_max_pct":  20.0,
            "pode_editar_total": True,
            "pode_ver_margens":  True,
            "cor":               "#f0a500",
            "senha_gerente":     "1234"
        },
        "diretoria": {
            "nome":              "Diretoria",
            "desconto_max_pct":  100.0,  # sem limite prático
            "pode_editar_total": True,
            "pode_ver_margens":  True,
            "cor":               "#e8611a"
        }
    }
}

def perfis_carregar() -> dict:
    if storage_existe(PERFIS_FILE):
        dados = storage_ler_json(PERFIS_FILE)
        # Merge com padrão para garantir que novos campos existam
        for perfil, cfg in PERFIS_PADRAO["perfis"].items():
            if perfil not in dados.get("perfis", {}):
                dados.setdefault("perfis", {})[perfil] = cfg
        return dados
    storage_salvar_json(PERFIS_FILE, PERFIS_PADRAO)
    return PERFIS_PADRAO.copy()

def perfis_salvar(dados: dict) -> None:
    storage_salvar_json(PERFIS_FILE, dados)

def perfil_ativo_get() -> dict:
    dados = perfis_carregar()
    nome_perfil = dados.get("perfil_ativo", "consultor")
    return dados["perfis"].get(nome_perfil, PERFIS_PADRAO["perfis"]["consultor"])

def perfil_desconto_max() -> float:
    return float(perfil_ativo_get().get("desconto_max_pct", 10.0))

# == SESSION LAYER ==
# Estado da sessão do usuário.
# Local: dicionário Python em memória (um usuário por vez).
# Para nuvem: substituir por Redis ou cookies assinados.
# NUNCA acessar _session diretamente fora desta seção.

_session: dict = {
    "running": False,
    "logs": [],
    "pedidos": [],
    "confirm_pending": None,
    "confirm_result": None,
    "cliente_selecionado": None,
    "confirm_event": None,
    "cancel": False,
    "dados_carregados": None,
    "xmls_carregados": None,
    "nome_cliente": None,
    "excel_atual_caminho": None,
    "idx_negociacao": None,
    "projeto_ativo": None,
}

def session_get(chave: str, padrao=None):
    return _session.get(chave, padrao)

def session_set(chave: str, valor) -> None:
    _session[chave] = valor

def session_reset_exportacao() -> None:
    for k, v in [("running", False), ("logs", []), ("pedidos", []),
                 ("confirm_pending", None), ("confirm_result", None),
                 ("confirm_event", None), ("cancel", False)]:
        _session[k] = v

# -- Helpers basicos ------------------------------------------------------------
def _sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def normalizar(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").upper().strip()

def so_digitos(s):
    return re.sub(r"[^0-9]", "", s or "")

# -- Cache de grupos ------------------------------------------------------------
def _load_grupos_cache():
    if storage_existe(GRUPOS_CACHE_FILE):
        try:
            return storage_ler_json(GRUPOS_CACHE_FILE)
        except Exception:
            pass
    return {}

def _save_grupos_cache(cache):
    storage_salvar_json(GRUPOS_CACHE_FILE, cache)

_grupos_cache = _load_grupos_cache()

# -- Credenciais e rate limit ---------------------------------------------------
_sleep_interval = [0.5]
_omie_key       = [""]
_omie_secret    = [""]

def _set_credenciais(app_key, app_secret):
    _omie_key[0]    = app_key
    _omie_secret[0] = app_secret

def get_omie_key() -> str:
    return _omie_key[0]

def get_omie_secret() -> str:
    return _omie_secret[0]

def get_sleep_interval() -> float:
    return _sleep_interval[0]

def set_sleep_interval(val: float) -> None:
    _sleep_interval[0] = val
