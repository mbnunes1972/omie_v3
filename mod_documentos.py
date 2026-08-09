# -*- coding: utf-8 -*-
"""mod_documentos.py — Registro versionado dos modelos de documento por loja.

Único módulo da frente que fala com o banco (mod_marcadores e
mod_documentos_import são puros).

Regra central: uma versão é IMUTÁVEL. Editar = criar a próxima. Contrato aponta
para a versão que o gerou (Contrato.modelo_versao_id), então regerar um contrato
antigo reproduz as cláusulas originais mesmo que a loja já tenha trocado o modelo.

Fallback: loja sem modelo ativo cai no arquivo global de hoje
(contrato_template/contrato.md) — nada quebra para quem não subiu nada.
"""
import os
import re
import shutil
import hashlib

from sqlalchemy.exc import IntegrityError

from database import DocumentoModelo, DocumentoTipo

TIPOS = ("contrato", "proposta", "termo_aditivo", "aprovacao_pe",
         # 2026-08-09, pedido do usuário: documentos de processo além do contrato/proposta —
         # todos corpo-só (sem capa), mesmo mecanismo genérico de termo_aditivo/aprovacao_pe.
         # A geração PARA UM PROJETO REAL (marcadores preenchidos, botão na tela do projeto)
         # é frente futura — isto aqui só habilita o CADASTRO do modelo em Config > Documentos.
         "termo_vistoria", "termo_responsabilidade", "solicitacao_medicao",
         "checklist_eletros", "autorizacao_foto_video", "carta_agradecimento")

# ── Tipos CUSTOMIZADOS ("Novo Documento", spec 2026-07-22) ────────────────────
# O slug vira componente de DIRETÓRIO em documentos_loja/<loja>/<tipo>/ — a forma
# doc_[a-z0-9_]+ é path-safe por construção, então os pontos db-free (staging)
# validam só a FORMA; a EXISTÊNCIA (slug registrado para a loja) é validada onde
# há sessão de banco (criar_versao / endpoints).
_RE_TIPO_CUSTOM = re.compile(r"^doc_[a-z0-9_]{1,40}$")


def tipo_forma_valida(tipo):
    """Aceita os nativos e a FORMA dos customizados (path-safe). Não consulta o banco."""
    return tipo in TIPOS or bool(_RE_TIPO_CUSTOM.match(tipo or ""))


def _loja_mae_id(db, loja_id):
    """loja_mae_id quando `loja_id` é um PDV (loja com mãe); None caso contrário."""
    from database import Loja
    l = db.get(Loja, loja_id) if loja_id else None
    return getattr(l, "loja_mae_id", None) if l is not None else None


def tipo_existe(db, loja_id, tipo):
    """Nativo, ou slug customizado REGISTRADO para esta loja (PDV: vale o da mãe)."""
    if tipo in TIPOS:
        return True
    if not _RE_TIPO_CUSTOM.match(tipo or ""):
        return False
    if (db.query(DocumentoTipo)
          .filter_by(loja_id=loja_id, slug=tipo).first()) is not None:
        return True
    mae_id = _loja_mae_id(db, loja_id)
    if mae_id:
        return (db.query(DocumentoTipo)
                  .filter_by(loja_id=mae_id, slug=tipo).first()) is not None
    return False


def tipos_customizados(db, loja_id):
    return (db.query(DocumentoTipo).filter_by(loja_id=loja_id)
              .order_by(DocumentoTipo.id.asc()).all())


def _slugificar_nome(nome):
    import unicodedata
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s[:40] or None


def criar_tipo(db, loja_id, nome, etapa_ciclo, usuario_id):
    """Cria um tipo customizado (slug doc_<nome-slugificado>, único por loja).
    Levanta ValueError com mensagem de usuário; NÃO commita (o chamador decide)."""
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Dê um nome ao documento.")
    base = _slugificar_nome(nome)
    if not base:
        raise ValueError("Nome inválido — use letras e números.")
    slug = "doc_" + base
    ja = db.query(DocumentoTipo).filter_by(loja_id=loja_id, slug=slug).first()
    if ja is not None:
        raise ValueError("Já existe um documento com esse nome (%s)." % ja.nome)
    t = DocumentoTipo(loja_id=loja_id, slug=slug, nome=nome,
                      etapa_ciclo=(str(etapa_ciclo).strip() or None) if etapa_ciclo else None,
                      criado_por_id=usuario_id)
    db.add(t)
    db.flush()
    return t

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_LOJA_DIR = os.path.join(_THIS_DIR, "documentos_loja")

