import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture(autouse=True)
def _sem_rate_limit_de_login_entre_testes():
    """O rate limiter de login (achado de auditoria 2026-08-13) guarda estado em memória de
    PROCESSO (`auth.auth._LOGIN_TENTATIVAS`) — correto em produção (1 processo por instância),
    mas a suíte inteira roda num processo só e reusa um punhado de logins do seed (dir_l1, super,
    cons_l1...) em milhares de testes. Sem isto, falhas de login intencionais em um arquivo
    (ex. senha errada testada de propósito) se acumulam e derrubam logins LEGÍTIMOS de outro
    arquivo bem depois na mesma rodada — falso positivo de teste, não bug do rate limit em si."""
    from auth import auth as _auth
    with _auth._LOGIN_LOCK:
        _auth._LOGIN_TENTATIVAS.clear()
    yield
    with _auth._LOGIN_LOCK:
        _auth._LOGIN_TENTATIVAS.clear()


@pytest.fixture(autouse=True)
def _sem_credenciais_de_canal_externo_ao_vivo(monkeypatch):
    """P6 — hermeticidade (docs/db/TAREFA_BATERIA_CICLO.md, item 0): `chat/externo.py` lê
    ORIZON_WA_*/ORIZON_SMTP_* direto do ambiente (`meio_configurado`); com o `.env` do
    desenvolvedor carregado (credenciais reais de WhatsApp/SMTP), test_chat_wa e
    test_comunicacao viravam tentativa de envio AO VIVO em vez de 'pendente_config' — a
    suíte com dois vermelhos permanentes ensinava a ignorar vermelho. Testes que precisam
    simular canal configurado já fazem `monkeypatch.setenv` explicitamente (ver
    tests/test_chat_externo.py) — isso continua funcionando, pois roda DEPOIS deste
    autouse no mesmo `monkeypatch`. Os que não fazem devem rodar como se nenhuma
    credencial existisse, não como se o `.env` de quem roda a suíte estivesse configurado."""
    for var in ("ORIZON_WA_TOKEN", "ORIZON_WA_PHONE_ID", "ORIZON_WA_APP_SECRET",
                "ORIZON_WA_VERIFY_TOKEN", "ORIZON_SMTP_HOST", "ORIZON_SMTP_PORT",
                "ORIZON_SMTP_USER", "ORIZON_SMTP_PASS", "ORIZON_SMTP_FROM"):
        monkeypatch.delenv(var, raising=False)


def _test_database_url():
    """URL do banco de TESTE (sempre Postgres — o SQLite saiu da suíte na faxina 2026-07-23).

    Precedência: TEST_DATABASE_URL explícita; senão deriva do DATABASE_URL do `.env`
    trocando o database por `orizon_test` (mesmas credenciais do dev local). NUNCA
    aponte para o banco de dev/produção: o setup dá DROP SCHEMA CASCADE por módulo."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        import re as _re
        with open(env_path, encoding="utf-8") as f:
            m = _re.search(r"DATABASE_URL\s*=\s*['\"]?(postgresql[^'\"\s]+)", f.read())
        if m:
            base = m.group(1)
            return base.rsplit("/", 1)[0] + "/orizon_test"
    raise RuntimeError(
        "Suíte exige Postgres: defina TEST_DATABASE_URL (banco DEDICADO, ex. orizon_test) "
        "ou tenha um .env com DATABASE_URL Postgres para derivar o orizon_test.")


def _reset_schema_pg(engine):
    """Derruba e recria o schema `public` do banco de TESTE.

    drop_all() falharia: há FK circular real no schema (ex.: Usuario.funcionario_id <->
    Funcionario.usuario_id) que o SQLAlchemy não consegue ordenar pra DROP. O CASCADE
    resolve a ordem sozinho.

    Antes do DROP: mata qualquer outra conexão pendurada neste banco de teste (dedicado só
    pra isso). Em Postgres, um SELECT já abre transação de verdade — se um teste anterior
    falhou num assert NO MEIO da função (antes do db.close() do fim), a sessão fica "idle
    in transaction" segurando lock e o DROP SCHEMA trava indefinidamente. Só mata conexões
    do MESMO role (current_user) — pg_terminate_backend em processo de role SUPERUSER
    (ex.: autovacuum) dá InsufficientPrivilege e derruba a query inteira."""
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid() "
            "AND usename = current_user"))
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="module")
def app_db():
    """Rebinda a engine de `database` para o Postgres de TESTE e cria o schema.
    Como get_session/init_db lêem os globais em tempo de chamada, o rebind vale
    para todo o processo (inclusive o servidor em thread). Dropa e recria o schema
    a cada módulo (isolamento equivalente ao antigo arquivo SQLite novo por módulo)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import database

    # guarda os globais originais para restaurar no teardown — assim este módulo
    # não deixa `database` apontando para o banco de teste e quebrando um futuro
    # uso de get_session() fora da suíte.
    orig = (database.ENGINE, database.Session)

    database.ENGINE = create_engine(_test_database_url(), echo=False)
    database.Session = sessionmaker(bind=database.ENGINE)
    _reset_schema_pg(database.ENGINE)

    database.init_db()
    yield database

    database.ENGINE.dispose()
    database.ENGINE, database.Session = orig


