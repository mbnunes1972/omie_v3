# -*- coding: utf-8 -*-
"""F2-26 (05/09) — trava anti-NF-e-real no repositório.

Duas vezes em três dias uma NF-e REAL quase entrou por um `git add -A` numa pasta que ganhou
arquivos sem ninguém notar: `tests/fixtures/nfe/` em 04/09, `XML/Nfe/` em 05/09 (este chegou a
ser commitado localmente e foi desfeito antes do push). O sintoma é o mesmo das varreduras
anti-órfão que já existem no repo (`test_arquitetura_modulos.py`, `test_orfaos_gabarito.py`):
silêncio — ninguém PERCEBE o arquivo chegando, só depois de já ter quase saído do controle.

Varre a ÁRVORE VERSIONADA (`git ls-files`, não o disco — arquivo não commitado ainda não é o
risco que os dois incidentes descrevem) procurando XML com CHAVE DE NF-e:
  - nome do arquivo = exatamente 44 dígitos (convenção da Focus/SEFAZ, confirmada em
    `nfe_amostras/`, que já é gitignored — não aparece aqui de propósito); ou
  - conteúdo com `<infNFe ... Id="NFe<44 dígitos>">` (a chave embutida no atributo Id; a ordem
    real dos atributos NFe é `versao` ANTES de `Id` — um literal `<infNFe Id=` nunca aparece em
    NF-e nenhuma, real ou fake; por isso o regex procura o atributo em qualquer posição da tag).

`nfe_amostras/` é excluída explicitamente (redundante com o `.gitignore`, mas documenta a
intenção — defesa em profundidade). As DUAS fixtures sintéticas de teste
(`tests/fixtures/nfe/nfe_basica.xml`/`nfe_sem_ipi.xml`) são auditadas e permitidas por
ALLOWLIST NOMEADA: usam CNPJ/razão social óbvios ("FABRICA TESTE LTDA"/"LOJA TESTE LTDA") e
chave placeholder (zeros) — a mesma ideia das outras exclusões explícitas e comentadas do
código (`_PROV_PAINEL_EXCLUI`, `_PROV_FORA_DO_VEREDITO`), nunca um padrão numérico "parece
fake" (chave toda zero PASSA no dígito verificador por coincidência — não dá pra confiar em
heurística de conteúdo aqui, só em allowlist auditada por arquivo)."""
import os
import re
import subprocess

REPO = os.path.join(os.path.dirname(__file__), "..")

_ALLOWLIST_FIXTURES_SINTETICAS = {
    "tests/fixtures/nfe/nfe_basica.xml",
    "tests/fixtures/nfe/nfe_sem_ipi.xml",
}

_RE_CHAVE_NO_NOME = re.compile(r"^\d{44}$")
_RE_ID_INFNFE = re.compile(r'<infNFe\b[^>]*\sId="NFe(\d{44})"')


def _arquivos_versionados():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True)
    return [p for p in out.stdout.decode("utf-8").split("\0") if p]


def test_nenhuma_nfe_real_versionada_fora_de_nfe_amostras():
    ofensores = []
    for rel in _arquivos_versionados():
        if not rel.lower().endswith(".xml"):
            continue
        if rel.startswith("nfe_amostras/"):
            continue   # já gitignored — exclusão explícita aqui é defesa em profundidade
        if rel in _ALLOWLIST_FIXTURES_SINTETICAS:
            continue
        nome = os.path.basename(rel)
        base, _ext = os.path.splitext(nome)
        if _RE_CHAVE_NO_NOME.match(base):
            ofensores.append("%s — nome do arquivo é uma chave de NF-e (44 dígitos)" % rel)
            continue
        caminho_abs = os.path.join(REPO, rel)
        try:
            conteudo = open(caminho_abs, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        m = _RE_ID_INFNFE.search(conteudo)
        if m:
            ofensores.append('%s — <infNFe Id="NFe%s"> no conteúdo' % (rel, m.group(1)))
    assert not ofensores, (
        "NF-e real (ou chave real) versionada fora de nfe_amostras/ — mesma classe dos "
        "incidentes de 04/09 (tests/fixtures/nfe/) e 05/09 (XML/Nfe/):\n  " + "\n  ".join(ofensores))


def test_allowlist_das_fixtures_sinteticas_continua_existindo_e_e_minima():
    """Controle: a allowlist não pode crescer em silêncio nem apontar pra arquivo que sumiu —
    se um dia ela precisar de um 3º item, alguém tem que decidir isso de propósito, não deixar
    a lista desatualizar sozinha."""
    for rel in _ALLOWLIST_FIXTURES_SINTETICAS:
        assert os.path.isfile(os.path.join(REPO, rel)), (
            "allowlist aponta pra arquivo que não existe mais: %s — remova da lista" % rel)
    assert len(_ALLOWLIST_FIXTURES_SINTETICAS) == 2