# Tentativas de reservar número de versão. N uploads simultâneos da mesma loja podem
# exigir até N-1 retries (cada perdedor recua e relê o MAX). 8 cobre com folga o pior
# caso realista — é um lojista trocando o modelo, não tráfego de máquina.
_MAX_TENTATIVAS_VERSAO = 8


def _validar(tipo, corpo_md):
    if not tipo_forma_valida(tipo):
        raise ValueError("tipo inválido: %r (aceitos: %s ou doc_<slug> customizado)"
                         % (tipo, ", ".join(TIPOS)))
    if not (corpo_md or "").strip():
        raise ValueError("corpo do modelo vazio")


def _proxima_versao(db, loja_id, tipo):
    ultima = (db.query(DocumentoModelo)
                .filter(DocumentoModelo.loja_id == loja_id,
                        DocumentoModelo.tipo == tipo)
                .order_by(DocumentoModelo.versao.desc())
                .first())
    return (ultima.versao + 1) if ultima else 1


def _e_colisao_de_versao(e):
    """A IntegrityError é a colisão de (loja, tipo, versao) — a única retentável?

    Qualquer outra violação (NOT NULL, FK) não se resolve tentando de novo: queimaria
    as tentativas à toa e sairia como "não foi possível reservar número de versão",
    mensagem enganosa. SQLite não cita o nome da constraint na mensagem, só as colunas;
    Postgres cita o nome — os dois formatos são cobertos.
    """
    msg = str(getattr(e, "orig", e))
    baixa = msg.lower()
    if "uq_doc_modelo_versao" in baixa:                       # Postgres
        return True
    return "unique constraint failed" in baixa and "documento_modelos.versao" in baixa


def guardar_staging(loja_id, tipo, origem_nome, conteudo_bytes):
    """Guarda o arquivo subido ANTES de a versão existir.

    A importação analisa sem salvar a versão, então o original fica no staging
    até o lojista ativar; criar_versao o promove para v<N>/. Devolve (caminho, sha256).

    DÉBITO CONHECIDO: o _staging/ não tem limpeza. Quem sobe um modelo e desiste antes
    de criar a versão deixa o arquivo aqui para sempre. Não vaza dado (é escopado por
    loja), mas cresce sem teto — falta uma rotina de expurgo por idade.
    """
    d = os.path.join(DOCS_LOJA_DIR, str(loja_id), tipo, "_staging")
    os.makedirs(d, exist_ok=True)
    sha = hashlib.sha256(conteudo_bytes).hexdigest()
    caminho = os.path.join(d, sha[:16] + os.path.splitext(origem_nome or "")[1].lower())
    with open(caminho, "wb") as fh:
        fh.write(conteudo_bytes)
    return caminho, sha


# Forma do nome que guardar_staging gera: sha256[:16] + extensão minúscula (ou sem
# extensão, quando o arquivo subido não tinha uma). Nada além disso é staging legítimo.
_RE_NOME_STAGING = re.compile(r"^[0-9a-f]{16}(\.[a-z0-9]+)?$")


def resolver_staging(loja_id, tipo, nome_recebido):
    """Caminho real de um staging a partir do nome que o CLIENTE devolveu, ou None.

    Devolve None (nunca levanta) quando o nome não resolve para um arquivo legítimo
    dentro do _staging/ desta loja. None é resposta válida, não erro: origem_path é
    nullable e a versão vale sem trilha de origem.

    NÃO CONFIE EM os.path.basename PARA CONTER O CLIENTE — foi o furo que existiu aqui:
    basename('.') == '.' e basename('..') == '..' (não têm barra, então nada é removido).
    Com '.', o join devolvia o PRÓPRIO diretório _staging/, os.path.exists() dizia True,
    e criar_versao mandava o diretório inteiro — com os uploads pendentes de outras
    importações dentro — para v<N>/ via shutil.move. Com '..', o shutil.Error subia sem
    tratamento e derrubava a conexão. Os dois comprovados por execução contra o servidor
    real antes desta correção; tests/test_documentos_api.py trava os dois vetores.

    Três barreiras, nesta ordem (cada uma sozinha já mataria '.'/'..'; juntas cobrem o
    que a próxima pessoa inventar):
      1. tipo no catálogo   — antes de virar componente de caminho ('..' entraria por aqui).
      2. forma do nome      — regex do que guardar_staging gera; mata '.', '..', caminho
                              absoluto, string vazia e qualquer nome inventado.
      3. confinamento real  — realpath + commonpath sob o _staging/ desta loja, e isfile
                              (diretório não serve — foi exatamente o que o '.' explorou).
    """
    if not tipo_forma_valida(tipo):
        return None
    nome = (nome_recebido or "").strip()
    if not _RE_NOME_STAGING.match(nome):
        return None
    base = os.path.join(DOCS_LOJA_DIR, str(loja_id), tipo, "_staging")
    try:
        base_real = os.path.realpath(base)
        candidato = os.path.realpath(os.path.join(base, nome))
        # commonpath levanta ValueError p/ caminhos em drives diferentes (Windows):
        # é justamente um caso a recusar, então o except trata como "não resolve".
        if os.path.commonpath([base_real, candidato]) != base_real:
            return None
    except (ValueError, OSError):
        return None
    return candidato if os.path.isfile(candidato) else None


