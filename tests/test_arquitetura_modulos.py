import sys, os, ast, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import modulos as m

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PY_RAIZ = {p.name for p in RAIZ.glob("*.py")}

# Pacotes locais (dir com __init__.py) detectados, não hardcoded: antes havia um
# `| {"mod_fin"}` na mão, que só o mod_fin ganhava — qualquer pacote novo ficava
# invisível para os testes de dependência abaixo.
PACOTES_LOCAIS = {d.name for d in RAIZ.iterdir()
                  if d.is_dir() and (d / "__init__.py").exists()}
NOMES_LOCAIS = {p.stem for p in RAIZ.glob("*.py")} | PACOTES_LOCAIS


def _arquivos_do_modulo(nome):
    """Arquivos do módulo. Entrada que é PACOTE (diretório) expande para os .py de dentro.

    Sem essa expansão, os testes de dependência (que fazem `if not
    arquivo.endswith(".py"): continue`) PULAVAM o pacote inteiro — o ratchet ficava
    verde sem checar uma linha do que está lá dentro. Era o caso do mod_fin desde
    que virou pacote: nunca foi verificado.
    """
    out = set()
    for a in m.MODULOS[nome]["arquivos"]:
        p = RAIZ / a
        if p.is_dir():
            out |= {f.relative_to(RAIZ).as_posix() for f in p.rglob("*.py")}
        else:
            out.add(a)
    return out


def _imports_locais(arquivo):
    """Módulos-locais (nome-base) importados por `arquivo`, top-level e dentro de funções."""
    tree = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))
    achados = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                b = a.name.split(".")[0]
                if b in NOMES_LOCAIS:
                    achados.add(b)
        elif isinstance(node, ast.ImportFrom) and node.module:
            b = node.module.split(".")[0]
            if b in NOMES_LOCAIS:
                achados.add(b)
    return achados


def test_todo_py_esta_classificado():
    """Todo .py da raiz pertence a um módulo OU está na allowlist de shell — sem órfãos."""
    classificados = set()
    for v in m.MODULOS.values():
        for a in v["arquivos"]:
            if a.endswith(".py"):
                classificados.add(a)
    orfaos = PY_RAIZ - classificados - m.SHELL
    assert not orfaos, f"arquivos sem módulo (classifique em modulos.py ou SHELL): {sorted(orfaos)}"


def test_todo_arquivo_do_manifesto_existe():
    for nome, v in m.MODULOS.items():
        for a in v["arquivos"]:
            alvo = RAIZ / a
            assert alvo.exists(), f"{nome}: arquivo inexistente no manifesto: {a}"


def test_nucleo_nao_importa_dominio():
    """Regra de dependência: Núcleo NÃO pode importar módulo de domínio."""
    arqs_dominio = {a for d in m.DOMINIOS for a in _arquivos_do_modulo(d)}
    violacoes = []
    for nome in m.NUCLEO:
        for arquivo in _arquivos_do_modulo(nome):
            if not arquivo.endswith(".py"):
                continue
            for imp in _imports_locais(arquivo):
                if (imp + ".py") in arqs_dominio:
                    violacoes.append(f"{arquivo} (núcleo/{nome}) importa {imp} (domínio)")
    assert not violacoes, "Núcleo importando domínio:\n" + "\n".join(violacoes)


def test_dominios_so_importam_o_que_declaram():
    """Ratchet: um módulo de domínio só importa arquivos do próprio módulo, do Núcleo, dos módulos
    em depende_de, dos compartilhados, ou shell. Qualquer import cruzado NÃO declarado falha."""
    dono = {}
    for nome, v in m.MODULOS.items():
        for a in v["arquivos"]:
            dono[a] = nome
            # Pacote: registra também o nome-base, porque um `from fiscal import X`
            # chega aqui como o import de "fiscal", não de "fiscal.py".
            if (RAIZ / a).is_dir():
                dono[pathlib.Path(a).name] = nome
    violacoes = []
    for nome in m.DOMINIOS:
        permitidos = set(m.MODULOS[nome]["depende_de"]) | m.NUCLEO | {nome}
        for arquivo in _arquivos_do_modulo(nome):
            if not arquivo.endswith(".py"):
                continue
            for imp in _imports_locais(arquivo):
                impfile = imp + ".py"
                mod_imp = dono.get(impfile) or dono.get(imp)
                if mod_imp is None:
                    continue  # shell/tool/local não-modular
                if mod_imp in permitidos:
                    continue
                if impfile in m.COMPARTILHADOS and nome in m.COMPARTILHADOS[impfile]:
                    continue
                violacoes.append(f"{arquivo} ({nome}) importa {imp} ({mod_imp}) — não declarado em depende_de")
    assert not violacoes, "Import cruzado não declarado:\n" + "\n".join(violacoes)


def test_tabelas_batem_com_o_schema():
    """Toda tabela do manifesto existe em database.py e toda tabela do schema está classificada."""
    import database
    tabelas_schema = set(database.Base.metadata.tables.keys())
    tabelas_manifesto = {t for v in m.MODULOS.values() for t in v["tabelas"]}
    faltando_no_schema = tabelas_manifesto - tabelas_schema
    assert not faltando_no_schema, f"manifesto cita tabela inexistente: {sorted(faltando_no_schema)}"
    nao_classificadas = tabelas_schema - tabelas_manifesto
    assert not nao_classificadas, f"tabela sem módulo no manifesto: {sorted(nao_classificadas)}"


def test_chat_pacote_nao_importa_host():
    """Ratchet do MÓDULO DESTACÁVEL (spec _geral/2026-07-31-chat-modulo-destacavel-portas):
    dentro de chat/ só entram stdlib, libs e o SCHEMA compartilhado (database) — nenhum módulo
    do host (mod_*, auth, main, storage, fiscal, …). O host fala com o chat importando-o
    (direção host→chat é livre); o chat fala com o host SÓ pelas portas (chat/ports.py,
    adaptadores registrados em chat_host.py). Sem este ratchet o desacoplamento regride em
    três commits."""
    PERMITIDOS = {"chat", "database"}
    violacoes = []
    for f in sorted((RAIZ / "chat").rglob("*.py")):
        rel = f.relative_to(RAIZ).as_posix()
        for imp in _imports_locais(rel):
            if imp not in PERMITIDOS:
                violacoes.append(f"{rel} importa {imp} — use uma porta (chat/ports.py)")
    assert not violacoes, "chat/ acoplado ao host:\n" + "\n".join(violacoes)