@pytest.fixture
def db_pg_limpo(monkeypatch):
    """Banco de teste LIMPO por FUNÇÃO, com init_db completo (loja seed etc.) —
    herdeiro dos antigos SQLite temporários por teste. Rebinda ENGINE/Session via
    monkeypatch (restaura sozinho no teardown). Yield: o módulo `database`."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import database
    eng = create_engine(_test_database_url(), echo=False)
    _reset_schema_pg(eng)
    monkeypatch.setattr(database, "ENGINE", eng)
    monkeypatch.setattr(database, "Session", sessionmaker(bind=eng))
    database.init_db()
    yield database
    eng.dispose()


@pytest.fixture
def db_pg_schema(monkeypatch):
    """Como db_pg_limpo, mas SÓ create_all (schema vazio, sem seed nenhum) — herdeiro
    dos fixtures que faziam create_all num sqlite descartável. Yield: o módulo `database`."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import database
    eng = create_engine(_test_database_url(), echo=False)
    _reset_schema_pg(eng)
    monkeypatch.setattr(database, "ENGINE", eng)
    monkeypatch.setattr(database, "Session", sessionmaker(bind=eng))
    database.Base.metadata.create_all(eng)
    yield database
    eng.dispose()


@pytest.fixture(scope="module")
def seed(app_db):
    """2 lojas na mesma rede; 1 diretor por loja; super_admin e admin_rede;
    e dados cross-loja (1 cliente + 1 projeto em cada loja)."""
    db = app_db.get_session()
    rede = app_db.Rede(nome="Rede Teste")
    db.add(rede); db.flush()

    l1 = app_db.Loja(nome="Loja 1", rede_id=rede.id, codigo="LJ1")
    l2 = app_db.Loja(nome="Loja 2", rede_id=rede.id, codigo="LJ2")
    db.add_all([l1, l2]); db.flush()

    # Semeia os perfis padrão (master/gerencial/operador) por loja — fiel à produção, onde a
    # migração já semeia as lojas reais. Sem isto o registro DB fica vazio e perfis.py cai
    # inteiro no fallback hardcoded, mascarando bugs de wiring por-loja (Task 7).
    from auth import perfil_store
    from auth import perfis as _perfis
    for _lid in (l1.id, l2.id):
        perfil_store.seed_perfis_loja(db, _lid)
    _perfis.recarregar()

    # Emitente próprio de cada loja (identidade fiscal — Task 1/2/4). loja.emitente_id = self.
    def mk_emitente(cnpj, razao, uf="SP"):
        em = app_db.Emitente(cnpj=cnpj, razao_social=razao, regime_tributario="simples",
                             csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102",
                             inscricao_estadual="ISENTO", logradouro="Rua Emit", numero="1",
                             bairro="Centro", cidade="Sao Paulo", uf=uf, cep="01000-000",
                             ambiente_ativo="homologacao")
        db.add(em); db.flush()
        return em
    em1 = mk_emitente("11111111000111", "EMITENTE LOJA 1 LTDA")
    em2 = mk_emitente("22222222000122", "EMITENTE LOJA 2 LTDA")
    l1.emitente_id = em1.id
    l2.emitente_id = em2.id
    db.flush()

    def mkuser(nome, login, nivel, loja_id=None, rede_id=None):
        u = app_db.Usuario(nome=nome, login=login, nivel=nivel,
                           loja_id=loja_id, rede_id=rede_id, ativo=1)
        u.set_senha("senha123")
        db.add(u)

    mkuser("Diretor L1", "dir_l1", "master", loja_id=l1.id)   # Perfil-4: master (era 'diretoria')
    mkuser("Diretor L2", "dir_l2", "master", loja_id=l2.id)
    # Perfil-4/Task 3: 'operador' (era 'consultor') — agora que a regra "só vê os próprios
    # projetos" (main._ve_apenas_proprios_projetos / mod_escopo.escopo_por_posse) é dirigida
    # pela BASE (perfis.base(nivel) == 'operador'), o seed pode usar a base diretamente.
    mkuser("Consultor L1", "cons_l1", "operador", loja_id=l1.id)
    mkuser("Super",      "super",  "super_admin")
    mkuser("Adm Rede",   "adm_rede", "admin_rede", rede_id=rede.id)

    c1 = app_db.Cliente(nome="Cliente L1", cpf="111.444.777-35", loja_id=l1.id)
    c2 = app_db.Cliente(nome="Cliente L2", cpf="222.222.222-22", loja_id=l2.id)
    db.add_all([c1, c2]); db.flush()

    p1 = app_db.Projeto(nome_safe="Proj_L1", cliente_id=c1.id, status="quente", loja_id=l1.id)
    p2 = app_db.Projeto(nome_safe="Proj_L2", cliente_id=c2.id, status="quente", loja_id=l2.id)
    db.add_all([p1, p2]); db.flush()

    o1 = app_db.Orcamento(projeto_id=p1.nome_safe, nome="Orçamento 1", ordem=1, loja_id=l1.id)
    o2 = app_db.Orcamento(projeto_id=p2.nome_safe, nome="Orçamento 1", ordem=1, loja_id=l2.id)
    db.add_all([o1, o2]); db.flush()
    ct1 = app_db.Contrato(projeto_nome=p1.nome_safe, orcamento_id=o1.id, loja_id=l1.id)
    ct2 = app_db.Contrato(projeto_nome=p2.nome_safe, orcamento_id=o2.id, loja_id=l2.id)
    db.add_all([ct1, ct2]); db.flush()

    # Briefing completo para Proj_L2 (necessário para criar orçamentos via POST)
    from datetime import datetime as _dt
    bf2 = app_db.Briefing(
        cliente_id=c2.id,
        projeto_nome=p2.nome_safe,
        data_atendimento=_dt(2026, 1, 1),
        tipo_imovel="apartamento",
        budget_declarado=50000.0,
        categoria_proposta="completo",
        data_entrega_desejada="2026-12-01",
        flexibilidade_prazo="sim",
    )
    db.add(bf2)
    db.commit()

    ctx = {
        "rede_id": rede.id,
        "loja1_id": l1.id, "loja2_id": l2.id,
        "emitente_l1_id": em1.id, "emitente_l2_id": em2.id,
        "cliente_l1_id": c1.id, "cliente_l2_id": c2.id,
        "projeto_l1": "Proj_L1", "projeto_l2": "Proj_L2",
        "orcamento_l1_id": o1.id, "orcamento_l2_id": o2.id,
        "contrato_l1_id": ct1.id,
    }
    db.close()
    return ctx