def _promover_original(staging_path, loja_id, tipo, versao, origem_nome):
    """Move o original do staging para v<N>/. Devolve o caminho final, ou None."""
    if not staging_path or not os.path.exists(staging_path):
        return None
    destino_dir = os.path.join(DOCS_LOJA_DIR, str(loja_id), tipo, "v%d" % versao)
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, os.path.basename(origem_nome or "original"))
    shutil.move(staging_path, destino)
    return destino


def criar_versao(db, loja_id, tipo, corpo_md, origem_nome, usuario_id,
                 nome=None, staging_path=None, origem_sha256=None):
    """Cria a próxima versão (inativa). Ativar é passo à parte — ver ativar().

    staging_path: original vindo de guardar_staging(); é promovido para v<N>/
    depois que a linha existe.

    ORDEM DELIBERADA — linha primeiro, arquivo depois. _proxima_versao tem corrida
    (dois uploads simultâneos leem o mesmo MAX(versao)); a UniqueConstraint pega o
    perdedor e aqui a gente tenta de novo. Mover o arquivo ANTES do commit deixaria
    o perdedor com um arquivo órfão em v<N>/ e nenhuma linha apontando pra ele —
    verificado por experimento de concorrência. O retry mora aqui, e não em cada
    chamador, porque senão todo chamador futuro teria que lembrar de tratar isso.

    Invariante que isto sustenta: NUNCA existe arquivo em v<N>/ sem uma linha
    apontando pra ele. Os três caminhos de falha, e por que nenhum quebra isso:
      1. INSERT falha (corrida)      → nada foi movido; staging intacto; retry limpo.
      2. _promover_original falha    → versão vale com origem_path=None; original
                                       segue no staging; a exceção sobe.
      3. commit do origem_path falha → o move JÁ aconteceu, então é desfeito (o
                                       original volta pro staging) e a versão fica
                                       com origem_path=None. Não relança — ver o
                                       comentário no bloco.
    Em todos, o pior caso é perder a trilha de auditoria de uma tentativa, nunca
    abandonar arquivo sem dono.
    """
    _validar(tipo, corpo_md)
    if not tipo_existe(db, loja_id, tipo):    # slug custom precisa estar REGISTRADO na loja
        raise ValueError("tipo de documento não cadastrado para esta loja: %r" % (tipo,))
    ultima_violacao = None
    for _ in range(_MAX_TENTATIVAS_VERSAO):
        try:
            m = DocumentoModelo(
                loja_id=loja_id, tipo=tipo,
                versao=_proxima_versao(db, loja_id, tipo),
                nome=nome or os.path.splitext(os.path.basename(origem_nome or ""))[0] or None,
                corpo_md=corpo_md, origem_nome=origem_nome,
                origem_path=None,          # preenchido depois que a linha existe
                origem_sha256=origem_sha256, ativo=0, criado_por_id=usuario_id,
            )
            db.add(m)
            db.commit()
            break
        except IntegrityError as e:
            db.rollback()
            if not _e_colisao_de_versao(e):
                raise          # NOT NULL, FK...: retentar não resolve, sobe agora
            ultima_violacao = e
    else:
        raise RuntimeError(
            "não foi possível reservar número de versão para (loja=%s, tipo=%s) "
            "após %d tentativas" % (loja_id, tipo, _MAX_TENTATIVAS_VERSAO)
        ) from ultima_violacao

    # A linha existe e já é válida sem trilha de origem. Agora o arquivo.
    if staging_path:
        destino = _promover_original(staging_path, loja_id, tipo, m.versao, origem_nome)
        try:
            m.origem_path = destino
            db.commit()
        except Exception:
            db.rollback()
            # Desfaz o move. Sem isto, o arquivo fica em v<N>/ sem linha apontando
            # pra ele — o mesmo órfão que a ordem INSERT-primeiro resolveu.
            if destino and os.path.exists(destino):
                shutil.move(destino, staging_path)
            # Não relança de propósito: a versão EXISTE e é válida; estourar aqui
            # faria o chamador achar que nada foi criado e tentar de novo, gerando
            # uma versão duplicada. O que se perde é só a trilha de origem desta
            # tentativa, e o original volta pro staging — recuperável.
    return m