import json as _json
import threading
import time
import urllib.request
import urllib.error


class HttpClient:
    """Cliente HTTP fininho com cookie jar de 1 sessão (header Cookie reusado)."""
    def __init__(self, base):
        self.base = base
        self.cookie = None
        self.loja_ativa = None   # X-Loja-Ativa opcional

    def _req(self, method, path, body=None):
        data = _json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        if self.loja_ativa is not None:
            req.add_header("X-Loja-Ativa", str(self.loja_ativa))
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            status, raw, headers = resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            status, raw, headers = e.code, e.read(), e.headers
        sc = headers.get("Set-Cookie")
        if sc:
            self.cookie = sc.split(";")[0]
        try:
            out = _json.loads(raw) if raw else None
        except Exception:
            out = raw
        return status, out

    def post_multipart(self, path, files, fields=None):
        """files = {name: (filename, bytes)}; fields = {name: valor}. Para testar uploads."""
        boundary = "orizonTESTboundary1234"
        parts = []
        for k, v in (fields or {}).items():
            parts += [("--" + boundary).encode(),
                      ('Content-Disposition: form-data; name="%s"' % k).encode(),
                      b"", str(v).encode()]
        for name, (fname, data) in files.items():
            parts += [("--" + boundary).encode(),
                      ('Content-Disposition: form-data; name="%s"; filename="%s"' % (name, fname)).encode(),
                      b"Content-Type: application/octet-stream", b"", data]
        parts += [("--" + boundary + "--").encode(), b""]
        body = b"\r\n".join(parts)
        req = urllib.request.Request(self.base + path, data=body, method="POST")
        req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        if self.loja_ativa is not None:
            req.add_header("X-Loja-Ativa", str(self.loja_ativa))
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        try:
            out = _json.loads(raw) if raw else None
        except Exception:
            out = raw
        return status, out

    def get(self, path):             return self._req("GET", path)
    def post(self, path, body=None): return self._req("POST", path, body)
    def put(self, path, body=None):  return self._req("PUT", path, body)
    def patch(self, path, body=None):return self._req("PATCH", path, body)

    def login(self, login, senha):
        return self.post("/api/auth/login", {"login": login, "senha": senha})


@pytest.fixture(scope="module")
def projetos_dir(app_db, seed, tmp_path_factory):
    """Redireciona PROJETOS_DIR (em storage/main/projetos_store) para um diretório temporário,
    deixando o harness hermético quanto a disco — espelha o isolamento do banco.
    Também cria no disco os projetos do seed: a lista de `/projetos` vem do disco e é
    cruzada com `projetos_meta.loja_id`, então o filtro por loja só é exercitável de fato
    se os dois projetos existirem em disco (o de loja 1 deve ser filtrado para a loja 2).
    Depende de `app_db` para garantir que `import main` ocorra após o rebind do banco."""
    import json as _json2
    import storage, main
    from integracoes import projetos_store
    tmp = str(tmp_path_factory.mktemp("projetos"))
    for mod in (storage, main, projetos_store):
        if hasattr(mod, "PROJETOS_DIR"):
            mod.PROJETOS_DIR = tmp
    for nome in (seed["projeto_l1"], seed["projeto_l2"]):
        pasta = os.path.join(tmp, nome)
        os.makedirs(pasta, exist_ok=True)
        with open(os.path.join(pasta, "projeto.json"), "w", encoding="utf-8") as f:
            _json2.dump({"nome_safe": nome, "ambientes": []}, f)
    return tmp


@pytest.fixture(scope="module")
def servidor(app_db, seed, projetos_dir):
    """Sobe main.Handler numa thread, porta efêmera, usando o banco isolado+seed.
    ThreadingHTTPServer (2026-08-08, espelha o main.py real desde o fix da Vera/item 2): usava
    HTTPServer single-thread aqui, que nunca exerceria de fato uma corrida de threads mesmo que
    o servidor de produção virasse concorrente — os testes de concorrência real precisam deste
    fixture já rodando igual à produção."""
    import main
    from http.server import ThreadingHTTPServer

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), main.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/login", timeout=1)
            break
        except urllib.error.HTTPError:
            break
        except Exception:
            time.sleep(0.05)
    yield base
    httpd.shutdown()


@pytest.fixture
def http_client_factory(servidor):
    return lambda: HttpClient(servidor)

# tests/test_e2e_browser_conciliacao_final.py: E2E de Playwright, sobe servidor+navegador de
# verdade e usa o MESMO orizon_test da suíte (sem CREATEDB local pra um banco dedicado — ver
# docs/db/IMPLANTAR.md) via um subprocesso que dá DROP SCHEMA CASCADE nele. Rodar dentro da
# mesma sessão de `pytest -q` colidiria com o app_db/db_pg_limpo de outros módulos disputando
# o mesmo schema ao mesmo tempo — por isso fica fora da coleta padrão. Continua rodável direto
# por caminho: `pytest tests/test_e2e_browser_conciliacao_final.py -v` (collect_ignore só vale
# pra coleta RECURSIVA, não quando o arquivo é passado explicitamente).
collect_ignore = ["test_e2e_browser_conciliacao_final.py"]