def ativar(db, modelo_id):
    """Liga esta versão e desliga a anterior do mesmo (loja, tipo)."""
    m = db.get(DocumentoModelo, modelo_id)
    if m is None:
        raise ValueError("modelo não encontrado: %s" % modelo_id)
    (db.query(DocumentoModelo)
       .filter(DocumentoModelo.loja_id == m.loja_id,
               DocumentoModelo.tipo == m.tipo,
               DocumentoModelo.id != m.id)
       .update({"ativo": 0}))
    m.ativo = 1
    db.commit()
    return m


def ativo_de(db, loja_id, tipo):
    """Modelo ativo de (loja, tipo). PDV (loja com mãe, spec 2026-07-22): sem modelo
    próprio, vale o modelo ativo da MÃE — juridicamente o cliente contrata com ela."""
    m = (db.query(DocumentoModelo)
           .filter(DocumentoModelo.loja_id == loja_id,
                   DocumentoModelo.tipo == tipo,
                   DocumentoModelo.ativo == 1)
           .first())
    if m is not None:
        return m
    mae_id = _loja_mae_id(db, loja_id)
    if mae_id:
        return (db.query(DocumentoModelo)
                  .filter(DocumentoModelo.loja_id == mae_id,
                          DocumentoModelo.tipo == tipo,
                          DocumentoModelo.ativo == 1)
                  .first())
    return None


def corpo_da_versao(db, modelo_versao_id):
    """Corpo de uma versão específica — o caminho de reprodução do contrato antigo."""
    m = db.get(DocumentoModelo, modelo_versao_id)
    return m.corpo_md if m else None


def resolver_modelo(db, loja_id, tipo):
    """Corpo vigente para (loja, tipo).

    Sem modelo ativo: contrato cai no arquivo global (comportamento de hoje);
    proposta devolve "" (hoje ela é capa-só).
    """
    m = ativo_de(db, loja_id, tipo)
    if m is not None:
        return m.corpo_md
    if tipo == "contrato":
        # Import LOCAL de propósito, não é ruído: mod_contrato vai importar
        # mod_documentos (para resolver o corpo do contrato pela versão), fechando
        # mod_contrato → mod_documentos → mod_contrato. No topo isso quebra o import;
        # aqui dentro, não. Não promova para o topo do arquivo.
        import mod_contrato
        return mod_contrato._carregar_md()
    return ""


def versao_para_contrato(db, contrato, loja_id):
    """Qual versão de modelo vale para ESTE contrato. Fixa, se for o caso.

    - já fixada          -> ela (reproduz o assinado, mesmo com modelo novo ativo)
    - nunca gerado       -> modelo ativo da loja, e FIXA em contrato.modelo_versao_id
    - legado (já gerado, -> None: cai no template global. NUNCA adotar modelo novo
      sem versão)           num contrato já gerado — reescreveria cláusula assinada.

    Devolve o id da versão, ou None para 'usar o template global'.
    """
    if contrato.modelo_versao_id:
        return contrato.modelo_versao_id
    if contrato.gerado_em is not None:
        return None
    m = ativo_de(db, loja_id, "contrato")
    if m is None:
        return None
    contrato.modelo_versao_id = m.id
    db.commit()
    return m.id


def listar(db, loja_id):
    """Modelos da loja, mais novo primeiro. Escopado por loja (tenancy)."""
    return (db.query(DocumentoModelo)
              .filter(DocumentoModelo.loja_id == loja_id)
              .order_by(DocumentoModelo.tipo, DocumentoModelo.versao.desc())
              .all())
