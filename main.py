"""
main.py — Servidor HTTP, rotas e inicialização.
Ponto de entrada da aplicação: python main.py
"""
import os, io, json, time, re, threading, webbrowser, hashlib, uuid
import sys
import logging
import email
import email.header
from email import policy as _email_policy
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from auth.auth_routes import handle_auth_get, handle_auth_post, get_usuario_sessao
from database import (init_db, get_session, Cliente, Parceiro, Orcamento,
                       PoolAmbiente, OrcamentoAmbiente, Projeto, upsert_projeto_status,
                       CicloEtapa, Contrato, ContratoAssinatura, Usuario, Briefing,
                       LogAcaoGerencial, Medicao, Rede, Loja, ParceiroLoja,
                       membership_loja_ids, lojas_acessiveis_ids, UsuarioLoja, ProvisaoRegistro,
                       CicloDocumento, CicloRevisao, DocumentoFiscal, Emitente,
                       PerfilEmissao, CicloLogistico, CicloLogisticoTransicao, AssistenciaCaso,
                       Funcionario, Fornecedor, Terceiro, Funcao, FolhaPagamento, ComissaoFolha,
                       AdiantamentoFuncionario,
                       AtribuicaoAmbiente, ArquivoPE, ParcelaProjeto, ParcelaAmbiente,
                       Aditivo, AditivoAssinatura, AprovacaoPE, AprovacaoPEAssinatura,
                       AcordoFabrica, AjusteFabrica, AjusteFabricaAplicacao, AcordoMovimento,
                       ContraparteFinanceira)
import mod_expedicao
import mod_assistencias
import mod_cadastro
import mod_folha
import mod_escopo
from urllib.parse import urlparse, unquote

from storage import (
    _BASE_DIR, PROJETOS_DIR,
    PERFIS_PADRAO, PERFIS_FILE,
    storage_ler_json, storage_salvar_json, storage_salvar_binario,
    storage_salvar_texto, storage_ler_texto, storage_ler_binario,
    storage_existe, storage_listar, storage_deletar,
    perfis_carregar, perfis_salvar,
    session_get, session_set,
    so_digitos, normalizar
)
from integracoes.projetos_store import (
    _listar_projetos, _buscar_projetos, _carregar_projeto, _salvar_projeto,
    _criar_projeto, _adicionar_ambientes, _arquivar_xmls,
    _projeto_path, carregar_xmls,
    bloquear_projeto, verificar_integridade_xmls
)
from mod_margens import _normalizar_faixas
from mod_fin import calcular_aymore, calcular_cartao, calcular_venda_programada, calcular_total_flex
from mod_contrato import (calcular_hash_assinatura,
                          gerar_pdf_contrato,
                          construir_contexto, _formatar_valor)
import mod_ciclo
import mod_medicao
from auth import perfis
from auth import mod_usuarios
import mod_tenancy
import mod_arvore
import mod_provisoes
import mod_pe_comparacao
import mod_ajustes_fabrica
import mod_indicadores
from mod_qualidade_xml import avaliar_qualidade_xml

def _enriquecer_projetos_com_status(projetos):
    """Adiciona status, ultimo_orcamento_valor e o consultor (criador) a cada projeto da lista."""
    if not projetos:
        return
    nomes = [p['nome_safe'] for p in projetos if p.get('nome_safe')]
    if not nomes:
        return
    db = get_session()
    try:
        metas = db.query(Projeto).filter(Projeto.nome_safe.in_(nomes)).all()
        meta_map = {m.nome_safe: m for m in metas}

        # Consultor = usuário que criou o projeto (projetos_meta.criado_por_id).
        cons_ids = {m.criado_por_id for m in metas if getattr(m, "criado_por_id", None)}
        cons_map = ({u.id: u.nome for u in db.query(Usuario).filter(Usuario.id.in_(cons_ids)).all()}
                    if cons_ids else {})

        # Pega o orçamento mais recente por projeto (desempate por id desc)
        orc_map = {}
        for nome in nomes:
            orc = (db.query(Orcamento)
                     .filter(Orcamento.projeto_id == nome)
                     .order_by(Orcamento.updated_at.desc(), Orcamento.id.desc())
                     .first())
            if orc:
                orc_map[nome] = orc.valor_total

        for p in projetos:
            ns = p.get('nome_safe')
            if not ns:
                continue
            meta = meta_map.get(ns)
            p['loja_id']                = meta.loja_id    if meta else None
            p['status']                 = meta.status     if meta else None
            p['status_at']              = meta.status_at.isoformat() if meta and meta.status_at else None
            p['perdido_em']             = meta.perdido_em.isoformat() if meta and meta.perdido_em else None
            p['ultimo_orcamento_valor'] = orc_map.get(ns)
            cpid = getattr(meta, "criado_por_id", None) if meta else None
            p['consultor_id']           = cpid
            p['consultor_nome']         = cons_map.get(cpid)
    finally:
        db.close()

def _enriquecer_projetos_com_parceiro(projetos):
    """Resolve o nome do parceiro (arquiteto) de cada projeto a partir do parceiro_id já presente no item."""
    if not projetos:
        return
    ids = {p.get("parceiro_id") for p in projetos if p.get("parceiro_id")}
    if not ids:
        return
    db = get_session()
    try:
        nomes = {pr.id: pr.nome for pr in db.query(Parceiro).filter(Parceiro.id.in_(ids)).all()}
        for p in projetos:
            pid = p.get("parceiro_id")
            p["parceiro_nome"] = nomes.get(pid) if pid else None
    finally:
        db.close()

def _enriquecer_projetos_com_atraso(projetos):
    """Sinal de atraso GERAL (Fatia 4, spec §6): anota `atrasado` + `data_entrega` em cada item.
    Atrasado = qualquer CicloEtapa aberta com previsão vencida, ou entrega vencida com a "16" aberta
    (mod_cronograma.projeto_em_atraso). Status terminal (perdido/concluido/cancelado) nunca acende;
    "fechado" NÃO é terminal — é o estado de EXECUÇÃO (2ª assinatura → etapa 21), a população-alvo
    do sinal. Chamar DEPOIS de _enriquecer_projetos_com_status (reusa o p['status'] já anotado)."""
    import mod_cronograma as _mcr
    nomes = [p['nome_safe'] for p in projetos if p.get('nome_safe')]
    if not nomes:
        return
    db = get_session()
    try:
        hoje = datetime.utcnow()
        entregas = dict(db.query(Projeto.nome_safe, Projeto.data_entrega)
                        .filter(Projeto.nome_safe.in_(nomes)).all())
        etapas_map = {}
        for e in db.query(CicloEtapa).filter(CicloEtapa.projeto_nome.in_(nomes)).all():
            etapas_map.setdefault(e.projeto_nome, []).append(
                (e.etapa_codigo, e.data_prevista_conclusao, e.concluido_em))
        for p in projetos:
            ns = p.get('nome_safe')
            if not ns:
                continue
            de = entregas.get(ns)
            p['data_entrega'] = de.isoformat() if de else None
            if ns not in entregas or (p.get('status') or "") in ("perdido", "concluido", "cancelado"):
                p['atrasado'] = False
                continue
            p['atrasado'] = _mcr.projeto_em_atraso(etapas_map.get(ns, []), de, hoje)
    finally:
        db.close()

def _enriquecer_projetos_com_pool(projetos):
    """Para projetos EP-07, sobrescreve n_ambientes/n_selecionados com contagens do pool."""
    nomes = [p['nome_safe'] for p in projetos if p.get('nome_safe')]
    if not nomes:
        return
    db = get_session()
    try:
        contagens = {}
        for pa in db.query(PoolAmbiente).filter(PoolAmbiente.projeto_id.in_(nomes)).all():
            contagens[pa.projeto_id] = contagens.get(pa.projeto_id, 0) + 1
        for p in projetos:
            n = contagens.get(p.get('nome_safe'), 0)
            if n > 0:
                p['n_ambientes']    = n
                p['n_selecionados'] = n
    finally:
        db.close()

# Consultor responsável do projeto (criado_por_id) — atribuição por gerente+ ------------------
# Quem pode ser "consultor responsável" de um projeto: pela FUNÇÃO (não pelo perfil de acesso).
# Consultor de Vendas + Gerente de Vendas (que pode assumir/reatribuir projetos). Comparação por nome
# normalizado (catálogo FUNCOES_PADRAO).
_FUNCOES_CONSULTOR = ("consultor de vendas", "gerente de vendas")

def _funcao_nome_do_usuario(db, u):
    """Nome (lower) da FUNÇÃO do usuário: via funcao_id direto ou via Funcionário vinculado."""
    fid = getattr(u, "funcao_id", None)
    if not fid and getattr(u, "funcionario_id", None):
        fnc = db.get(Funcionario, u.funcionario_id)
        fid = fnc.funcao_id if fnc else None
    if not fid:
        return None
    fn = db.get(Funcao, fid)
    return (fn.nome or "").strip().lower() if fn else None

def _usuario_pertence_a_loja(db, u, loja_id):
    """True se o usuário `u` está ligado à loja (loja_id direto ou vínculo UsuarioLoja)."""
    if u is None or not loja_id:
        return False
    if u.loja_id == loja_id:
        return True
    return db.query(UsuarioLoja).filter_by(usuario_id=u.id, loja_id=loja_id).first() is not None

def _usuarios_atribuiveis_da_loja(db, loja_id):
    """Usuários ATIVOS da loja que podem ser consultor responsável (para o seletor). Ordenados por nome."""
    if not loja_id:
        return []
    from sqlalchemy import or_
    vinc_ids = {r[0] for r in db.query(UsuarioLoja.usuario_id)
                .filter(UsuarioLoja.loja_id == loja_id).all()}
    conds = [Usuario.loja_id == loja_id]
    if vinc_ids:
        conds.append(Usuario.id.in_(vinc_ids))
    us = (db.query(Usuario).filter(Usuario.ativo == 1).filter(or_(*conds)).all())
    us = [u for u in us if _funcao_nome_do_usuario(db, u) in _FUNCOES_CONSULTOR]
    return sorted(us, key=lambda u: (u.nome or "").lower())

# Cadastro (Modulos_Orizon_v9): entidade -> (Model, serialize, aplicar) para dispatch genérico
def _cad_ent(nome):
    return {
        "funcionarios": (Funcionario, mod_cadastro.func_serialize, mod_cadastro.func_aplicar),
        "fornecedores": (Fornecedor,  mod_cadastro.forn_serialize, mod_cadastro.forn_aplicar),
        "terceiros":    (Terceiro,    mod_cadastro.terc_serialize, mod_cadastro.terc_aplicar),
        "funcoes":      (Funcao,      mod_cadastro.funcao_serialize, mod_cadastro.funcao_aplicar),
    }[nome]

# HTML servido como arquivo estático
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

def _serve_html():
    path = os.path.join(_STATIC_DIR, "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()

# == HANDLERS HTTP ==
# == HANDLERS HTTP ==
# -- Multipart -----------------------------------------------------------------
def _header_texto(valor):
    """Valor de header do multipart como str. Com o policy compat32, um header com
    byte não-ASCII (filename acentuado — caso real: 'ASuíte Master.xml') vem como
    email.header.Header, não str: o .split(';') dos parsers estourava AttributeError
    e a conexão morria SEM resposta ("Failed to fetch" no browser). str(Header)
    também não serve — troca os bytes por U+FFFD. decode_header devolve os bytes
    crus, que são o UTF-8 que o browser mandou."""
    if isinstance(valor, email.header.Header):
        partes = []
        for dados, _charset in email.header.decode_header(valor):
            partes.append(dados.decode("utf-8", "replace") if isinstance(dados, bytes) else dados)
        return "".join(partes)
    return valor


def _parse_multipart(body, ct):
    raw = b"Content-Type: " + ct.encode() + b"\r\n\r\n" + body
    msg = email.message_from_bytes(raw, policy=_email_policy.compat32)
    arquivos, campos = [], {}
    for part in msg.walk():
        cd = _header_texto(part.get("Content-Disposition", ""))
        if not cd:
            continue
        params = {}
        for seg in cd.split(";"):
            seg = seg.strip()
            if "=" in seg:
                k, v = seg.split("=", 1)
                params[k.strip().lower()] = v.strip().strip('"')
        nome    = params.get("name", "")
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        if nome == "xmls" and params.get("filename"):
            arquivos.append((params["filename"], payload.decode("utf-8", "ignore")))
        elif nome and not params.get("filename"):
            campos[nome] = payload.decode("utf-8", "ignore").strip()
    return arquivos, campos

def _parse_multipart_arquivos(body, ct):
    """Multipart binário: retorna (arquivos, campos) onde arquivos[name] = (filename, bytes)
    e campos[name] = texto. (O _parse_multipart é específico p/ XML texto.)"""
    raw = b"Content-Type: " + ct.encode() + b"\r\n\r\n" + body
    msg = email.message_from_bytes(raw, policy=_email_policy.compat32)
    arquivos, campos = {}, {}
    for part in msg.walk():
        cd = _header_texto(part.get("Content-Disposition", ""))
        if not cd:
            continue
        params = {}
        for seg in cd.split(";"):
            seg = seg.strip()
            if "=" in seg:
                k, v = seg.split("=", 1)
                params[k.strip().lower()] = v.strip().strip('"')
        nome = params.get("name", "")
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        if params.get("filename"):
            arquivos[nome] = (params["filename"], payload)
        elif nome:
            campos[nome] = payload.decode("utf-8", "ignore").strip()
    return arquivos, campos


_STEPUP_GRANTS = {}   # {(token, recurso): expira_em_epoch}
_STEPUP_TTL = 30 * 60


def _stepup_conceder(token, recurso):
    _STEPUP_GRANTS[(token, recurso)] = time.time() + _STEPUP_TTL


def _stepup_valido(token, recurso):
    exp = _STEPUP_GRANTS.get((token, recurso))
    if exp and exp > time.time():
        return True
    if exp:
        _STEPUP_GRANTS.pop((token, recurso), None)
    return False


def _usuario_com_capacidade(db, login, senha, capacidade, sessao=None):
    """Usuario ativo com senha correta e a capacidade dada (perfis), ou None.

    SESSÃO-PRIMEIRO (pedido 2026-07-24): se o request veio SEM credenciais e o próprio
    usuário logado (`sessao`) tem a capacidade, ele é o autorizador — logado com permissão
    não redigita senha. Credenciais de terceiro (login+senha) seguem valendo para quem
    não tem a permissão (o gerente digita a dele na tela do operador)."""
    if sessao is not None and not (login or "").strip() and not (senha or ""):
        u = db.get(Usuario, sessao.get("id"))
        if u and u.ativo and perfis.pode(u.nivel, capacidade):
            return u
        return None
    u = db.query(Usuario).filter_by(login=(login or "").strip()).first()
    if not u or not u.ativo or not u.check_senha(senha or ""):
        return None
    if not perfis.pode(u.nivel, capacidade):
        return None
    return u


def _set_etapa_status(db, nome_safe, codigo, status, responsavel_id):
    etapa = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
    if not etapa:
        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=codigo)
        db.add(etapa)
    if etapa.status == "pendente" and status != "pendente":
        etapa.iniciado_em = datetime.utcnow()
    etapa.status = status
    if status in mod_ciclo.STATUS_CONCLUSIVOS:
        etapa.concluido_em = datetime.utcnow()
        etapa.responsavel_id = responsavel_id
        try:                       # Fase 4: comissão do papel na conclusão da etapa (nunca bloqueia)
            import mod_comissao
            db.flush()             # concluido_em disponível
            proj = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
            mod_comissao.preparar_comissao_etapa(db, (proj.loja_id if proj else None), etapa)
        except Exception as _e:
            print("[COMISSAO] preparar falhou:", _e)
    return etapa


def _get_or_create_medicao(db, nome_safe):
    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
    if not md:
        md = Medicao(projeto_nome=nome_safe)
        db.add(md)
    return md


# Etapas cujo responsável é POR AMBIENTE (Mapa de Atribuições) — o gate por FUNÇÃO não se aplica a
# elas (evita falso-bloqueio de montagem/assistência já atribuídas por ambiente). Decisão 2026-07-27.
_ETAPAS_POR_AMBIENTE = frozenset({"17", "18"})


def _bloqueio_execucao_etapa(db, nome_safe, loja_id, codigo):
    """Gate de EXECUÇÃO (bloqueador invertido, decisão 2026-07-27): devolve a mensagem de erro se a
    etapa está TRAVADA por falta de responsável definido (LACUNA — a função tem >1 candidato e
    ninguém foi escolhido), ou None se liberada. Só bloqueia na LACUNA: etapas de responsável único/
    já-definido passam; etapas por ambiente (montagem/assistência) ficam de fora deste gate."""
    if str(codigo) in _ETAPAS_POR_AMBIENTE:
        return None
    import mod_equipe
    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=str(codigo)).first()
    if et is None or not et.funcao_responsavel_id:
        return None
    if mod_equipe.responsavel_da_etapa(db, loja_id, et)["motivo"] == "lacuna":
        return ("Defina o responsável desta etapa antes de executá-la: a função tem mais de um "
                "candidato — um gerente ou diretor precisa indicar o nome.")
    return None


def _aprovador_financeiro(db, login, senha, sessao=None):
    """Usuario apto a aprovar financeiro, ou None. Sessão-primeiro: ver _usuario_com_capacidade."""
    return _usuario_com_capacidade(db, login, senha, "aprovar_financeiro", sessao=sessao)


def _chat_registrar_documento(db, nome_safe, loja_id, doc, usuario_id):
    """Gancho do host → chat (spec 2026-07-31, decisão 2): documento do ciclo vira evento inline
    na conversa do projeto. BEST-EFFORT: nunca derruba o upload (efeito principal do endpoint).
    Chamar ANTES do commit do chamador (entra na mesma transação); precisa do doc.id (flush)."""
    try:
        db.flush()
        import mod_chat
        mod_chat.registrar_documento_na_conversa(db, loja_id, nome_safe, doc,
                                                 autor_usuario_id=usuario_id)
    except Exception as _e:
        logging.getLogger(__name__).warning(
            "evento de documento na conversa falhou (%s/%s): %s", nome_safe, doc.tipo, _e)


def _lojas_do_escopo(db, ator):
    """Unidades da VISÃO UNIFICADA financeira (PDV, spec 2026-07-22): para quem abre o
    painel Financeiro de uma loja-MÃE, devolve [mãe] + PDVs ativos dela; para os demais,
    [loja ativa]. É OPT-IN painel a painel — NUNCA altera o escopo_operacional global."""
    lid = ator.get("active_loja_id") or ator.get("loja_id")
    if not lid:
        return []
    unidades = [lid]
    if perfis.acessa_modulo(ator.get("nivel"), "financeiro"):
        l = db.get(Loja, lid)
        if l is not None and not getattr(l, "loja_mae_id", None):
            unidades += [p.id for p in db.query(Loja)
                         .filter(Loja.loja_mae_id == lid, Loja.ativo == 1)
                         .order_by(Loja.id).all()]
    return unidades


def _contabil_ctx(handler, exige_edicao, consolidado_ok=False):
    """(usuario, db, owner_tipo, owner_id) ou envia erro via handler.send_json e retorna None.
    Gate: módulo financeiro ativo na loja; edição exige aprovar_financeiro OU editar_dados_loja.
    O chamador é responsável por db.close().

    Visão unificada (PDV, spec 2026-07-22): `?unidade=<loja_id>` (ou header
    X-Unidade-Financeira) troca o owner das consultas/ações para a unidade escolhida,
    restrito a _lojas_do_escopo (mãe + PDVs dela) — operações continuam atômicas numa
    unidade por vez. `unidade=consolidado` só nos painéis que declaram consolidado_ok:
    devolve ot="consolidado" e oid=[(ot, oid) de cada unidade] para o handler somar."""
    import mod_contabil, mod_tenancy
    usuario = get_usuario_sessao(handler)
    if not usuario:
        handler.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return None
    db = get_session()
    loja = db.get(Loja, usuario.get("loja_id")) if usuario.get("loja_id") else None
    if loja is not None and getattr(loja, "loja_mae_id", None):
        # PDV: o painel financeiro não existe na UI do PDV e a API acompanha — o financeiro
        # é operado pela loja-mãe em visão unificada. Os LANÇAMENTOS do razão do PDV seguem
        # normais (o wiring de eventos não passa por aqui). ANTES do check de perfil para a
        # mensagem certa chegar ao usuário do PDV (e sem oferta de step-up, que não abriria).
        db.close(); handler.send_json({"ok": False, "erro": "O financeiro do Ponto de Venda "
                                       "é operado pela loja-mãe (visão unificada)."}, code=403); return None
    # Perfil-4 (rev2 §2): só perfis com acesso ao Financeiro abrem o módulo (Diretoria).
    if _sem_acesso_modulo(usuario, "financeiro", handler=handler):
        db.close(); handler.send_json({"ok": False, "erro": "Sem acesso ao módulo Financeiro.", "precisa_stepup": "financeiro"}, code=403); return None
    if loja is not None and not mod_tenancy.modulo_ativo(loja, "financeiro"):
        db.close(); handler.send_json({"ok": False, "erro": "Módulo financeiro inativo."}, code=403); return None
    if exige_edicao:
        niv = usuario.get("nivel")
        if not (perfis.pode(niv, "aprovar_financeiro") or perfis.pode(niv, "editar_dados_loja")):
            db.close(); handler.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return None
    try:
        ot, oid = mod_contabil.resolver_owner(db, usuario)
    except ValueError as e:
        db.close(); handler.send_json({"ok": False, "erro": str(e)}, code=400); return None
    from urllib.parse import parse_qs as _pq
    unid = (_pq(urlparse(handler.path).query).get("unidade") or [None])[0]
    if not unid:
        unid = (handler.headers.get("X-Unidade-Financeira") or "").strip() or None
    if unid == "consolidado":
        if not consolidado_ok:
            db.close(); handler.send_json({"ok": False, "erro": "Este painel não tem visão "
                                           "consolidada — escolha uma unidade."}, code=400); return None
        ator = _ator_dict(db, usuario)
        unidades = _lojas_do_escopo(db, ator)
        if len(unidades) < 2:
            db.close(); handler.send_json({"ok": False, "erro": "Sem Pontos de Venda para "
                                           "consolidar."}, code=400); return None
        vistos, owners = set(), []
        for u in unidades:
            o = mod_contabil.resolver_owner(db, {"loja_id": u, "rede_id": None})
            if o not in vistos:
                vistos.add(o); owners.append(o)
        return usuario, db, "consolidado", owners
    if unid is not None:
        ator = _ator_dict(db, usuario)
        if not str(unid).isdigit() or int(unid) not in _lojas_do_escopo(db, ator):
            db.close(); handler.send_json({"ok": False, "erro": "Unidade fora do escopo."},
                                          code=403); return None
        ot, oid = mod_contabil.resolver_owner(db, {"loja_id": int(unid), "rede_id": None})
    return usuario, db, ot, oid


def _parse_data(s):
    """String ISO ('2026-07-09' ou datetime completo) -> datetime, ou None."""
    if not s:
        return None
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(s)
    except ValueError:
        try:
            return _dt.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None


def _fin_evento_seguro(loja_id, tipo_evento, valor, projeto_id, ref):
    """Wiring evento→lançamento a partir de um fluxo de negócio (contrato/NF-e).
    **Fail-soft e isolado**: usa sessão própria e NUNCA levanta — contabilidade não pode abortar o
    fluxo. **Idempotente** por `ref`. Só dispara se o módulo financeiro está ativo na loja."""
    try:
        if not loja_id or valor is None or float(valor) <= 0:
            return
        import mod_contabil, mod_tenancy
        db = get_session()
        try:
            loja = db.get(Loja, loja_id)
            if loja is None or not mod_tenancy.modulo_ativo(loja, "financeiro"):
                return
            ot, oid = mod_contabil.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
            mod_contabil.registrar_evento(db, ot, oid, tipo_evento, float(valor),
                                          projeto_id=projeto_id, ref=ref)
        finally:
            db.close()
    except Exception as e:
        logging.getLogger(__name__).warning("wiring financeiro (%s, ref=%s) falhou: %s", tipo_evento, ref, e)


def _fin_provisoes_venda_seguro(orc, projeto_id, ref_base):
    """Auto-constitui TODAS as provisões rastreadas no fechamento da venda (v6 §6.4 + FASE B2.4/B2.5), a
    partir do breakdown do motor (`_negociacao_breakdown` → `mod_provisoes`): montagem/garantia/assist +
    fretes/insumos/comissões (5.6.x × 2.1.04.x), impostos como provisão diferida (1.1.05 × 2.1.04.13) e
    o custo financeiro (Cust_Fin) como despesa DIRETA no contrato (5.5.03 × 2.1.05). Cada base é a do
    motor. **Fail-soft/isolado/idempotente** — não aborta o contrato."""
    try:
        loja_id = getattr(orc, "loja_id", None)
        orc_id = getattr(orc, "id", None)
        if not loja_id or not orc_id:
            return
        import mod_contabil, mod_tenancy
        db = get_session()
        try:
            loja = db.get(Loja, loja_id)
            if loja is None or not mod_tenancy.modulo_ativo(loja, "financeiro"):
                return
            orc2 = db.get(Orcamento, orc_id)
            if orc2 is None:
                return
            d = _negociacao_breakdown(orc2, db)
            valores = {
                "montagem":            d.get("Prov_Mont"),
                "garantia":            d.get("Prov_Gar"),
                "assistencia":         d.get("Assist_Orc"),
                "frete_fabrica":       d.get("Frete_Fab_Orc"),
                "frete_local":         d.get("Frete_Loc_Orc"),
                "insumos":             d.get("Ins_Loc_Orc"),
                "com_medidor":         d.get("Com_Med_Orc"),
                "com_proj_exec":       d.get("Com_Proj_Exec_Orc"),
                "retencao_com_vendas": d.get("Com_Venda_Orc"),
                # FASE D2: Custo de Fábrica (= CFO congelado) passa a ser provisionado no contrato (era só na NF-e)
                "custo_fabrica":       round(float(getattr(orc2, "cfo", 0) or 0), 2),
                "impostos":            d.get("Prov_Imp"),
                # FASE A (resultado da venda): os 4 custos adicionais viram provisão (valores do breakdown;
                # 0 quando o toggle do custo está desligado → não lança). JÁ deduzidos do Val_Liq, então
                # NÃO entram no _RUBRICAS/Cust_Var (a margem gerencial já os conta) — só faltavam no razão.
                "com_arq":             d.get("Com_Arq"),
                "pro_fid":             d.get("Pro_Fid"),
                "cust_via":            d.get("Cust_Via"),
                "brinde":              d.get("Bri"),
                "cust_esp":           d.get("Cust_Esp"),
            }
            ot, oid = mod_contabil.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
            # FASE D2: registra a venda CHEIA (Val_Cont) em Receita a Realizar (1.1.02 × 2.1.06) — não toca a DRE
            val_cont = round(float(getattr(orc2, "valor_total", 0) or 0), 2)
            if val_cont > 0:
                mod_contabil.registrar_evento(db, ot, oid, "registro_venda_contrato", val_cont,
                                              projeto_id=projeto_id, ref=ref_base + ":venda")
            mod_contabil.constituir_provisoes_fechamento(db, ot, oid, projeto_id, valores, ref_base)
            # Custo financeiro = Val_Cont − VAVO. Ramo pela forma de pagamento (Fatia B / spec §3.4):
            #  - financeira (Aymoré/Cartão): DESPESA financeira diferida (provisão, rota própria);
            #  - loja (Venda Programada/Total Flex, capital próprio): RECEITA financeira a apropriar (sem despesa).
            # (O box de override loja×financeira na AF1 entra na etapa B.2.)
            cust_fin = round(float(getattr(orc2, "valor_total", 0) or 0) - float(d.get("VAVO") or 0), 2)
            if cust_fin > 0:
                import mod_fin as _mfin
                try:
                    _fp = json.loads(orc2.forma_pagamento) if orc2.forma_pagamento else {}
                except Exception:
                    _fp = {}
                _ramo = _mfin.ramo_financiamento((_fp or {}).get("codigo") or "")
                _ev = "fechamento_venda_custo_financeiro" if _ramo == "financeira" else "constituir_juros_direto"
                mod_contabil.registrar_evento(db, ot, oid, _ev, cust_fin,
                                              projeto_id=projeto_id, ref=ref_base + ":cfin")
        finally:
            db.close()
    except Exception as e:
        logging.getLogger(__name__).warning("wiring fechamento (provisões+custo fin, ref=%s) falhou: %s", ref_base, e)


def _ramo_financeiro_efetivo(orc):
    """Ramo do custo financeiro (Fatia B): override confirmado na AF (orc.ramo_financeiro) ou o default
    automático pela forma de pagamento (loja|financeira|avista)."""
    if getattr(orc, "ramo_financeiro", None):
        return orc.ramo_financeiro
    import mod_fin as _mfin
    try:
        _fp = json.loads(orc.forma_pagamento) if orc.forma_pagamento else {}
    except Exception:
        _fp = {}
    return _mfin.ramo_financiamento((_fp or {}).get("codigo") or "")


def _cust_fin_orc(orc):
    """Custo financeiro do orçamento = valor_total (Val_Cont) − VAVO."""
    return round(float(getattr(orc, "valor_total", 0) or 0) - float(getattr(orc, "vavo", 0) or 0), 2)


def _congelar_segmentacao_no_projeto(db, loja_id, projeto_nome):
    """FASE B2 (A6): congela a segmentação Mercadoria × Serviço EFETIVA (override do projeto vence o
    default da loja) no `parametros_json` do projeto — chamado na assinatura. Depois disso NF-e e NFS-e
    leem os MESMOS percentuais, imunes a mudança do default da loja. Retorna o par congelado ou None
    (loja/projeto ausente). NÃO commita (o chamador decide) e preserva os demais parâmetros."""
    from mod_orcamento_params import (parametros_default_loja, resolver_segmentacao,
                                      segmentacao_efetiva)
    lj = db.get(Loja, loja_id) if loja_id else None
    pj = _projeto_da_loja(db, projeto_nome, loja_id)
    if lj is None or pj is None:
        return None
    if pj.parametros_json:
        par = json.loads(pj.parametros_json)
    else:
        # 🔴 Vera E2E 2026-08-03: projeto que NUNCA persistiu parâmetros vive dos defaults da
        # loja (fallback do breakdown). Gravar só a segmentação DESCARTAVA esses defaults
        # (carga_trib etc.) → recálculo "ao vivo" pós-assinatura zerava Prov_Imp e inflava a
        # margem. Congela os defaults EFETIVOS junto — o comportamento não muda na assinatura.
        par = parametros_default_loja(_cfg_financeira_loja(db, loja_id))
    seg = segmentacao_efetiva(resolver_segmentacao(lj.pct_mercadoria, lj.pct_servico), par)
    par["pct_mercadoria"] = seg["pct_mercadoria"]
    par["pct_servico"]    = seg["pct_servico"]
    pj.parametros_json = json.dumps(par, ensure_ascii=False)
    return seg


def _valores_segmentados_do_projeto(db, loja_id, projeto_nome):
    """Fonte ÚNICA da segmentação de um projeto p/ a face fiscal (NF-e/NFS-e) e o wiring contábil:
    Val_Cont do orçamento do contrato + parcelas Mercadoria/Serviço pela segmentação efetiva (congelada
    na assinatura; override do projeto vence o default da loja). Retorna
    {val_cont, mercadoria, servico, cfo, orc} ou None se não houver contrato/Val_Cont > 0."""
    from mod_orcamento_params import resolver_segmentacao, segmentacao_efetiva, segmentar
    if not loja_id:
        return None
    loja = db.get(Loja, loja_id)
    if loja is None:
        return None
    contrato = (db.query(Contrato).filter_by(projeto_nome=projeto_nome).order_by(Contrato.id.desc()).first())
    orc = db.get(Orcamento, contrato.orcamento_id) if contrato else None
    val_cont = round(float(getattr(orc, "valor_total", 0) or 0), 2)
    if val_cont <= 0:
        return None
    pj = _projeto_da_loja(db, projeto_nome, loja_id)
    params = json.loads(pj.parametros_json) if (pj and pj.parametros_json) else {}
    seg = segmentacao_efetiva(resolver_segmentacao(loja.pct_mercadoria, loja.pct_servico), params)
    merc, serv = segmentar(val_cont, seg["pct_mercadoria"])
    return {"val_cont": val_cont, "mercadoria": merc, "servico": serv, "seg": seg,
            "cfo": round(float(getattr(orc, "cfo", 0) or 0), 2), "orc": orc}


def _fin_faturamento_segmentado_seguro(loja_id, projeto_nome, segmento, ref_doc):
    """Wiring do faturamento SEGMENTADO (FASE B2). O valor do segmento vem do ORÇAMENTO DO CONTRATO
    (`Val_Cont × segmentação efetiva`, congelada na assinatura), NÃO do valor de face do documento
    fiscal. No segmento 'mercadoria' também reconhece o CMV = **CFO** congelado (1× por projeto, ref
    `cmv:<projeto>`). **Fail-soft/isolado/idempotente**, como `_fin_evento_seguro`."""
    try:
        if not loja_id or segmento not in ("mercadoria", "servico"):
            return
        import mod_contabil, mod_tenancy
        db = get_session()
        try:
            loja = db.get(Loja, loja_id)
            if loja is None or not mod_tenancy.modulo_ativo(loja, "financeiro"):
                return
            vals = _valores_segmentados_do_projeto(db, loja_id, projeto_nome)
            if vals is None:
                logging.getLogger(__name__).warning(
                    "faturamento segmentado (%s, %s): sem contrato/Val_Cont — nada lançado", projeto_nome, ref_doc)
                return
            valor_seg = vals["mercadoria"] if segmento == "mercadoria" else vals["servico"]
            ot, oid = mod_contabil.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
            mod_contabil.faturar_segmento(db, ot, oid, projeto_nome, segmento, valor_seg, ref_base="fat:" + ref_doc)
            # Impostos (B2.6): efetiva a parcela do segmento (proporcional Merc/Serv) — dedução na DRE +
            # obrigação fiscal real, baixando a provisão diferida constituída no contrato.
            from mod_orcamento_params import segmentar as _segmentar
            imp_total = mod_contabil.total_lancado(db, ot, oid, "2.1.04.13", "credito", projeto_nome)
            if imp_total > 0:
                imp_merc, imp_serv = _segmentar(imp_total, vals["seg"]["pct_mercadoria"])
                imp_seg = imp_merc if segmento == "mercadoria" else imp_serv
                mod_contabil.efetivar_impostos_segmento(db, ot, oid, projeto_nome, imp_seg, ref_base="imp:" + ref_doc)
            # FASE D2: matching pleno — reconhece TODAS as despesas planejadas (10 rubricas, incl. o CMV da
            # fábrica) na NF-e, baixando os ativos diferidos 1.1.06.0X. Idempotente por projeto+rubrica e por
            # saldo → seguro disparar em ambas as emissões (mercadoria/serviço). Substitui o faturamento_cmv.
            # Desmembramento operacional (Fatia 4): limita ao ELEGÍVEL (parcelas não retidas) — a retida
            # fica DIFERIDA; ao liberar (fração maior), a re-emissão reconhece só o delta. None = inteiro.
            import mod_retido
            _fr = mod_retido.fracao_reconhecivel(db, projeto_nome)
            mod_contabil.reconhecer_despesas_nfe(db, ot, oid, projeto_nome,
                                                 ref_base="match:" + projeto_nome, fracao=_fr)
        finally:
            db.close()
    except Exception as e:
        logging.getLogger(__name__).warning(
            "wiring faturamento segmentado (%s, %s, ref=%s) falhou: %s", segmento, projeto_nome, ref_doc, e)


_REQ_LOJA_ATIVA = None   # header X-Loja-Ativa da requisição atual (HTTPServer single-thread)

def _ler_loja_ativa_header(handler):
    raw = (handler.headers.get("X-Loja-Ativa") or "").strip()
    return int(raw) if raw.isdigit() else None


def _loja_admin_alvo(usuario):
    """Loja-alvo de uma operação de Admin escopada por LOJA (Perfis de Usuário).
    super_admin opera na loja selecionada no console (header X-Loja-Ativa); demais
    perfis usam a própria loja."""
    if usuario.get("nivel") == "super_admin":
        # header PRESENTE (mesmo 0) vence; só cai pra loja própria quando AUSENTE (None).
        return _REQ_LOJA_ATIVA if _REQ_LOJA_ATIVA is not None else usuario.get("loja_id")
    return usuario.get("loja_id")


def mod_perfis_opcoes():
    import modulos
    from auth import mod_perfis
    doms = [{"id": d["id"], "rotulo": d["rotulo"]} for d in modulos.dominios_com_rotulo()]
    return {"dominios": doms, "paineis": [{"id": "admin", "rotulo": "Painel Administração"},
                                          {"id": "config", "rotulo": "Painel Config"}]}


def porta_do_ambiente(environ=None):
    """Porta de bind, lida de ORIZON_PORT (default 8765) — espelha ORIZON_HOST.
    Permite subir uma 2ª instância no mesmo servidor (pré-homologação em :8766).
    Valor inválido/fora de 1-65535 dá erro CLARO no bootstrap: não cai calado numa
    porta errada (mesma lição do header de loja inexistente)."""
    environ = os.environ if environ is None else environ
    raw = environ.get("ORIZON_PORT")
    if not raw:                       # ausente ou "" → default
        return 8765
    try:
        p = int(raw)
    except (TypeError, ValueError):
        raise ValueError("ORIZON_PORT inválido: %r (esperado inteiro 1-65535)" % (raw,))
    if not (1 <= p <= 65535):
        raise ValueError("ORIZON_PORT fora de faixa: %d (esperado 1-65535)" % p)
    return p


MAX_BODY_MB_DEFAULT = 50  # < client_max_body_size do nginx (64M): o erro amigável sai do app


def max_body_bytes(environ=None):
    """Teto do body em bytes, lido de ORIZON_MAX_BODY_MB (default 50 MB) — mesmo
    padrão de porta_do_ambiente: valor inválido dá erro CLARO no bootstrap, não
    default silencioso. Mantido abaixo do teto do nginx (64M) de propósito, para o
    413 amigável em JSON vir sempre do app, nunca do reset seco do proxy."""
    environ = os.environ if environ is None else environ
    raw = environ.get("ORIZON_MAX_BODY_MB")
    if not raw:                       # ausente ou "" → default
        return MAX_BODY_MB_DEFAULT * 1024 * 1024
    try:
        mb = int(raw)
    except (TypeError, ValueError):
        raise ValueError("ORIZON_MAX_BODY_MB inválido: %r (esperado inteiro >= 1)" % (raw,))
    if mb < 1:
        raise ValueError("ORIZON_MAX_BODY_MB fora de faixa: %d (esperado >= 1)" % mb)
    return mb * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _ler_body(self):
        """Ponto ÚNICO de leitura do body (do_POST/do_PUT/do_PATCH). Content-Length
        acima do teto (max_body_bytes) → responde 413 JSON e devolve None SEM ler um
        byte do corpo — drenar dezenas de MB pra memória só pra recusar seria o
        próprio problema — e fecha a conexão (Connection: close), senão o cliente
        segue enviando o resto num socket que ninguém vai ler. O handler chamador
        deve retornar em silêncio no None. Header ausente/inválido → b'{}' (contrato
        que as rotas já esperam)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        teto = max_body_bytes()
        if length > teto:
            body = json.dumps({"ok": False, "erro": "Arquivo grande demais (máx. %d MB)."
                               % (teto // (1024 * 1024))}, ensure_ascii=False).encode("utf-8")
            self.send_response(413)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return None
        return self.rfile.read(length) if length else b'{}'

    def do_GET(self):
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
        path = urlparse(self.path).path
        # Webhook WhatsApp (Fatia 7) — verificação (handshake da Meta). NÃO autenticado (a Meta
        # chama), mas gated pelo ORIZON_WA_VERIFY_TOKEN do ambiente. Dormiente sem o token.
        if path == "/webhooks/whatsapp":
            from urllib.parse import parse_qs
            qs = parse_qs(urlparse(self.path).query)
            verify = (os.environ.get("ORIZON_WA_VERIFY_TOKEN") or "").strip()
            token = (qs.get("hub.verify_token") or [""])[0]
            challenge = (qs.get("hub.challenge") or [""])[0]
            if verify and token == verify:
                self.send_response(200); self.send_header("Content-Type", "text/plain")
                self.end_headers(); self.wfile.write(challenge.encode()); return
            self.send_response(403); self.end_headers(); return
        if path.rstrip("/") in ("/privacidade", "/politica-privacidade") and path != "/":
            # tolerante à barra final — o crawler do Meta reportou 404 em /privacidade/ (2026-08-04)
            # Política de Privacidade (2026-08-03): página PÚBLICA e ESTÁTICA exigida pelo
            # cadastro do app WhatsApp no Meta for Developers (URL acessível sem login).
            # Sem auth/tenancy/banco — só lê static/privacidade.html do disco. O texto é
            # rascunho substituível (trocar o arquivo não exige mudança de código).
            try:
                _pp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "static", "privacidade.html")
                with open(_pp, "rb") as _f:
                    _conteudo = _f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(_conteudo)))
                self.end_headers()
                self.wfile.write(_conteudo)
            except OSError:
                self.send_response(404); self.end_headers()
            return
        if handle_auth_get(self, path): return
        if path == "/api/financeiro/unidades":
            # Visão unificada (PDV, spec 2026-07-22): unidades que o ator pode escolher no
            # seletor dos painéis financeiros da mãe ([mãe] + PDVs ativos; 1 = sem seletor).
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            usuario, db, ot, oid = ctx
            try:
                ator = _ator_dict(db, usuario)
                ids = _lojas_do_escopo(db, ator)
                lojas = {l.id: l for l in db.query(Loja).filter(Loja.id.in_(ids)).all()} if ids else {}
                unidades = [{"id": i, "nome": lojas[i].nome, "codigo": lojas[i].codigo or "",
                             "tipo": (lojas[i].tipo or "loja")} for i in ids if i in lojas]
                self.send_json({"ok": True, "unidades": unidades,
                                "consolidado_disponivel": len(unidades) > 1})
            finally:
                db.close()
            return
        if path == "/api/financeiro/contas":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            inc = (parse_qs(urlparse(self.path).query).get("incluir_inativas") or ["0"])[0] == "1"
            try:
                contas = mod_contabil.listar_contas(db, ot, oid, incluir_inativas=inc)
                self.send_json({"ok": True, "contas": contas})
            finally:
                db.close()
            return
        if path == "/api/financeiro/lancamentos":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            proj = (qs.get("projeto") or [None])[0]
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                lans = mod_contabil.listar_lancamentos(db, ot, oid, projeto_id=proj, ini=ini, fim=fim)
                self.send_json({"ok": True, "lancamentos": lans})
            finally:
                db.close()
            return
        m_aud = re.match(r"^/api/projetos/([^/]+)/auditoria-contabil$", path)
        if m_aud:
            # Relatório de Auditoria Contábil do projeto — razão do projeto (view derivada, read-only).
            from urllib.parse import unquote as _unq
            nome_safe = _unq(m_aud.group(1))
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                if _projeto_da_loja(db, nome_safe, usuario.get("loja_id")) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                self.send_json({"ok": True, "lancamentos": mod_contabil.auditoria_contabil(db, ot, oid, nome_safe)})
            finally:
                db.close()
            return
        m_crono = re.match(r"^/api/projetos/([^/]+)/cronograma$", path)
        if m_crono:
            # Cronograma do projeto — por etapa: Prazo Limite (regressivo) / Planejado (progressivo) /
            # Executado. View derivada do Cronograma Padrão + âncoras do projeto (read-only, operacional).
            from urllib.parse import unquote as _unq
            import mod_cronograma as _mcr, mod_tenancy as _mten
            nome_safe = _unq(m_crono.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = _mten.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                cfg = _cfg_financeira_loja(db, loja_id)
                self.send_json({"ok": True, "cronograma": _mcr.cronograma_projeto_view(db, nome_safe, cfg)})
            finally:
                db.close()
            return
        m_eq = re.match(r"^/api/projetos/([^/]+)/equipe$", path)
        if m_eq:
            # Equipe do Projeto: roster papel→responsáveis (automáticos derivados + seletores) +
            # candidatos (funcionários/terceiros da loja) para os seletores.
            from urllib.parse import unquote as _unq
            import mod_equipe as _meq, mod_tenancy as _mten
            nome_safe = _unq(m_eq.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = _mten.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                self.send_json({"ok": True, "equipe": _meq.equipe(db, nome_safe, loja_id),
                                "candidatos": _meq.candidatos(db, loja_id),
                                # Equipe de Montagem só oferta montador/ajudante (feedback 2026-07-26)
                                "candidatos_montagem": _meq.candidatos_montagem(db, loja_id)})
            finally:
                db.close()
            return
        m_razao = re.match(r"^/api/financeiro/contas/(\d+)/razao$", path)
        if m_razao:
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                r = mod_contabil.razao(db, ot, oid, int(m_razao.group(1)), ini=ini, fim=fim)
                self.send_json({"ok": True, "razao": r})
            except (ValueError, PermissionError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400 if isinstance(e, ValueError) else 403)
            finally:
                db.close()
            return
        if path == "/api/financeiro/dre":
            ctx = _contabil_ctx(self, exige_edicao=False, consolidado_ok=True)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                if ot == "consolidado":
                    self.send_json({"ok": True,
                                    "dre": mod_contabil.dre_consolidada(db, oid, ini=ini, fim=fim)})
                    return
                self.send_json({"ok": True, "dre": mod_contabil.dre(db, ot, oid, ini=ini, fim=fim)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/projetos-dre":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0])
            fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                self.send_json({"ok": True, "projetos": mod_contabil.margem_todos_projetos(db, ot, oid, ini=ini, fim=fim)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/periodos":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                self.send_json({"ok": True, "periodos": mod_contabil.listar_periodos(db, ot, oid)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/indicadores":
            # Snapshot de Indicadores (2026-07-22): liquidez, margens, prazos/giro, KPIs
            # comerciais e séries mensais com tendência. Cálculo puro em mod_indicadores;
            # aqui só a coleta (razão via mod_contabil + funil comercial via queries).
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            from datetime import date as _date_i, timedelta as _td_i
            usuario, db, ot, oid = ctx
            try:
                meses = max(3, min(24, int((parse_qs(urlparse(self.path).query)
                                            .get("meses") or ["6"])[0])))
            except (TypeError, ValueError):
                meses = 6
            try:
                # UTC-naive como TODO o banco (datetime.utcnow) — hoje local desalinharia os
                # buckets perto da virada de dia e a venda "sumiria" da série (tz skew)
                hoje = datetime.utcnow().date()
                # janelas mensais: 1º dia de cada mês, terminando no mês corrente
                inicios = []
                anc = hoje.replace(day=1)
                for _ in range(meses):
                    inicios.append(anc)
                    anc = (anc - _td_i(days=1)).replace(day=1)
                inicios.reverse()
                ini_periodo = datetime.combine(inicios[0], datetime.min.time())
                fim_periodo = datetime.combine(hoje, datetime.max.time())

                # ESCOPO ÚNICO (QA Vera 🔴/🟠): todos os blocos respondem pelo OWNER contábil —
                # as lojas do owner (rede inteira quando a loja pertence a uma; senão a própria).
                # Nada de query global: loja avulsa/outra rede NUNCA entra.
                if ot == "rede":
                    lojas_owner = [l.id for l in db.query(Loja).filter_by(rede_id=oid).all()]
                else:
                    lojas_owner = [oid]
                bal = mod_contabil.balanco(db, ot, oid)
                dre_per = mod_contabil.dre(db, ot, oid, ini=ini_periodo, fim=fim_periodo)
                mv = lambda pref, sen, i=None, f=None: mod_contabil._mov(db, ot, oid, pref, sen, i, f)
                caixa = mv("1.1.01", "devedor")
                receber = round(mv("1.1.02", "devedor") + mv("1.1.07", "devedor"), 2)
                diferidos = round(mv("1.1.05", "devedor") + mv("1.1.06", "devedor"), 2)
                fornecedores = round(mv("2.1.01", "credor") + mv("2.1.04.06", "credor"), 2)

                liq = mod_indicadores.liquidez(bal["ativo"]["circulante"],
                                               bal["passivo"]["circulante"], caixa, diferidos)
                marg = mod_indicadores.margens(dre_per)
                dias_per = (hoje - inicios[0]).days + 1
                praz = mod_indicadores.prazos_giro(receber, fornecedores,
                                                   dre_per.get("receita_liquida"),
                                                   dre_per.get("cmv_csp"), dias_per)

                # funil comercial (Projeto.status) — MESMO escopo do razão (lojas do owner)
                status_counts = {}
                for p in db.query(Projeto).filter(Projeto.loja_id.in_(lojas_owner)).all():
                    st_p = (p.status or "").strip().lower() or "quente"
                    status_counts[st_p] = status_counts.get(st_p, 0) + 1
                # VENDA = contrato com 1ª ASSINATURA (QA Vera 🟠): data imutável (regerar o PDF
                # não move a venda de mês), rascunho não conta, projeto cancelado fora.
                cancelados = {p.nome_safe for p in db.query(Projeto)
                              .filter(Projeto.loja_id.in_(lojas_owner),
                                      Projeto.status == "cancelado").all()}
                rows_ass = (db.query(ContratoAssinatura, Contrato)
                              .join(Contrato, ContratoAssinatura.contrato_id == Contrato.id)
                              .filter(Contrato.loja_id.in_(lojas_owner)).all())
                primeira_ass = {}   # contrato_id -> datetime da 1ª assinatura
                ct_por_id = {}
                for ass, ct in rows_ass:
                    if ct.projeto_nome in cancelados:
                        continue
                    ct_por_id[ct.id] = ct
                    atual = primeira_ass.get(ct.id)
                    if atual is None or (ass.assinado_em and ass.assinado_em < atual):
                        primeira_ass[ct.id] = ass.assinado_em
                orc_val = {o.id: (o.valor_total or 0.0) for o in
                           db.query(Orcamento).filter(
                               Orcamento.id.in_([c.orcamento_id for c in ct_por_id.values()])
                           ).all()} if ct_por_id else {}
                vendas_datadas = [(dt, orc_val.get(ct_por_id[cid].orcamento_id, 0.0))
                                  for cid, dt in primeira_ass.items() if dt is not None]
                vals_ct = [v for dt, v in vendas_datadas if dt >= ini_periodo]
                kpis = mod_indicadores.kpis_comerciais(status_counts, vals_ct)

                # séries mensais: receita/lucro (DRE do mês), caixa (posição fim do mês),
                # vendas (Σ contratos gerados no mês)
                labels, s_receita, s_lucro, s_caixa, s_vendas = [], [], [], [], []
                for i, mi_ in enumerate(inicios):
                    mf = (inicios[i + 1] - _td_i(days=1)) if i + 1 < len(inicios) else hoje
                    mi_dt = datetime.combine(mi_, datetime.min.time())
                    mf_dt = datetime.combine(mf, datetime.max.time())
                    d_m = mod_contabil.dre(db, ot, oid, ini=mi_dt, fim=mf_dt)
                    labels.append(mi_.strftime("%m/%y"))
                    s_receita.append(d_m.get("receita_liquida") or 0.0)
                    s_lucro.append(d_m.get("lucro_liquido") or 0.0)
                    s_caixa.append(mod_contabil._mov(db, ot, oid, "1.1.01", "devedor",
                                                     None, mf_dt))
                    s_vendas.append(round(sum(v for dt, v in vendas_datadas
                                              if mi_dt <= dt <= mf_dt), 2))
                series = {"labels": labels, "receita": s_receita, "lucro": s_lucro,
                          "caixa": s_caixa, "vendas": s_vendas}
                # Tendência (QA Vera 🟠): métricas de FLUXO comparam meses FECHADOS (o mês
                # corrente parcial contra o anterior completo leria "queda" o mês inteiro);
                # caixa é SALDO — posição de hoje vs fim do mês anterior é comparação válida.
                tend = {}
                for k in ("receita", "lucro", "vendas"):
                    tend[k] = mod_indicadores.tendencia(series[k][:-1]
                                                        if len(series[k]) >= 3 else series[k])
                tend["caixa"] = mod_indicadores.tendencia(series["caixa"])
                self.send_json({"ok": True, "indicadores": {
                    "meses": meses, "periodo": {"ini": inicios[0].isoformat(),
                                                "fim": hoje.isoformat()},
                    "liquidez": liq, "margens": marg, "prazos": praz,
                    "caixa": round(caixa, 2), "receber": receber,
                    "comercial": kpis, "series": series, "tendencias": tend,
                    "tend_fluxo_ate_mes_fechado": True,   # a UI rotula a seta dos fluxos
                    "balanco_confere": bal.get("confere", True)}})
            finally:
                db.close()
            return

        if path == "/api/financeiro/balanco":
            ctx = _contabil_ctx(self, exige_edicao=False, consolidado_ok=True)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            data = _parse_data((parse_qs(urlparse(self.path).query).get("data") or [None])[0])
            try:
                if ot == "consolidado":
                    self.send_json({"ok": True,
                                    "balanco": mod_contabil.balanco_consolidado(db, oid, data_corte=data)})
                    return
                self.send_json({"ok": True, "balanco": mod_contabil.balanco(db, ot, oid, data_corte=data)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/rateios":
            # Rateios mãe→PDV do perímetro (visão unificada) — lista com estado de estorno.
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                ator = _ator_dict(db, usuario)
                owners, vistos = [], set()
                for u in _lojas_do_escopo(db, ator):
                    o = mod_contabil.resolver_owner(db, {"loja_id": u, "rede_id": None})
                    if o not in vistos:
                        vistos.add(o); owners.append(o)
                nomes = {("loja", l.id): l.nome for l in db.query(Loja).all()}
                itens = mod_contabil.listar_rateios(db, owners)
                for it in itens:
                    pdvs = [nomes.get(tuple(o)) for o in it["owners"]
                            if tuple(o) != owners[0] and nomes.get(tuple(o))]
                    it["unidade"] = pdvs[0] if pdvs else ""
                self.send_json({"ok": True, "rateios": itens,
                                "eliminacoes_pendentes": mod_contabil.eliminacoes_intercompany(db, owners)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/repasse-fabrica":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            qs = parse_qs(urlparse(self.path).query)
            ini = _parse_data((qs.get("ini") or [None])[0]); fim = _parse_data((qs.get("fim") or [None])[0])
            try:
                self.send_json({"ok": True, "repasse": mod_contabil.total_a_cobrar_fabrica(db, ot, oid, ini=ini, fim=fim)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/provisoes-venda":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            proj = (parse_qs(urlparse(self.path).query).get("projeto") or [None])[0]
            try:
                if not proj:
                    self.send_json({"ok": False, "erro": "informe ?projeto="}, code=400)
                else:
                    self.send_json({"ok": True, "provisoes_venda": mod_contabil.provisoes_da_venda(db, ot, oid, proj)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/dashboard":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                self.send_json({"ok": True, "dashboard": mod_contabil.dashboard_financeiro(db, ot, oid)})
            finally:
                db.close()
            return
        if path == "/api/comercial/dashboard":
            # Dashboard Comercial: funil de conversão + carteira por status + volume contratado.
            # View DERIVADA da fonte única, escopada pela loja ativa (escopo_operacional).
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_comercial_dash
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                self.send_json({"ok": True, "dashboard": mod_comercial_dash.dashboard_comercial(db, loja_id)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/reconciliacao-provisoes":
            # FASE D: Provisionado × Efetivado × Saldo × Destino. ?projeto=<nome> → granular; sem → consolidado.
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            try:
                proj = (parse_qs(urlparse(self.path).query).get("projeto") or [None])[0]
                self.send_json({"ok": True, "reconciliacao": mod_contabil.reconciliacao(db, ot, oid, projeto_id=proj)})
            finally:
                db.close()
            return
        m_pecmp = re.match(r'^/api/projetos/([^/]+)/pe/comparacao$', path)
        if m_pecmp:
            # Fatia 1 (desmembramento PE): comparação de CFO venda×PE + reconciliação ESTIMADA
            # referenciada ao Val_Cont (#9, read-only, não lança). spec 2026-07-13.
            nome = unquote(m_pecmp.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_contabil   # local (não é module-level); mod_tenancy/mod_pe_comparacao são globais
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                pool = (db.query(PoolAmbiente).filter_by(projeto_id=nome)
                          .order_by(PoolAmbiente.id.asc()).all())
                itens_cfo = [(pa.nome_exibicao or pa.nome, pa.order_total or 0.0) for pa in pool]
                pa_nome = {pa.id: (pa.nome_exibicao or pa.nome) for pa in pool}
                pes = db.query(ArquivoPE).filter_by(projeto_nome=nome, formato="xml_pe").all()
                valores_pe = {pa_nome[a.pool_ambiente_id]: a.valor_atualizado
                              for a in pes if a.valor_atualizado is not None and a.pool_ambiente_id in pa_nome}
                linhas = mod_pe_comparacao.montar_comparacao_pe(itens_cfo, valores_pe)
                # enriquece cada linha com o pool_ambiente_id (glue de UI p/ o upload por ambiente;
                # fora do contrato da função pura, que é keyed por nome — §6)
                _id_por_nome = {(pa.nome_exibicao or pa.nome): pa.id for pa in pool}
                for _l in linhas:
                    _l["pool_ambiente_id"] = _id_por_nome.get(_l["ambiente"])
                delta_cfo = -mod_pe_comparacao.saldo_margem_estimado(linhas)
                # reconciliação estimada (lê o razão só p/ exibir) + Val_Cont do contrato assinado
                ot, oid = mod_contabil.resolver_owner(db, usuario)
                rec = mod_contabil.reconciliacao(db, ot, oid, projeto_id=nome)
                contrato = (db.query(Contrato).filter_by(projeto_nome=nome)
                              .order_by(Contrato.id.desc()).first())
                orc = db.get(Orcamento, contrato.orcamento_id) if contrato else None
                val_cont = (orc.val_cont or 0.0) if orc else 0.0
                rec_est = mod_pe_comparacao.reconciliacao_estimada(
                    rec.get("provisoes", []), delta_cfo, val_cont)
                # ── Fatia venda (2026-07-21): comparação de VENDA À VISTA pelo MESMO motor ──
                # Backfill lazy: PE carregado antes da coluna valor_venda → re-parseia o arquivo salvo.
                for a in pes:
                    if (a.valor_venda is None and a.arquivo_path
                            and str(a.arquivo_path).lower().endswith(".xml")
                            and os.path.exists(a.arquivo_path)):
                        try:
                            with open(a.arquivo_path, "rb") as _f:
                                a.valor_venda = mod_pe_comparacao.extrair_venda_pe(
                                    os.path.basename(a.arquivo_path), _f.read())
                        except Exception:
                            pass
                db.commit()
                comparacao_venda, venda_totais = [], None
                if orc is not None:
                    # motor 2×: insumos salvos (original) × VBVA substituído pelo do PE onde carregado
                    vbva_pe = {a.pool_ambiente_id: a.valor_venda for a in pes
                               if a.valor_venda is not None and a.pool_ambiente_id in pa_nome}
                    d_orig = _negociacao_breakdown(orc, db)
                    d_pe = _negociacao_breakdown(orc, db, vbva_override=vbva_pe) if vbva_pe else d_orig
                    vava_orig = {amb.get("id"): amb.get("VAVA", 0.0) for amb in d_orig.get("ambientes", [])}
                    vava_pe_id = {amb.get("id"): amb.get("VAVA", 0.0) for amb in d_pe.get("ambientes", [])}
                    itens_vava = [(pa_nome[i], vava_orig[i]) for i in vava_orig if i in pa_nome]
                    vava_pe_nome = {pa_nome[i]: vava_pe_id.get(i, 0.0) for i in vbva_pe if i in pa_nome}
                    renegs = {(pa.nome_exibicao or pa.nome): bool(pa.renegociar_pe) for pa in pool}
                    comparacao_venda = mod_pe_comparacao.montar_comparacao_venda(
                        itens_vava, vava_pe_nome, renegs)
                    for _l in comparacao_venda:
                        _l["pool_ambiente_id"] = _id_por_nome.get(_l["ambiente"])
                    venda_totais = {"vavo_original": d_orig.get("VAVO", 0.0),
                                    "vavo_pe": d_pe.get("VAVO", 0.0),
                                    "val_cont_original": d_orig.get("Val_Cont", 0.0),
                                    "val_cont_pe": d_pe.get("Val_Cont", 0.0)}
                self.send_json({"ok": True, "comparacao": linhas,
                                "comparacao_venda": comparacao_venda,
                                "venda_totais": venda_totais,
                                "reconciliacao_estimada": rec_est})
            finally:
                db.close()
            return

        m_parc = re.match(r'^/api/projetos/([^/]+)/parcelas$', path)
        if m_parc:
            # Fatia 2 (desmembramento): lista as parcelas do projeto (ambientes + fração congelada #5)
            nome = unquote(m_parc.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                pa_nome = {pa.id: (pa.nome_exibicao or pa.nome)
                           for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome).all()}
                parcs = (db.query(ParcelaProjeto).filter_by(projeto_nome=nome)
                           .order_by(ParcelaProjeto.ordem.asc()).all())
                out = []
                for p in parcs:
                    ambs = db.query(ParcelaAmbiente).filter_by(parcela_id=p.id).all()
                    out.append({"id": p.id, "ordem": p.ordem, "status": p.status,
                                "fracao_val_cont": round(p.fracao_val_cont or 0.0, 6),
                                "val_cont_congelado": round(p.val_cont_congelado or 0.0, 2),
                                "val_liq_congelado": (round(p.val_liq_congelado, 2)
                                                      if p.val_liq_congelado is not None else None),
                                "liberacao_prevista": (p.liberacao_prevista.isoformat()
                                                       if p.liberacao_prevista else None),
                                "entrega_prevista": (p.entrega_prevista.isoformat()
                                                     if p.entrega_prevista else None),
                                "ambientes": [{"id": a.pool_ambiente_id,
                                               "nome": pa_nome.get(a.pool_ambiente_id, "")} for a in ambs]})
                import mod_retido as _mret
                sinais = [{"pool_ambiente_id": s["pool_ambiente_id"], "motivo": s["motivo"],
                           "nome": pa_nome.get(s["pool_ambiente_id"], "")}
                          for s in _mret.listar_sinais(db, nome)]
                # 🟠 Vera E2E 2026-08-03: o "pool" oferecido a desmembramento/retenção são os
                # ambientes do orçamento CONTRATADO (ambiente de orçamento perdedor fica fora);
                # sem contrato, cai no pool inteiro (comportamento antigo).
                _ctr = (db.query(Contrato).filter_by(projeto_nome=nome)
                          .order_by(Contrato.id.desc()).first())
                if _ctr:
                    _ids_ctr = [lk.pool_ambiente_id for lk in
                                db.query(OrcamentoAmbiente).filter_by(
                                    orcamento_id=_ctr.orcamento_id).all()]
                    pool_out = [{"id": i, "nome": pa_nome.get(i, "")} for i in _ids_ctr]
                else:
                    pool_out = [{"id": i, "nome": n} for i, n in pa_nome.items()]
                self.send_json({"ok": True, "parcelas": out, "desmembrado": bool(out),
                                "sinais_retido": sinais, "pool": pool_out})
            finally:
                db.close()
            return

        m_entr = re.match(r'^/api/projetos/([^/]+)/entrega-resumo$', path)
        if m_entr:
            # Faixa de entrega do fichário (etapas 9→16): previsão × entregue, global e por fase.
            # Previsão: CicloLogistico.prazo_entrega da fase (expedição) ou Projeto.data_entrega;
            # entregue: CicloLogistico.data_entrega, e no global também a etapa 16 concluída.
            nome = unquote(m_entr.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                proj = _projeto_da_loja(db, nome, loja_id)
                if proj is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                _iso = lambda v: v.isoformat() if v else None
                previsao = _iso(proj.data_entrega)
                card_glob = (db.query(CicloLogistico)
                               .filter_by(projeto_nome=nome, parcela_id=None)
                               .order_by(CicloLogistico.id.desc()).first())
                e16 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="16").first()
                entregue = (_iso(card_glob.data_entrega if card_glob else None)
                            or (_iso(e16.concluido_em)
                                if (e16 and e16.status in mod_ciclo.STATUS_CONCLUSIVOS) else None))
                pa_nome = {pa.id: (pa.nome_exibicao or pa.nome)
                           for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome).all()}
                parcs = (db.query(ParcelaProjeto).filter_by(projeto_nome=nome)
                           .order_by(ParcelaProjeto.ordem.asc()).all())
                fases = []
                if parcs:
                    cards = {c.parcela_id: c
                             for c in db.query(CicloLogistico)
                                        .filter(CicloLogistico.projeto_nome == nome,
                                                CicloLogistico.parcela_id != None).all()}  # noqa: E711
                    import mod_agenda as _mag_er
                    for p in parcs:
                        ambs = db.query(ParcelaAmbiente).filter_by(parcela_id=p.id).all()
                        card = cards.get(p.id)
                        # cadeia CANÔNICA compartilhada com a Agenda (mod_agenda, Vera 🟠2):
                        # prazo da expedição > previsão da fase > data de entrega do projeto >
                        # prevista da etapa 16 (último recurso)
                        _prev_fase = _mag_er.data_entrega_da_fase(
                            None, card.prazo_entrega if card else None,
                            p.entrega_prevista, proj.data_entrega,
                            e16.data_prevista_conclusao if e16 else None)
                        fases.append({
                            "id": p.id, "ordem": p.ordem, "status": p.status,
                            "previsao": (_prev_fase.isoformat() if _prev_fase else None),
                            "liberacao_prevista": _iso(p.liberacao_prevista),
                            "entregue_em": _iso(card.data_entrega) if card else None,
                            "ambientes": [pa_nome.get(a.pool_ambiente_id, "") for a in ambs]})
                else:
                    # sem desmembramento: "fase única" com os ambientes do orçamento contratado
                    contrato = (db.query(Contrato).filter_by(projeto_nome=nome)
                                  .order_by(Contrato.id.desc()).first())
                    if contrato:
                        lks = db.query(OrcamentoAmbiente).filter_by(
                            orcamento_id=contrato.orcamento_id).all()
                        nomes_amb = [pa_nome.get(l.pool_ambiente_id, "") for l in lks]
                    else:
                        nomes_amb = list(pa_nome.values())
                    fases.append({"id": None, "ordem": 1, "status": None,
                                  "previsao": (previsao
                                               or (_iso(e16.data_prevista_conclusao) if e16 else None)),
                                  "entregue_em": entregue,
                                  "ambientes": [n for n in nomes_amb if n]})
                self.send_json({"ok": True, "desmembrado": bool(parcs),
                                "previsao": previsao, "entregue_em": entregue, "fases": fases})
            finally:
                db.close()
            return

        if path == "/api/agenda/montagem":
            # ── Gantt de MONTAGEM + espelho de atribuições (rev 2026-08-03) ──
            # Um item por projeto/fase com janela de montagem; ambientes com Val_Liq (base da
            # comissão) e o montador do Mapa; conflitos = mesmo montador em janelas sobrepostas
            # de projetos distintos. Visão operacional recebe SEM valores.
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            from urllib.parse import parse_qs
            _qs = parse_qs(urlparse(self.path).query)
            def _q(k):
                return (_qs.get(k) or [None])[0]
            def _pd(s):
                try:
                    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date() if s else None
                except ValueError:
                    return None
            de, ate = _pd(_q("de")), _pd(_q("ate"))
            proj_filtro = unquote(_q("projeto") or "") or None
            papel_j = (_q("papel") or "montagem")
            if papel_j not in ("montagem", "projeto_executivo"):
                self.send_json({"ok": False, "erro": "papel deve ser montagem|projeto_executivo"},
                               code=400); return
            db = get_session()
            try:
                import mod_agenda as _mag
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                visao = mod_escopo.visao_do_papel(ator)
                _cfg_ag = (_cfg_financeira_loja(db, loja_id) or {}).get("agenda") or {}
                itens = _montagem_itens_enriquecidos(db, ator, loja_id, _cfg_ag, proj_filtro,
                                                     papel=papel_j)
                if de:
                    itens = [i for i in itens if i["fim"] >= de]
                if ate:
                    itens = [i for i in itens if i["inicio"] <= ate]
                conflitos = _mag.conflitos_montagem(itens)
                for it in itens:
                    it["inicio"] = it["inicio"].isoformat()
                    it["fim"] = it["fim"].isoformat()
                    if visao == "operacional":
                        it["val_liq"] = None
                        for a in it["ambientes"]:
                            a["val_liq"] = None
                for c in conflitos:
                    for x in c["itens"]:
                        x["inicio"] = x["inicio"].isoformat()
                        x["fim"] = x["fim"].isoformat()
                self.send_json({"ok": True, "itens": itens, "conflitos": conflitos,
                                "visao": visao})
            finally:
                db.close()
            return

        m_rets = re.match(r'^/api/projetos/([^/]+)/retencoes$', path)
        if m_rets:
            # Histórico de retenções por obra (eventos): quando, etapa do ciclo, ambientes,
            # motivo, liberação prevista e liberação efetiva.
            nome = unquote(m_rets.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                import mod_retido as _mret
                pa_nome = {pa.id: (pa.nome_exibicao or pa.nome)
                           for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome).all()}
                regs = _mret.listar_retencoes(db, nome)
                for r in regs:
                    r["ambientes"] = [{"id": a, "nome": pa_nome.get(a, "")} for a in r["ambientes"]]
                self.send_json({"ok": True, "retencoes": regs})
            finally:
                db.close()
            return

        if path == "/api/agenda":
            # ── Agenda da Loja (Fatia 2, spec 2026-08-03): marcos de TODOS os cronogramas ──
            # DERIVADA: lê cronograma/fases/expedição e devolve marcos por dia/Setor. Escopo da
            # LOJA; consultor filtrado por posse; visão operacional recebe marcos SEM valores.
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            from urllib.parse import parse_qs
            _qs = parse_qs(urlparse(self.path).query)
            def _q(k):
                return (_qs.get(k) or [None])[0]
            def _pd(s):
                try:
                    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date() if s else None
                except ValueError:
                    return None
            de, ate, setor = _pd(_q("de")), _pd(_q("ate")), (_q("setor") or None)
            proj_filtro = unquote(_q("projeto") or "") or None   # agenda de UM projeto (cronograma)
            db = get_session()
            try:
                import mod_agenda as _mag
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                visao = mod_escopo.visao_do_papel(ator)
                dados = _agenda_dados_projetos(db, ator, loja_id, proj_filtro)
                out = []
                for m in _mag.marcos(dados, de=de, ate=ate, setor=setor):
                    if visao == "operacional":
                        m["valor"] = None            # visão do papel: sem comercial (Regras §3)
                    m["data"] = m["data"].isoformat()
                    out.append(m)
                # Fatias 3/4: CARGAS + CAPACIDADE — só p/ visão comercial (é tudo R$)
                cargas_out, cap_out, cap_cfg = [], [], {}
                if visao != "operacional":
                    _cfg_ag = (_cfg_financeira_loja(db, loja_id) or {}).get("agenda") or {}
                    _cgs = _mag.cargas(dados, cfg_agenda=_cfg_ag, de=de, ate=ate)
                    for c in _mag.capacidade(_cgs, cfg_agenda=_cfg_ag):
                        c["data"] = c["data"].isoformat()
                        cap_out.append(c)
                    for c in _cgs:
                        c["data"] = c["data"].isoformat()
                        cargas_out.append(c)
                    cap_cfg = {"produtividade_montagem": _cfg_ag.get("produtividade_montagem_rs_dupla_dia", 7000.0),
                               "duplas_disponiveis": _cfg_ag.get("duplas_disponiveis", 2),
                               "produtividade_pe": _cfg_ag.get("produtividade_pe_rs_dia", 20000.0),
                               "sabado_util": bool(_cfg_ag.get("sabado_util")),
                               "horizonte_semanas": _cfg_ag.get("horizonte_capacidade_semanas", 6),
                               # grade do Operacional (2026-08-06): sombreia coluna de feriado —
                               # antes só mod_calendario via server sabia dessa lista.
                               "feriados": _cfg_ag.get("feriados") or []}
                self.send_json({"ok": True, "marcos": out, "cargas": cargas_out,
                                "capacidade": cap_out, "capacidade_cfg": cap_cfg, "visao": visao,
                                "setores": [{"id": s, "rotulo": r} for s, r in _mag.SETORES],
                                "itens": [{"id": i, "rotulo": r} for i, r in _mag.ITENS_VALOR]})
            finally:
                db.close()
            return
        if path == "/api/financeiro/contas-a-pagar":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            try:
                proj = (parse_qs(urlparse(self.path).query).get("projeto") or [None])[0]
                self.send_json({"ok": True, "contas_a_pagar": mod_contabil.contas_a_pagar(db, ot, oid, projeto_id=proj)})
            finally:
                db.close()
            return
        if path == "/api/financeiro/provisao-projetos":
            # FASE D: discrimina uma provisão por projeto (modal ao clicar no painel de Provisões).
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            from urllib.parse import parse_qs
            usuario, db, ot, oid = ctx
            try:
                cod = (parse_qs(urlparse(self.path).query).get("conta") or [""])[0].strip()
                self.send_json({"ok": True, "provisao": mod_contabil.provisao_projetos(db, ot, oid, cod)})
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/expedicao/kanban":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "expedicao"):
                    self.send_json({"ok": False, "erro": "Módulo Expedição inativo."}, code=403); return
                proj_cli = {p.nome_safe: p.cliente_id for p in db.query(Projeto).filter_by(loja_id=lid).all()}
                cli_nome = {c.id: c.nome for c in db.query(Cliente).filter_by(loja_id=lid).all()}
                idx = {s: i for i, s in enumerate(mod_expedicao.STATUS)}
                colunas = [{"status": s, "cards": []} for s in mod_expedicao.STATUS]
                for card in db.query(CicloLogistico).filter_by(loja_id=lid).all():
                    if card.status_atual not in idx:
                        continue
                    cnome = cli_nome.get(proj_cli.get(card.projeto_nome))
                    colunas[idx[card.status_atual]]["cards"].append(mod_expedicao.card_kanban(card, cnome))
                self.send_json({"ok": True, "colunas": colunas,
                                "meta": {"status": mod_expedicao.STATUS,
                                         "captura": mod_expedicao.REALIZADO_AO_ENTRAR,
                                         "campos_prazo": mod_expedicao.CAMPOS_PRAZO,
                                         "campos_realizado": mod_expedicao.CAMPOS_REALIZADO}})
            finally:
                db.close()
            return

        m = re.match(r'^/api/expedicao/cards/(\d+)$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                card = db.get(CicloLogistico, int(m.group(1)))
                if card is None or (lid and card.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                p = db.query(Projeto).filter_by(nome_safe=card.projeto_nome).first()
                cli = db.get(Cliente, p.cliente_id) if p and p.cliente_id else None
                self.send_json({"ok": True, "card": mod_expedicao.card_detalhe(db, card, cli.nome if cli else "")})
            finally:
                db.close()
            return

        if path == "/api/assistencias/casos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "assistencias"):
                    self.send_json({"ok": False, "erro": "Módulo Assistências inativo."}, code=403); return
                from urllib.parse import parse_qs
                tipo = (parse_qs(urlparse(self.path).query).get("tipo") or [""])[0].strip()
                self.send_json({"ok": True,
                                "casos": mod_assistencias.listar(db, lid, tipo or None),
                                "a_cobrar_fabrica": mod_assistencias.a_cobrar_fabrica(db, lid),
                                "meta": mod_assistencias.meta()})
            finally:
                db.close()
            return

        # ── Folha de Pagamento (Modulos_Orizon_v10 §2.1) — folha do período ──────────────
        if path == "/api/folha":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if _sem_acesso_modulo(usuario, "folha", handler=self):
                self.send_json({"ok": False, "erro": "Sem acesso ao módulo Folha.", "precisa_stepup": "folha"}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                from urllib.parse import parse_qs
                comp = (parse_qs(urlparse(self.path).query).get("competencia") or [""])[0].strip()
                if not re.match(r'^\d{4}-\d{2}$', comp):
                    self.send_json({"ok": False, "erro": "Informe a competência AAAA-MM."}, code=400); return
                self.send_json({"ok": True, "folha": mod_folha.listar(db, loja_id, comp)})
            finally:
                db.close()
            return

        # ── Comissão: composição da BASE (ambientes atribuídos) de um item de papel ──────
        m = re.match(r'^/api/comissao/(\d+)/base$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_comissao
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                it = db.query(ComissaoFolha).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                if it is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                itens = mod_comissao.base_detalhe(db, it)
                self.send_json({"ok": True, "itens": itens, "projeto": it.projeto_nome, "papel": it.papel,
                                "total": round(sum(x["valor"] for x in itens), 2)})
            finally:
                db.close()
            return

        # ── Folha: discriminação da BASE de comissão de uma linha (todos os itens + ambientes) ──
        m = re.match(r'^/api/folha/(\d+)/comissoes-base$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_comissao
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                reg = db.query(FolhaPagamento).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                if reg is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                itens = (db.query(ComissaoFolha)
                         .filter_by(funcionario_id=reg.funcionario_id, competencia=reg.competencia)
                         .filter(ComissaoFolha.status != "cancelado")
                         .order_by(ComissaoFolha.id.asc()).all())
                out = []
                for it in itens:
                    base = it.base_ajustada if it.base_ajustada is not None else it.base
                    out.append({"projeto": it.projeto_nome, "papel": it.papel or it.origem, "origem": it.origem,
                                "base": round(base or 0.0, 2), "valor": it.valor,
                                "ambientes": mod_comissao.base_detalhe(db, it)})
                self.send_json({"ok": True, "itens": out,
                                "total_base": round(sum(x["base"] for x in out), 2)})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Cadastro (Modulos_Orizon_v9/v10): listas Funcionários/Fornecedores/Terceiros/Funções ──
        m = re.match(r'^/api/(funcionarios|fornecedores|terceiros|funcoes)$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                Model, ser, _ = _cad_ent(m.group(1))
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(self.path).query)
                q = (qs.get("q") or [""])[0].strip()
                status = (qs.get("status") or [""])[0].strip()
                itens = mod_cadastro.listar(db, Model, ser, loja_id, q or None, status or None)
                # Filtro por função (Modulos_Orizon_v12): dropdown de responsável do Cronograma lista
                # só funcionários da função exigida pela fase.
                funcao_id = (qs.get("funcao_id") or [""])[0].strip()
                if funcao_id:
                    try:
                        fid = int(funcao_id)
                        itens = [x for x in itens if x.get("funcao_id") == fid]
                    except ValueError:
                        pass
                self.send_json({"ok": True, "meta": mod_cadastro.META, "itens": itens})
            finally:
                db.close()
            return
        if path == "/":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return
            body = _serve_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)

        elif path == "/perfis":
            self.send_json(perfis_carregar())

        elif path == "/perfis/ativo":
            dados = perfis_carregar()
            nome  = dados.get("perfil_ativo", "consultor")
            cfg   = dados["perfis"].get(nome, PERFIS_PADRAO["perfis"]["consultor"])
            self.send_json({"perfil_ativo": nome, "config": cfg})

        elif path == "/pagamentos":
            # Lista modalidades do mod_fin.py para popular o dropdown
            try:
                import mod_fin as _mf
                mods = _mf.listar_modalidades()
            except Exception:
                mods = [{"codigo": "a_vista", "descricao": "A Vista"}]
            self.send_json({"ok": True, "modalidades": mods})

        elif path == "/projetos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                projetos = _listar_projetos()
                projetos = _filtrar_projetos_por_loja(projetos, db, loja_id, ator=usuario)
                _enriquecer_projetos_com_pool(projetos)
                _enriquecer_projetos_com_status(projetos)
                _enriquecer_projetos_com_parceiro(projetos)
                _enriquecer_projetos_com_atraso(projetos)
                self.send_json({"ok": True, "projetos": projetos})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif path == "/api/projetos/consultores":
            # Seletor de consultor responsável (criação/edição). `pode_atribuir` = gerente+ (não escopo-próprio).
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                pode = not _ve_apenas_proprios_projetos(usuario.get("nivel"))
                us = _usuarios_atribuiveis_da_loja(db, loja_id)
                self.send_json({"ok": True, "pode_atribuir": pode,
                                "consultores": [{"id": u.id, "nome": u.nome, "nivel": u.nivel} for u in us]})
            finally:
                db.close()

        elif path == "/projetos/buscar":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                from urllib.parse import parse_qs
                q = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip()
                locais = _buscar_projetos(q)
                locais = _filtrar_projetos_por_loja(locais, db, loja_id, ator=usuario)
                for p in locais: p['origem'] = 'local'
                _enriquecer_projetos_com_pool(locais)
                _enriquecer_projetos_com_status(locais)
                _enriquecer_projetos_com_parceiro(locais)
                _enriquecer_projetos_com_atraso(locais)
                self.send_json({'ok': True, 'projetos': locais})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        m = re.match(r"^/api/clientes/(\d+)/briefing$", path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, int(m.group(1)), loja_id)
                if c is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                b = db.query(Briefing).filter_by(cliente_id=c.id)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    self.send_json({"ok": True, "briefing": None})
                    return
                self.send_json({"ok": True, "briefing": _briefing_dict(b)})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        m = re.match(r"^/api/projetos/([^/]+)/briefing$", path)
        if m:
            nome_safe = unquote(m.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    self.send_json({"ok": True, "briefing": None})
                    return
                self.send_json({"ok": True, "briefing": _briefing_dict(b)})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        elif path == "/api/clientes":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            from urllib.parse import parse_qs
            q  = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip().lower()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                query = db.query(Cliente).filter(Cliente.loja_id == loja_id).order_by(Cliente.nome)
                if q:
                    query = query.filter(
                        (Cliente.nome.ilike(f"%{q}%")) |
                        (Cliente.cpf.ilike(f"%{q}%"))
                    )
                all_clientes = query.all()
                # IDs com briefing completo
                cli_ids = [c.id for c in all_clientes]
                briefings_ok = set()
                if cli_ids:
                    bfs = db.query(Briefing.cliente_id).filter(
                        Briefing.cliente_id.in_(cli_ids),
                        Briefing.tipo_imovel != None,
                        Briefing.tipo_imovel != "",
                        Briefing.budget_declarado != None,
                        Briefing.budget_declarado != 0,
                        Briefing.categoria_proposta != None,
                        Briefing.categoria_proposta != "",
                        Briefing.data_entrega_desejada != None,
                        Briefing.data_entrega_desejada != "",
                        Briefing.flexibilidade_prazo != None,
                        Briefing.flexibilidade_prazo != "",
                    ).all()
                    briefings_ok = {b[0] for b in bfs}
                clientes = []
                for c in all_clientes:
                    cd = _cliente_dict(c)
                    cd["tem_briefing"] = c.id in briefings_ok
                    clientes.append(cd)
                self.send_json({"ok": True, "clientes": clientes})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e), "clientes": []})
            finally:
                db.close()

        elif path == "/api/parceiros":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            from urllib.parse import parse_qs
            q  = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip().lower()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                query = db.query(Parceiro).order_by(Parceiro.nome)
                if q:
                    query = query.filter(
                        (Parceiro.nome.ilike(f"%{q}%")) |
                        (Parceiro.cpf_cnpj.ilike(f"%{q}%"))
                    )
                todos = query.all()
                todos = [p for p in todos if _parceiro_visivel_loja(db, p, loja_id)]
                parceiros = [_parceiro_dict(p, db) for p in todos]
                self.send_json({"ok": True, "parceiros": parceiros})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e), "parceiros": []})
            finally:
                db.close()

        elif path == "/api/admin/usuarios":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                us = db.query(Usuario).order_by(Usuario.nome).all()
                # pré-carrega rede_id de cada loja referenciada (evita N+1 no loop de escopo)
                loja_ids = {u.loja_id for u in us if u.loja_id is not None}
                rede_de_loja = {l.id: l.rede_id for l in
                                db.query(Loja).filter(Loja.id.in_(loja_ids)).all()} if loja_ids else {}
                visiveis = []
                for u in us:
                    if mod_tenancy._eh_super_admin(ator):
                        ok = True
                    elif mod_tenancy._eh_admin_rede(ator):
                        ok = (u.rede_id == ator["rede_id"]) or (
                            u.loja_id is not None and mod_tenancy.pode_ver_loja(
                                ator, {"id": u.loja_id, "rede_id": rede_de_loja.get(u.loja_id)}))
                    else:
                        ok = (u.loja_id is not None and u.loja_id == ator.get("loja_id"))
                    if ok:
                        visiveis.append(u)
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(self.path).query)
                escopo = (qs.get("escopo") or [""])[0].strip()
                if escopo == "loja":
                    fl = (qs.get("loja_id") or [""])[0]
                    visiveis = [u for u in visiveis
                                if u.loja_id is not None and str(u.loja_id) == fl]
                elif escopo == "rede":
                    fr = (qs.get("rede_id") or [""])[0]
                    visiveis = [u for u in visiveis
                                if u.nivel == "admin_rede" and str(u.rede_id) == fr]
                elif escopo == "plataforma":
                    visiveis = [u for u in visiveis
                                if u.nivel == "super_admin"
                                and u.loja_id is None and u.rede_id is None]
                vis_ids = [u.id for u in visiveis]
                memb = {}
                if vis_ids:
                    for uid, lid in db.query(UsuarioLoja.usuario_id, UsuarioLoja.loja_id).filter(
                            UsuarioLoja.usuario_id.in_(vis_ids)).all():
                        memb.setdefault(uid, []).append(lid)
                # Função (cargo) = do Funcionário vinculado (funcionario_id → Funcao); para contas SEM
                # Funcionário, cai em Usuario.funcao_id (Perfil-4: cargo migrado do nível antigo).
                # Perfil = nivel (acesso). Os dois eixos separados.
                func_ids = {u.funcionario_id for u in visiveis if u.funcionario_id}
                funcs = {f.id: f for f in db.query(Funcionario).filter(Funcionario.id.in_(func_ids)).all()} \
                    if func_ids else {}
                funcao_ids = {f.funcao_id for f in funcs.values() if f.funcao_id} \
                    | {u.funcao_id for u in visiveis if u.funcao_id}
                funcoes_map = {fn.id: fn.nome for fn in db.query(Funcao).filter(Funcao.id.in_(funcao_ids)).all()} \
                    if funcao_ids else {}
                def _funcao_nome(u):
                    f = funcs.get(u.funcionario_id) if u.funcionario_id else None
                    if f and f.funcao_id:
                        return funcoes_map.get(f.funcao_id, "")
                    return funcoes_map.get(u.funcao_id, "") if u.funcao_id else ""
                self.send_json({"ok": True, "usuarios": [
                    {"id": u.id, "nome": u.nome, "login": u.login, "nivel": u.nivel,
                     "rotulo": perfis.rotulo(u.nivel), "telefone": u.telefone or "",
                     "whatsapp": u.whatsapp or "", "email": u.email or "", "cpf": u.cpf or "",
                     "loja_id": u.loja_id, "rede_id": u.rede_id,
                     "loja_ids": memb.get(u.id, []),
                     "funcao_nome": _funcao_nome(u),
                     "ativo": bool(u.ativo)} for u in visiveis]})
            finally:
                db.close()

        elif path == "/api/admin/perfis-matriz":
            # Admin › Perfis de Usuário: matriz perfil × capacidades da LOJA do ator (Task 7),
            # DB-backed via perfis.matriz_loja. Gate: gerir_usuarios (mesma audiência de Usuários).
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            lid = _loja_admin_alvo(usuario)
            _m = perfis.matriz_loja(lid)
            self.send_json({"ok": True, "perfis": _m["perfis"], "capacidades": _m["capacidades"],
                            "caps_selecionaveis": _m["caps_selecionaveis"],
                            "pode_editar": perfis.pode(usuario.get("nivel"), "gerir_perfis")})

        elif path == "/api/admin/perfis":
            # CRUD de perfis de acesso configuráveis por loja (Task 7). Leitura: gerir_usuarios;
            # criação/edição (POST/PATCH abaixo): gerir_perfis (só Master).
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            _m = perfis.matriz_loja(_loja_admin_alvo(usuario))
            self.send_json({"ok": True, "perfis": _m["perfis"], "capacidades": _m["capacidades"],
                            "caps_selecionaveis": _m["caps_selecionaveis"],
                            "modulos_opcoes": mod_perfis_opcoes(),
                            "pode_editar": perfis.pode(usuario.get("nivel"), "gerir_perfis")})

        elif path == "/api/admin/empresas":
            # Lojas que o ator pode administrar — alimenta o seletor de empresa (topo de Admin/Config).
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                redes = {r.id: r.nome for r in db.query(Rede).all()}
                empresas = []
                for lo in db.query(Loja).order_by(Loja.nome.asc()).all():
                    if not mod_tenancy.pode_ver_loja(ator, {"id": lo.id, "rede_id": lo.rede_id}):
                        continue
                    empresas.append({"loja_id": lo.id, "nome": lo.nome,
                                     "cnpj": lo.cnpj or "",
                                     "rede_id": lo.rede_id,
                                     "rede_nome": redes.get(lo.rede_id, "") if lo.rede_id else ""})
                self.send_json({"ok": True, "empresas": empresas})
            finally:
                db.close()
            return

        elif path == "/api/admin/usuarios/perfis-permitidos":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            from urllib.parse import parse_qs
            qs = parse_qs(urlparse(self.path).query)
            escopo = (qs.get("escopo") or [""])[0].strip()
            loja_q = (qs.get("loja_id") or [""])[0].strip()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                # loja ALVO (bug 2026-07-22): honra o loja_id do request — é o que traz os
                # perfis customizados da loja pro super_admin/admin_rede, que não têm loja
                # própria. Só dentro do escopo do ator (senão vazaria nomes de perfil).
                loja_alvo_id = None
                if loja_q.isdigit():
                    _lj = db.get(Loja, int(loja_q))
                    if _lj is not None and mod_tenancy.pode_ver_loja(
                            ator, {"id": _lj.id, "rede_id": _lj.rede_id}):
                        loja_alvo_id = _lj.id
                slugs = mod_tenancy.perfis_atribuiveis(ator, escopo, loja_id=loja_alvo_id)
                self.send_json({"ok": True, "perfis": [
                    {"slug": s, "rotulo": perfis.rotulo(s)} for s in slugs]})
            finally:
                db.close()

        elif path == "/api/admin/redes":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            db = get_session()
            try:
                redes = db.query(Rede).order_by(Rede.nome).all()
                self.send_json({"ok": True, "redes": [_rede_dict(r) for r in redes]})
            finally:
                db.close()
        elif path == "/api/admin/lojas":
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_lojas")
                                   or perfis.pode(usuario.get("nivel"), "editar_dados_loja")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            from urllib.parse import parse_qs
            rede_q = (parse_qs(urlparse(self.path).query).get("rede_id") or [""])[0].strip()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                q = db.query(Loja)
                if rede_q == "avulsas":
                    q = q.filter(Loja.rede_id.is_(None))
                elif rede_q:
                    if not rede_q.isdigit():
                        self.send_json({"ok": False, "erro": "rede_id inválido"}, code=400)
                        return
                    q = q.filter(Loja.rede_id == int(rede_q))
                lojas = [l for l in q.order_by(Loja.nome).all()
                         if mod_tenancy.pode_ver_loja(
                             ator, {"id": l.id, "rede_id": l.rede_id})]
                self.send_json({"ok": True, "lojas": [_loja_dict(l) for l in lojas]})
            finally:
                db.close()

        elif re.match(r'^/api/admin/lojas/(\d+)/pdvs$', path):
            # Pontos de Venda da loja (spec 2026-07-22): o lojista com editar_dados_loja
            # VISUALIZA seus PDVs; criar/editar é só super_admin (POST/PUT).
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            m_pdv = re.match(r'^/api/admin/lojas/(\d+)/pdvs$', path)
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                mae = db.get(Loja, int(m_pdv.group(1)))
                if mae is None or not mod_tenancy.pode_ver_loja(
                        ator, {"id": mae.id, "rede_id": mae.rede_id}):
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                pdvs = (db.query(Loja).filter(Loja.loja_mae_id == mae.id)
                          .order_by(Loja.nome).all())
                self.send_json({"ok": True, "pdvs": [_loja_dict(l) for l in pdvs]})
            finally:
                db.close()

        elif re.match(r'^/api/admin/acordos-fabrica/(\d+)/extrato$', path):
            # Extrato do acordo (spec: implantação, aplicações por loja/projeto, acertos)
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            m_ex = re.match(r'^/api/admin/acordos-fabrica/(\d+)/extrato$', path)
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                ac = db.get(AcordoFabrica, int(m_ex.group(1)))
                lj = db.get(Loja, ac.loja_titular_id) if ac else None
                if ac is None or lj is None or not mod_tenancy.pode_ver_loja(
                        ator, {"id": lj.id, "rede_id": lj.rede_id}):
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                loja_nome = {l.id: l.nome for l in db.query(Loja).all()}
                rows = (db.query(AjusteFabricaAplicacao, AjusteFabrica)
                          .join(AjusteFabrica, AjusteFabricaAplicacao.ajuste_id == AjusteFabrica.id)
                          .filter(AjusteFabrica.acordo_id == ac.id)
                          .order_by(AjusteFabricaAplicacao.id.asc()).all())
                aplicacoes = []
                for ap, aj in rows:
                    aplicacoes.append({
                        "id": ap.id, "loja": loja_nome.get(aj.loja_id, "?"),
                        "projeto": ap.projeto_nome, "tipo": aj.tipo, "pct": ap.pct_snapshot,
                        "valor": ap.valor,
                        "em": ap.criado_em.strftime("%Y-%m-%d %H:%M") if ap.criado_em else ""})
                movimentos = [{"tipo": m.tipo, "valor": m.valor,
                               "em": m.criado_em.strftime("%Y-%m-%d %H:%M") if m.criado_em else ""}
                              for m in db.query(AcordoMovimento).filter_by(acordo_id=ac.id)
                              .order_by(AcordoMovimento.id.asc()).all()]
                self.send_json({"ok": True,
                                "implantacao": {"valor": ac.valor_implantado,
                                                "em": ac.criado_em.strftime("%Y-%m-%d") if ac.criado_em else ""},
                                "aplicacoes": aplicacoes, "movimentos": movimentos})
            finally:
                db.close()

        elif path == "/api/admin/contrapartes-financeiras":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            db = get_session()
            try:
                cps = [_contraparte_dict(c) for c in db.query(ContraparteFinanceira)
                       .order_by(ContraparteFinanceira.nome.asc()).all()]
                self.send_json({"ok": True, "contrapartes": cps})
            finally:
                db.close()

        elif path == "/api/admin/acordos-fabrica":
            # Ajustes Excepcionais de Fábrica: lista de acordos visíveis com os TRÊS saldos
            # (contábil, pendente de acerto, disponível) + ajustes aninhados + avulsos (custo).
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                visiveis = set()
                for lj in db.query(Loja).all():
                    if mod_tenancy.pode_ver_loja(ator, {"id": lj.id, "rede_id": lj.rede_id}):
                        visiveis.add(lj.id)
                acordos = []
                for ac in db.query(AcordoFabrica).order_by(AcordoFabrica.id.asc()).all():
                    if ac.loja_titular_id not in visiveis:
                        continue
                    acordos.append({"id": ac.id, "descricao": ac.descricao, "tipo": ac.tipo,
                                    "contraparte_tipo": ac.contraparte_tipo or "fabrica",
                                    "contraparte_nome": ac.contraparte_nome or "",
                                    "loja_titular_id": ac.loja_titular_id,
                                    "conta_saldo": ac.conta_saldo, "status": ac.status,
                                    "valor_implantado": ac.valor_implantado,
                                    "saldos": _acordo_saldos(db, ac),
                                    "ajustes": [_ajuste_fabrica_dict(a) for a in ac.ajustes]})
                avulsos = [_ajuste_fabrica_dict(a) for a in
                           db.query(AjusteFabrica).filter(AjusteFabrica.acordo_id.is_(None)).all()
                           if a.loja_id in visiveis]
                self.send_json({"ok": True, "acordos": acordos, "ajustes_avulsos": avulsos})
            finally:
                db.close()

        elif path.startswith("/api/admin/lojas/") and path.endswith("/config-financeira"):
            import re as _re, mod_provisoes
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            m = _re.match(r"^/api/admin/lojas/(\d+)/config-financeira$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m.group(1)))
                if not loja or not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Loja fora do escopo"}, code=403); return
                # Merge com o default preenche chaves novas (ex.: cronograma_padrao, v11) em lojas
                # cujo config foi salvo antes da chave existir — sem apagar valores já configurados.
                # Normaliza o STORED antes do merge: config legada (sem cronograma_formato) é
                # convertida de acumulado para durações.
                _stored = mod_provisoes.normalizar_cronograma_formato(
                    json.loads(loja.config_financeira_json) if loja.config_financeira_json else {})
                cfg = {**mod_provisoes.config_financeira_default(), **_stored}
                import mod_cronograma as _mcr_cfg
                from datetime import datetime as _dt_cfg
                _cabe = _mcr_cfg.padrao_cabe_no_prazo_contratual(cfg, _dt_cfg(2026, 1, 5))  # 2026-01-05 = segunda
                self.send_json({"ok": True, "config": cfg, "padrao_cabe_prazo": _cabe})
            finally:
                db.close()

        elif path.startswith("/api/admin/lojas/") and path.endswith("/projetos"):
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_redes")
                                   or perfis.pode(usuario.get("nivel"), "gerir_lojas")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            import re as _re
            m = _re.match(r"^/api/admin/lojas/(\d+)/projetos$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                projetos = mod_arvore.projetos_estruturais(db, ator, int(m.group(1)))
                self.send_json({"ok": True, "projetos": projetos})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except LookupError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=404)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif path.startswith("/api/admin/projetos/") and path.endswith("/etapas"):
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_redes")
                                   or perfis.pode(usuario.get("nivel"), "gerir_lojas")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            import re as _re
            m = _re.match(r"^/api/admin/projetos/(.+)/etapas$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                etapas = mod_arvore.etapas_do_projeto(db, ator, unquote(m.group(1)))
                self.send_json({"ok": True, "etapas": etapas})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except LookupError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=404)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif path.rsplit(".", 1)[-1].lower() in ("png", "svg", "ico", "jpg", "jpeg", "webp", "gif") and path != "/":
            # Assets estáticos (logomarca, favicon, ícones) servidos de static/
            ext     = path.rsplit(".", 1)[-1].lower()
            nome    = os.path.basename(path.lstrip("/"))
            caminho = os.path.join(_STATIC_DIR, nome)
            _CT = {"png": "image/png", "svg": "image/svg+xml", "ico": "image/x-icon",
                   "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}
            if os.path.exists(caminho):
                with open(caminho, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", _CT.get(ext, "application/octet-stream"))
                self.send_header("Content-Length", len(data))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)
            return

        elif path.endswith(".css") and path != "/":
            # CSS do design system (design-system/*.css) servido da RAIZ do projeto —
            # design-system/ é a fonte única (não duplicamos em static/).
            rel     = os.path.normpath(path.lstrip("/")).replace("\\", "/")
            caminho = os.path.abspath(os.path.join(_BASE_DIR, rel))
            # trava de path traversal: precisa ficar dentro de _BASE_DIR
            if not caminho.startswith(os.path.abspath(_BASE_DIR) + os.sep) or not os.path.exists(caminho):
                self.send_error(404); return
            with open(caminho, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", len(data))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return

        elif path.endswith(".html") and path != "/":
            nome    = path.lstrip("/")
            caminho = os.path.join(_BASE_DIR, nome)
            if os.path.exists(caminho):
                with open(caminho, encoding="utf-8") as f:
                    body = f.read().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
            return

        else:
            import re as _re
            # GET /pagamentos/<codigo>/faixas
            m_pf = _re.match(r"^/pagamentos/([^/]+)/faixas$", path)
            if m_pf:
                codigo = m_pf.group(1)
                try:
                    import mod_fin as _mf
                    tab    = _mf._carregar(codigo)
                    tipo   = tab.get("tipo", "")
                    faixas = _normalizar_faixas(tab)
                    desconto_avista = float(tab.get("desconto_pct", 0)) if tipo == "avista" else 0.0
                except Exception as e:
                    print("[FAIXAS] Erro ao carregar %s: %s" % (codigo, e))
                    faixas = [{"parcelas": 1, "custo_pct": 0.0, "label": "A Vista"}]
                    tipo = "avista"; desconto_avista = 0.0
                self.send_json({"ok": True, "faixas": faixas, "tipo": tipo,
                                "desconto_avista": desconto_avista})
                return

            # ── GET /projetos/<nome>/pool?orcamento_id=<id> ───────────────────────────
            m = _re.match(r"^/projetos/([^/]+)/pool$", path)
            if m:
                from urllib.parse import parse_qs
                nome_safe    = m.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                qs           = parse_qs(urlparse(self.path).query)
                orcamento_id = qs.get("orcamento_id", [None])[0]
                orcamento_id = int(orcamento_id) if orcamento_id else None
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    ambientes = (db.query(PoolAmbiente)
                                   .filter_by(projeto_id=nome_safe)
                                   .order_by(PoolAmbiente.nome, PoolAmbiente.versao)
                                   .all())
                    incluidos = set()
                    if orcamento_id:
                        links = (db.query(OrcamentoAmbiente)
                                   .filter_by(orcamento_id=orcamento_id)
                                   .all())
                        incluidos = {lk.pool_ambiente_id for lk in links}
                    pool = []
                    for pa in ambientes:
                        d = _pool_ambiente_dict(pa)
                        d["incluido"] = pa.id in incluidos
                        pool.append(d)
                    self.send_json({"ok": True, "pool": pool})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # ── GET /orcamentos/<oid>/ambientes — listar ambientes do orçamento ─────
            m = _re.match(r"^/orcamentos/(\d+)/ambientes$", path)
            if m:
                oid = int(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db  = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    links = (db.query(OrcamentoAmbiente)
                               .filter_by(orcamento_id=oid)
                               .order_by(OrcamentoAmbiente.ordem)
                               .all())
                    ambientes = []
                    for lk in links:
                        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
                        if pa:
                            d = _pool_ambiente_dict(pa)
                            d["ordem"] = lk.ordem
                            d["desconto_individual_pct"] = lk.desconto_individual_pct or 0.0
                            ambientes.append(d)
                    desconto_pct = (orc.desconto_pct or 0.0) if orc else 0.0
                    negociacao = json.loads(orc.negociacao_json) if (orc and orc.negociacao_json) else None
                    parametros = {}
                    if orc:
                        _p = db.get(Projeto, orc.projeto_id)
                        if _p and _p.parametros_json:
                            parametros = json.loads(_p.parametros_json)   # respeita o salvo (edições persistem)
                        else:
                            # projeto sem params salvos: valores iniciais (defaults da loja +
                            # arquiteto/fidelidade do parceiro, se houver)
                            parametros = _params_iniciais_projeto(db, orc.projeto_id, orc.loja_id)
                    self.send_json({"ok": True, "orcamento_id": oid,
                                    "desconto_pct": desconto_pct, "negociacao": negociacao,
                                    "parametros": parametros, "ambientes": ambientes})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # ── GET /api/orcamentos/<id>/provisoes — versões + atual + desatualizado ──
            m = _re.match(r"^/api/orcamentos/(\d+)/provisoes$", path)
            if m:
                # NOTE: bare `mod_provisoes` vira local no do_GET (import local num elif adiante);
                # usar alias evita UnboundLocalError.
                import mod_provisoes as _mprov
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "aprovar_financeiro"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                oid = int(m.group(1))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return

                    def _reg(versao):
                        r = db.query(ProvisaoRegistro).filter_by(orcamento_id=oid, versao=versao).first()
                        if not r:
                            return None
                        return {"itens": json.loads(r.itens_json), "cfo": r.cfo, "val_liq": r.val_liq,
                                "cust_var": r.cust_var, "marg_cont": r.marg_cont, "decisao": r.decisao,
                                "criado_em": r.criado_em.isoformat() if r.criado_em else None,
                                "travada": getattr(r, "travada_em", None) is not None}

                    venda = _reg("venda")
                    d = _negociacao_breakdown(orc, db)
                    atual = {"itens": _mprov.itens_provisao(d),
                             "cfo": float(d.get("CFO") or 0),
                             "val_liq": float(d.get("Val_Liq") or 0),
                             "cust_var": float(d.get("Cust_Var") or 0),
                             "marg_cont": float(d.get("Marg_Cont") or 0),
                             # As 3 margens da venda (visão) — Contribuição/Venda/Contrato (NOMENCLATURA §3c)
                             "margens": _mprov.margens_venda(
                                 d.get("VAVO"), d.get("Cust_Ad"),
                                 float(d.get("Cust_Var") or 0), d.get("Val_Cont"))}
                    # Compara só as rubricas que o snapshot conhece: um snapshot pré-fold (10 chaves)
                    # não deve acusar "desatualizado" apenas porque 'atual' ganhou prov_mont/prov_gar
                    # (FASE 2). Snapshot novo (12 chaves) → comparação íntegra, inclui o drift das 2.
                    desatualizado = bool(venda and any(
                        venda["itens"].get(k) != atual["itens"].get(k) for k in venda["itens"]))
                    # custos adicionais (arq/fidelidade/viagem/brinde/custo especial): já descontados do
                    # Val. Líquido pelo motor — exibidos à parte, não somam no Cust_Var.
                    custos_adicionais = {
                        "com_arq":  float(d.get("Com_Arq")  or 0),
                        "pro_fid":  float(d.get("Pro_Fid")  or 0),
                        "cust_via": float(d.get("Cust_Via") or 0),
                        "brinde":   float(d.get("Bri")      or 0),
                        "cust_esp": float(d.get("Cust_Esp") or 0),
                        "total":    float(d.get("Cust_Ad")  or 0),
                        "cust_fin": float(d.get("Cust_Fin") or 0),   # custo financeiro (informativo)
                    }
                    self.send_json({"ok": True, "provisoes": {
                        "venda": venda, "rev1": _reg("rev1"), "rev2": _reg("rev2"),
                        "atual": atual, "desatualizado": desatualizado,
                        "custos_adicionais": custos_adicionais}})
                finally:
                    db.close()
                return

            # ── GET /api/orcamentos/<id>/ramo-financeiro — ramo atual do custo financeiro (box AF, Fatia B) ──
            m = _re.match(r"^/api/orcamentos/(\d+)/ramo-financeiro$", path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                oid = int(m.group(1))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    self.send_json({"ok": True,
                                    "ramo": _ramo_financeiro_efetivo(orc),
                                    "override": bool(getattr(orc, "ramo_financeiro", None)),
                                    "cust_fin": _cust_fin_orc(orc)})
                finally:
                    db.close()
                return

            # ── GET /api/orcamentos/<id>/proposta/pdf — gera proposta sob demanda ──
            m = _re.match(r"^/api/orcamentos/(\d+)/proposta/pdf$", path)
            if m:
                import tempfile, shutil
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                oid = int(m.group(1))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    _proj, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(orc.projeto_id, oid, db)
                    loja_dict = _loja_dict_para_contrato(db, loja_id)
                    usuario_ctx = {"nome": usuario.get("nome", ""),
                                   "telefone": _get_usuario_telefone(usuario["id"], db),
                                   "email": usuario.get("email", "") or ""}
                    # Proposta = PRIMEIRA PÁGINA do contrato (capa) via WeasyPrint, numerada com 'PV...'.
                    from mod_contrato import (construir_contexto as _cc,
                                              gerar_num_proposta as _gnp, gerar_pdf_proposta as _gpp)
                    ctx = _cc(cliente_dict, usuario_ctx, orc.forma_pagamento or "", loja_dict)
                    ctx["_ambientes"] = _ambientes_valor_para_contrato(oid, db)
                    # Número da proposta gerado uma vez e persistido no orçamento (sequencial por 'PV').
                    if not orc.num_proposta:
                        _existing = [o.num_proposta for o in db.query(Orcamento)
                                     .filter(Orcamento.num_proposta.isnot(None)).all()]
                        orc.num_proposta = _gnp(_existing)
                        db.commit()
                    ctx["num_contrato"] = orc.num_proposta   # marcador [NUM_CONTRATO] da capa
                    ctx["_db"] = db   # corpo da proposta vem do modelo da loja (se houver)
                    outdir = tempfile.mkdtemp(prefix="proposta_")
                    try:
                        pdf_path = os.path.join(outdir, "proposta_%d.pdf" % oid)
                        _gpp(ctx, pdf_path)
                        with open(pdf_path, "rb") as fh:
                            data = fh.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/pdf")
                        self.send_header("Content-Length", len(data))
                        self.send_header("Content-Disposition",
                                         'inline; filename="proposta_%d.pdf"' % oid)
                        self.end_headers()
                        self.wfile.write(data)
                    finally:
                        shutil.rmtree(outdir, ignore_errors=True)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/projetos/([^/]+)/orcamentos$", path)
            if m:
                nome_safe = m.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                print("[ORC] GET orcamentos para projeto_id=%r" % nome_safe)
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    orcs = (db.query(Orcamento)
                              .filter_by(projeto_id=nome_safe)
                              .order_by(Orcamento.ordem)
                              .all())
                    print("[ORC] encontrados %d orcamento(s)" % len(orcs))
                    # FASE D2 (Ajuste 1): expõe o orçamento CONTRATADO p/ o seletor travar nele por padrão
                    # (reaproveita esta chamada — sem endpoint novo). None se o projeto ainda não tem contrato.
                    _contrato = (db.query(Contrato).filter_by(projeto_nome=nome_safe)
                                 .order_by(Contrato.id.desc()).first())
                    self.send_json({"ok": True, "orcamentos": [_orcamento_dict(o) for o in orcs],
                                    "contratado_id": (_contrato.orcamento_id if _contrato else None)})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/projetos/([^/]+)$", path)
            if m:
                nome_safe = m.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    _meta = _projeto_da_loja(db, nome_safe, loja_id)
                    if _meta is None or not _projeto_visivel_ao_ator(_meta, usuario, db):
                        # escopo por projetista: consultor não abre projeto de outro
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"}, code=404)
                        return
                    _enriquecer_cliente_do_projeto(proj, db)   # contato sempre do cadastro vivo
                    try:
                        proj['loja_id'] = _meta.loja_id
                    except Exception:
                        pass
                    session_set("projeto_ativo", nome_safe)
                    self.send_json({"ok": True, "projeto": proj})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/api/clientes/(\d+)$", path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    c = _obj_da_loja(db, Cliente, int(m.group(1)), loja_id)
                    if c:
                        self.send_json({"ok": True, "cliente": _cliente_dict(c)})
                    else:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/api/parceiros/(\d+)$", path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    p = db.get(Parceiro, int(m.group(1)))
                    if p is None or not _parceiro_visivel_loja(db, p, loja_id):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r"^/api/clientes/(\d+)/projetos$", path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    c = _obj_da_loja(db, Cliente, int(m.group(1)), loja_id)
                    if not c:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    nome_lower = c.nome.lower()
                    projetos = [
                        p for p in _listar_projetos()
                        if p.get("cliente_id") == c.id
                        or p.get("cliente_nome", "").lower() == nome_lower
                    ]
                    _enriquecer_projetos_com_pool(projetos)
                    self.send_json({"ok": True, "projetos": projetos, "cliente": _cliente_dict(c)})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/parametros$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    p = _projeto_da_loja(db, nome_safe, loja_id)
                    if p is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    par = (json.loads(p.parametros_json) if p.parametros_json
                           else _params_iniciais_projeto(db, nome_safe, loja_id))
                    self.send_json({"ok": True, "parametros": par})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/contatos-comunicacao — confirmação de contatos na fase
            # de contrato (decisão 13): contatos vivos do cadastro + confirmação vigente.
            m = _re.match(r'^/api/projetos/([^/]+)/contatos-comunicacao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    import mod_chat
                    # Alias OBRIGATÓRIO: import local sem alias tornaria '_carregar_projeto'
                    # LOCAL ao método inteiro e quebraria os outros handlers que usam o nome
                    # (mesma armadilha do construir_contexto documentada no preview — pega por
                    # execução, não por leitura; derrubou 11 testes de parceiro/escopo).
                    from integracoes.projetos_store import _carregar_projeto as _cp_chat
                    p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                    pj = _cp_chat(nome_safe) or {}
                    contatos = mod_chat.contatos_do_projeto(
                        db, cliente_id=(p_meta.cliente_id if p_meta else None),
                        parceiro_id=pj.get("parceiro_id"))
                    reg = mod_chat.confirmacao_vigente(db, loja_id, nome_safe)
                    quem = None
                    if reg is not None and reg.confirmado_por_id:
                        u = db.get(Usuario, reg.confirmado_por_id)
                        quem = u.nome if u else None
                    self.send_json({"ok": True, "contatos": contatos,
                                    "confirmacao": mod_chat.serializar_confirmacao(reg, quem)})
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/conversa — aba Conversa (chat Fatia 1): get-or-create
            # da conversa do projeto + histórico cronológico de mensagens internas.
            m = _re.match(r'^/api/projetos/([^/]+)/conversa$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_visivel_da_loja(db, nome_safe, loja_id, usuario) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    import mod_chat, mod_equipe
                    p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                    conv = mod_chat.get_or_create_conversa_projeto(
                        db, loja_id, nome_safe,
                        cliente_id=(p_meta.cliente_id if p_meta else None))
                    # membership: mantém os participantes em dia com a equipe derivada do projeto
                    try:
                        _eqp = mod_equipe.equipe_do_projeto(db, nome_safe, loja_id)
                        mod_chat.sincronizar_participantes_projeto(db, conv, _eqp["membros_usuarios"])
                    except Exception as _es:
                        print("[EQUIPE] sync participantes na abertura falhou:", _es)
                    db.commit()
                    self.send_json({"ok": True,
                                    "conversa": {"id": conv.id,
                                                 "projeto_nome": conv.projeto_nome,
                                                 "cliente_id": conv.cliente_id},
                                    "mensagens": mod_chat.listar_mensagens(db, conv.id)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/inbox — Central de Comunicação (Fatia 1): conversas
            # direct/grupo de que o usuário participa, na loja ativa.
            if path == "/api/comunicacao/inbox":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat, mod_chat_externo
                    # Sweep preguiçoso da triagem vencida (2026-08-05): sem job em background,
                    # aproveita a leitura do inbox (roda em toda carga de tela + poll de badge)
                    # pra materializar entradas paradas há mais de 2min — ver
                    # chat.triagem.varrer_triagem_vencida.
                    mod_chat_externo.varrer_triagem_vencida(db, loja_id)
                    _inbox = mod_chat.listar_inbox(db, loja_id, usuario["id"])
                    db.commit()   # get_or_create_publico pode ter criado o mural da loja + sweep
                    self.send_json({"ok": True, "conversas": _inbox})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/janela?telefone= — Atendimentos UI (spec 2026-08-04 §11): a
            # etapa 1/2 do Iniciar Conversa precisa saber se JÁ há janela aberta com o telefone
            # ANTES de a conversa existir (decide se "Mensagem livre" pode ser oferecida).
            if path == "/api/comunicacao/janela":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    from urllib.parse import parse_qs as _pq_jan
                    tel = (_pq_jan(urlparse(self.path).query).get('telefone') or [''])[0].strip()
                    import mod_chat_externo as _mwj
                    self.send_json({"ok": True, **_mwj.janela_por_telefone(db, loja_id, tel)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/conversas/<id>/exportar?formato=txt|pdf — barra de ação
            # (spec 2026-08-04 §7.1 item 3). Download direto (não é fetch+JSON).
            m_exp_conv = re.match(r'^/api/comunicacao/conversas/(\d+)/exportar$', path)
            if m_exp_conv:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    from database import Conversa as _CV_exp
                    conv = db.get(_CV_exp, int(m_exp_conv.group(1)))
                    if conv is None or conv.loja_id != loja_id:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    _adm = perfis.pode(usuario.get("nivel"), "ver_todas_conversas")
                    if not (_adm or mod_chat.eh_participante(db, conv.id, usuario["id"])):
                        self.send_json({"ok": False, "erro": "Você não participa desta conversa."},
                                       code=403); return
                    from urllib.parse import parse_qs as _pq_exp
                    formato = (_pq_exp(urlparse(self.path).query).get('formato') or ['txt'])[0]
                    if formato == "pdf":
                        from weasyprint import HTML as _WeasyHTML
                        data = _WeasyHTML(string=mod_chat.exportar_conversa_html(db, conv)).write_pdf()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/pdf")
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Content-Disposition",
                                         'attachment; filename="conversa_%d.pdf"' % conv.id)
                        self.end_headers()
                        self.wfile.write(data)
                    else:
                        data = mod_chat.exportar_conversa_txt(db, conv).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.send_header("Content-Length", str(len(data)))
                        self.send_header("Content-Disposition",
                                         'attachment; filename="conversa_%d.txt"' % conv.id)
                        self.end_headers()
                        self.wfile.write(data)
                finally:
                    db.close()
                return

            # GET /api/comunicacao/assuntos — Orizon Chat (Fatia 2): opções do seletor "Assunto":
            # assuntos custom da loja + a lista de PROJETOS visíveis (Conversa Livre é fixa na UI).
            if path == "/api/comunicacao/assuntos":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    projs = [{"nome_safe": p.nome_safe,
                              "nome": (p.nome_safe or "").replace("_", " ")}
                             for p in db.query(Projeto)
                                        .filter(Projeto.loja_id == loja_id)
                                        .order_by(Projeto.nome_safe.asc()).all()
                             if _projeto_visivel_ao_ator(p, usuario, db)]
                    self.send_json({"ok": True,
                                    "assuntos": mod_chat.listar_assuntos(db, loja_id),
                                    "projetos": projs})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/admin/conversas — painel de administração (ver_todas_conversas):
            # TODAS as conversas da loja, com filtro ?participante=&assunto_tipo=&assunto_ref=.
            if path == "/api/comunicacao/admin/conversas":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "ver_todas_conversas"):
                    self.send_json({"ok": False, "erro": "Sem acesso ao painel de conversas."}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    from urllib.parse import parse_qs as _pq_adm
                    qs = _pq_adm(urlparse(self.path).query)
                    self.send_json({"ok": True, "conversas": mod_chat.listar_todas_conversas(
                        db, loja_id,
                        participante_id=(qs.get("participante", [None])[0] or None),
                        assunto_tipo=(qs.get("assunto_tipo", [None])[0] or None),
                        assunto_ref=(qs.get("assunto_ref", [None])[0] or None))})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/forum — Fatia 4: lista de DEBATES de um fórum. ?escopo=loja|orizon
            # &q=<busca no título>&assunto_tipo=&assunto_ref=. orizon é cross-loja (pela rede).
            if path == "/api/comunicacao/forum":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    from urllib.parse import parse_qs as _pq_f
                    qs = _pq_f(urlparse(self.path).query)
                    escopo = (qs.get("escopo", ["loja"])[0] or "loja")
                    rede = mod_chat._rede_da_loja(db, loja_id)
                    self.send_json({"ok": True, "rede_id": rede,
                                    "debates": mod_chat.listar_debates(
                                        db, escopo, loja_id, rede,
                                        q=(qs.get("q", [None])[0] or None),
                                        assunto_tipo=(qs.get("assunto_tipo", [None])[0] or None),
                                        assunto_ref=(qs.get("assunto_ref", [None])[0] or None))})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/anexos/<id> — Fatia 5: baixa/serve um anexo (só quem lê a conversa).
            m_anxg = _re.match(r'^/api/comunicacao/anexos/(\d+)$', path)
            if m_anxg:
                anexo_id = int(m_anxg.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    from database import MensagemAnexo as _MA, ConversaMensagem as _CMx, Conversa as _CVx
                    a = db.get(_MA, anexo_id)
                    msg = db.get(_CMx, a.mensagem_id) if a else None
                    conv = db.get(_CVx, msg.conversa_id) if msg else None
                    _rede = mod_chat._rede_da_loja(db, loja_id)
                    _adm = perfis.pode(usuario.get("nivel"), "ver_todas_conversas")
                    if (a is None or conv is None
                            or not (mod_chat.pode_ler_conversa(db, conv, loja_id, usuario["id"], rede_id=_rede)
                                    or (_adm and conv.loja_id == loja_id))):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    caminho = os.path.join(_BASE_DIR, "COMUNICACAO", a.caminho)
                    if not os.path.exists(caminho):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    conteudo = storage_ler_binario(caminho)
                    self.send_response(200)
                    self.send_header("Content-Type", a.mime or "application/octet-stream")
                    self.send_header("Content-Disposition", 'inline; filename="%s"' % (a.nome or "arquivo"))
                    self.send_header("Content-Length", str(len(conteudo)))
                    self.end_headers()
                    self.wfile.write(conteudo)
                finally:
                    db.close()
                return

            # GET /api/comunicacao/usuarios — usuários da loja ativa para o seletor "Para"
            # (Central de Comunicação). Exclui o próprio usuário. Filtro opcional ?q=.
            if path == "/api/comunicacao/usuarios":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    from urllib.parse import parse_qs as _pq_com
                    q = (_pq_com(urlparse(self.path).query).get("q", [""])[0] or "").strip().lower()
                    us = (db.query(Usuario)
                            .filter(Usuario.loja_id == loja_id, Usuario.ativo == 1,
                                    Usuario.id != usuario["id"])
                            .order_by(Usuario.nome.asc()).all())
                    fmap = {f.id: f.nome for f in db.query(Funcao)
                            .filter(Funcao.loja_id == loja_id).all()}
                    itens = [{"id": u.id, "nome": u.nome,
                              "funcao_nome": fmap.get(u.funcao_id)}
                             for u in us
                             if (not q or q in (u.nome or "").lower())]
                    self.send_json({"ok": True, "usuarios": itens})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/conversas/<id>/participantes — membros da conversa (projeto):
            # lista participante/gerência; devolve origem (auto|manual) para a UI de override.
            m_cp = _re.match(r'^/api/comunicacao/conversas/(\d+)/participantes$', path)
            if m_cp:
                conv_id = int(m_cp.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    from database import Conversa as _CV_p
                    conv = db.get(_CV_p, conv_id)
                    _adm = perfis.pode(usuario.get("nivel"), "ver_todas_conversas")
                    if (conv is None or conv.loja_id != loja_id
                            or not (mod_chat.eh_participante(db, conv_id, usuario["id"]) or _adm)):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    self.send_json({"ok": True, "pode_gerir": bool(_adm),
                                    "participantes": mod_chat.listar_participantes(db, conv)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/templates — biblioteca de templates da Meta (RF-07). Gerência.
            if path == "/api/comunicacao/templates" or path.startswith("/api/comunicacao/templates?"):
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "autorizar"):
                    self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    from urllib.parse import parse_qs
                    # Seed lazy (2026-08-04): loja VIRGEM de templates ganha os 9 modelos iniciais
                    # (rascunho) no primeiro carregamento da tela. Idempotente — remoções não voltam.
                    if mod_chat.seed_templates_iniciais(db, loja_id):
                        db.commit()
                    seg = (parse_qs(urlparse(self.path).query).get("segmento") or [None])[0]
                    self.send_json({"ok": True, "slots": list(mod_chat.SLOTS_OBRIGATORIOS),
                                    "templates": mod_chat.listar_templates(db, loja_id, segmento=seg)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/triagem — config da pergunta de triagem (RF-08). Gerência.
            if path == "/api/comunicacao/triagem":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "autorizar"):
                    self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    self.send_json({"ok": True, "triagem": mod_chat.triagem_config_get(db, loja_id)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/segmentos/ativos — lista LEVE dos segmentos ativos da loja
            # (base + custom) para os seletores da F7/triagem. Qualquer usuário autenticado.
            if path == "/api/comunicacao/segmentos/ativos":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    self.send_json({"ok": True, "segmentos": mod_chat.segmentos_ativos(db, loja_id)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/segmentos — config dos 7 segmentos (RF-02). Gerência.
            if path == "/api/comunicacao/segmentos":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "autorizar"):
                    self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    self.send_json({"ok": True, "segmentos": mod_chat.segmentos_config_get(db, loja_id)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/numeros — número WhatsApp da loja + status do transporte (RF-01). Gerência.
            if path == "/api/comunicacao/numeros":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "autorizar"):
                    self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    self.send_json({"ok": True, "numero": mod_chat.numero_conectado_get(db, loja_id)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/consumo — envios de WhatsApp por segmento (§10). Gerência.
            if path == "/api/comunicacao/consumo":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "autorizar"):
                    self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    self.send_json({"ok": True, "consumo": mod_chat.consumo_por_segmento(db, loja_id)})
                finally:
                    db.close()
                return

            # GET /api/comunicacao/conversas/<id>/mensagens — histórico de uma conversa
            # direct/grupo (só participante lê).
            m_cm = _re.match(r'^/api/comunicacao/conversas/(\d+)/mensagens$', path)
            if m_cm:
                conv_id = int(m_cm.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    import mod_chat
                    from database import Conversa as _CV_get
                    conv = db.get(_CV_get, conv_id)
                    # Leitura: participante/público/rede OU gerente/diretor (ver_todas_conversas).
                    _admin_chat = perfis.pode(usuario.get("nivel"), "ver_todas_conversas")
                    _rede = mod_chat._rede_da_loja(db, loja_id)
                    if (conv is None
                            or not (mod_chat.pode_ler_conversa(db, conv, loja_id, usuario["id"], rede_id=_rede)
                                    or (_admin_chat and conv.loja_id == loja_id))):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    # marca como lida (não p/ oversight de não-participante — marcar_lido já filtra)
                    mod_chat.marcar_lido(db, conv, usuario["id"]); db.commit()
                    self.send_json({"ok": True,
                                    "conversa": mod_chat.serializar_conversa(db, conv, usuario["id"]),
                                    "mensagens": mod_chat.listar_mensagens(db, conv_id)})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/ciclo$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    etapas = db.query(CicloEtapa)\
                               .filter_by(projeto_nome=nome_safe)\
                               .all()
                    codigos_existentes = {e.etapa_codigo for e in etapas}
                    # Auto-completar etapas 1-4 para projetos que já têm negociação
                    ETAPAS_PRE = ["1","2","3","4"]
                    if not any(c in codigos_existentes for c in ETAPAS_PRE):
                        p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                        eh_legado = (p_meta is None) or (p_meta.cliente_id is None)
                        tem_negociacao = db.query(Orcamento).filter(
                            Orcamento.projeto_id == nome_safe,
                        ).count() > 0
                        if tem_negociacao and eh_legado:
                            agora = datetime.utcnow()
                            for cod in ETAPAS_PRE:
                                nova = CicloEtapa(
                                    projeto_nome=nome_safe,
                                    etapa_codigo=cod,
                                    status="concluido",
                                    concluido_em=agora,
                                )
                                db.add(nova)
                                etapas.append(nova)
                            db.commit()
                    etapas_sorted = sorted(etapas, key=lambda e: mod_ciclo.chave_ordenacao(e.etapa_codigo))
                    # Responsável por função (v12): resolve nomes de função e do funcionário escolhido (batch).
                    _fnc_ids = {e.funcao_responsavel_id for e in etapas_sorted if e.funcao_responsavel_id}
                    _fnc_map = {f.id: f.nome for f in db.query(Funcao).filter(Funcao.id.in_(_fnc_ids)).all()} \
                        if _fnc_ids else {}
                    _fio_ids = {e.responsavel_funcionario_id for e in etapas_sorted if e.responsavel_funcionario_id}
                    _fio_map = {f.id: f.nome for f in db.query(Funcionario).filter(Funcionario.id.in_(_fio_ids)).all()} \
                        if _fio_ids else {}
                    # Mapa de Atribuições (Fase 1) é o DEFAULT do responsável da fase; o
                    # responsavel_funcionario_id (v12) é o override pontual. Efetivo = override OU Mapa.
                    _atrib = _atribuicoes_dicts(db, nome_safe)
                    _faixa_cache = {}   # Fatia 2: 1 resolução por faixa por request
                    # Revisão 2026-07-25 (decisão 16): CRIADOR do projeto é o dono-base — resolve
                    # o "não atribuído". Usuário → Funcionário pela ponte; None se não vinculado.
                    _proj_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                    _criador_fid = (_funcionario_do_usuario(db, _proj_meta.criado_por_id)
                                    if _proj_meta and _proj_meta.criado_por_id else None)
                    _criador_nome = ""
                    if _proj_meta and _proj_meta.criado_por_id:
                        _cu = db.get(Usuario, _proj_meta.criado_por_id)
                        _criador_nome = _cu.nome if _cu else ""
                    def _resp_efetivo(e):
                        if e.responsavel_funcionario_id:
                            return e.responsavel_funcionario_id
                        papel = _ETAPA_PAPEL.get(e.etapa_codigo)
                        a = mod_escopo.resolver_responsavel(_atrib, None, papel) if papel else None
                        if a and a.get("funcionario_id"):
                            return a.get("funcionario_id")
                        # Fatia 2 (spec seção 6): default por FAIXA — Vendas (consultor via
                        # ponte Usuário↔Funcionário), Financeiro e Logística (por Função).
                        fid = _default_responsavel_faixa(db, nome_safe, loja_id,
                                                         e.etapa_codigo, _faixa_cache)
                        # Revisão: sem faixa, o CRIADOR fica com a bola (nunca "não atribuído").
                        return fid or _criador_fid
                    _efet_by_cod = {e.etapa_codigo: _resp_efetivo(e) for e in etapas_sorted}
                    _efet_ids = {i for i in _efet_by_cod.values() if i}
                    _efet_map = {f.id: f.nome for f in db.query(Funcionario).filter(Funcionario.id.in_(_efet_ids)).all()} \
                        if _efet_ids else {}
                    resultado = [{
                        "etapa_codigo":  e.etapa_codigo,
                        "status":        e.status,
                        "responsavel_id": e.responsavel_id,
                        "iniciado_em":   e.iniciado_em.isoformat() if e.iniciado_em else None,
                        "concluido_em":  e.concluido_em.isoformat() if e.concluido_em else None,
                        # Cronograma do Ciclo (v11): data prevista (D0+prazo) e data de conclusão
                        # (= concluido_em, exposta com o nome do spec).
                        "data_prevista_conclusao": e.data_prevista_conclusao.isoformat() if e.data_prevista_conclusao else None,
                        "data_conclusao": e.concluido_em.isoformat() if e.concluido_em else None,
                        # Responsável por função (v12): função exigida (herdada) + funcionário escolhido.
                        "funcao_responsavel_id":   e.funcao_responsavel_id,
                        "funcao_responsavel_nome": _fnc_map.get(e.funcao_responsavel_id, ""),
                        "responsavel_funcionario_id":   e.responsavel_funcionario_id,
                        "responsavel_funcionario_nome": _fio_map.get(e.responsavel_funcionario_id, ""),
                        # Responsável EFETIVO (Fase 1): override da etapa OU default do Mapa de Atribuições.
                        "responsavel_efetivo_id":   _efet_by_cod.get(e.etapa_codigo),
                        "responsavel_efetivo_nome": _efet_map.get(_efet_by_cod.get(e.etapa_codigo), ""),
                        "observacoes":   e.observacoes or "",
                    } for e in etapas_sorted]
                    assinado = _contrato_assinado(nome_safe, db)
                    total_assinado = _contrato_totalmente_assinado(nome_safe, db)
                    self.send_json({"ok": True, "ciclo": resultado,
                                    "contrato_assinado": assinado,
                                    "contrato_totalmente_assinado": total_assinado,
                                    # Revisão 2026-07-25: nome do criador p/ a tag "com a bola"
                                    # quando nenhum Funcionário responsável resolve (fallback visual).
                                    "criado_por_id": (_proj_meta.criado_por_id if _proj_meta else None),
                                    "criado_por_nome": _criador_nome})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/atribuicoes — Mapa de Atribuições (Regras §4). Abrir/editar só
            # Gerência+ e Supervisor de Montagem.
            m = _re.match(r'^/api/projetos/([^/]+)/atribuicoes$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not _pode_editar_mapa(ator.get("nivel")):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    self.send_json({"ok": True, "papeis": list(mod_escopo.PAPEIS),
                                    "atribuicoes": _serializar_atribuicoes(db, nome_safe),
                                    "ambientes": _ambientes_do_projeto(db, nome_safe)})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/arquivo/(solicitacao|planta|doc_cliente)$', path)
            if m:
                nome_safe = unquote(m.group(1)); tipo = m.group(2)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    fname = md and getattr(md, tipo + "_arquivo", None)
                finally:
                    db.close()
                if not fname:
                    self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404); return
                caminho = os.path.join(_projeto_path(nome_safe), "medicao", fname)
                try:
                    data = storage_ler_binario(caminho)
                except Exception:
                    self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404); return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", len(data))
                self.send_header("Content-Disposition", 'attachment; filename="%s"' % fname)
                self.end_headers()
                self.wfile.write(data)
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    if not md:
                        self.send_json({"ok": True, "medicao": None})
                        return
                    self.send_json({"ok": True, "medicao": {
                        "parecer": md.parecer,
                        "ambientes_aprovados": md.ambientes_aprovados or "",
                        "tem_solicitacao": bool(md.solicitacao_arquivo),
                        "tem_planta": bool(md.planta_arquivo),
                        "tem_doc_cliente": bool(md.doc_cliente_arquivo),
                    }})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/conferencia/ajustes-preview$', path)
            if m:
                # Ajustes Excepcionais (spec 2026-07-21): preview do que a conferência aplicaria
                # sobre ?valor=<conferido> — só cálculo, nenhum lançamento.
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                from urllib.parse import parse_qs
                try:
                    valor = round(float((parse_qs(urlparse(self.path).query).get("valor")
                                         or ["0"])[0]), 2)
                except (TypeError, ValueError):
                    valor = 0.0
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    import mod_contabil as _mcp
                    ot, own_id = _mcp.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                    calc = _aplicar_ajustes_conferencia(db, ot, own_id, loja_id, nome_safe,
                                                        valor, aplicar=False)
                    self.send_json({"ok": True, "preview": calc})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/pe/complemento/comparativo$', path)
            if m:
                # Correção Fatia 3: comparativo do modal "Negociar Complemento" — à vista
                # contratado × à vista do XML de complemento (descontos do contrato + fator de
                # custos adicionais 1/(1−p)), por ambiente MARCADO, com totais e o p exibível.
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    linhas, resumo = _complemento_diferencas(db, nome_safe)
                    if linhas is None:
                        self.send_json({"ok": False, "erro": resumo}, code=400); return
                    self.send_json({"ok": True, "linhas": linhas, "resumo": resumo})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/aprovacao-pe$', path)
            if m:
                # Correção Fatia 3: estado da Aprovação do Projeto Executivo
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    a = (db.query(AprovacaoPE).filter_by(projeto_nome=nome_safe)
                           .order_by(AprovacaoPE.id.desc()).first())
                    self.send_json({"ok": True, "aprovacao": _aprovacao_pe_dict(a) if a else None})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/aprovacao-pe/pdf$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    a = (db.query(AprovacaoPE).filter_by(projeto_nome=nome_safe)
                           .order_by(AprovacaoPE.id.desc()).first())
                    if a is None or not a.pdf_path or not os.path.exists(a.pdf_path):
                        self.send_json({"ok": False, "erro": "PDF da aprovação não encontrado."},
                                       code=404); return
                    with open(a.pdf_path, "rb") as fh:
                        data = fh.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", len(data))
                    self.send_header("Content-Disposition",
                                     'inline; filename="aprovacao_pe_%d.pdf"' % a.id)
                    self.end_headers()
                    self.wfile.write(data)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/aditivo$', path)
            if m:
                # Fatia 3 PE: estado do Termo Aditivo (status, assinaturas, dados da diferença)
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    a = (db.query(Aditivo).filter_by(projeto_nome=nome_safe)
                           .order_by(Aditivo.id.desc()).first())
                    self.send_json({"ok": True, "aditivo": _aditivo_dict(a) if a else None})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/aditivo/defaults$', path)
            if m:
                # Wizard do Termo Aditivo (spec 2026-07-22): textos-padrão dos 5 modais +
                # blocos salvos da última geração (regerar reabre com o texto editado).
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    contrato = (db.query(Contrato).filter_by(projeto_nome=nome_safe)
                                  .order_by(Contrato.id.desc()).first())
                    if contrato is None or not _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False, "erro": "O termo aditivo exige contrato "
                                        "assinado."}, code=400); return
                    orc_aj = (db.query(Orcamento).filter_by(projeto_id=nome_safe, complemento_pe=1)
                                .order_by(Orcamento.id.desc()).first())
                    if orc_aj is None:
                        self.send_json({"ok": False, "erro": "Negocie o complemento antes de gerar "
                                        "o termo aditivo (11e → Negociar Complemento)."},
                                       code=400); return
                    import mod_contrato as _mc
                    defaults, calc = _aditivo_defaults_blocos(db, nome_safe, contrato, orc_aj)
                    a = (db.query(Aditivo).filter_by(projeto_nome=nome_safe)
                           .order_by(Aditivo.id.desc()).first())
                    blocos_salvos = None
                    if a is not None and a.status != "assinado" and a.dados_json:
                        try:
                            blocos_salvos = (json.loads(a.dados_json).get("blocos") or None)
                        except Exception:
                            blocos_salvos = None
                    n_ord = _aditivo_ordinal_atual(db, contrato, a)
                    self.send_json({"ok": True,
                                    "ordinal": _mc.ordinal_aditivo(n_ord),
                                    "ordinal_num": n_ord,
                                    "defaults": defaults,
                                    "blocos_salvos": blocos_salvos,
                                    "assinado": bool(a is not None and a.status == "assinado"),
                                    "valores": {"contrato_original": calc["contrato_original"],
                                                "contrato_novo": calc["contrato_novo"],
                                                "diferenca": calc["dif"]}})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/aditivo/pdf$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    a = (db.query(Aditivo).filter_by(projeto_nome=nome_safe)
                           .order_by(Aditivo.id.desc()).first())
                    if a is None or not a.pdf_path or not os.path.exists(a.pdf_path):
                        self.send_json({"ok": False, "erro": "PDF do aditivo não encontrado."},
                                       code=404); return
                    with open(a.pdf_path, "rb") as fh:
                        data = fh.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", len(data))
                    self.send_header("Content-Disposition",
                                     'inline; filename="aditivo_%d.pdf"' % a.id)
                    self.end_headers()
                    self.wfile.write(data)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/contrato/pdf$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato)\
                                 .filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc())\
                                 .first()
                    _pdf = _resolver_pdf_contrato(contrato.pdf_path) if contrato else None
                    if not _pdf:
                        self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404)
                        return
                    eh_pdf  = _pdf.endswith(".pdf")
                    ct      = "application/pdf" if eh_pdf else \
                              "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ext     = "pdf" if eh_pdf else "docx"
                    with open(_pdf, 'rb') as f:
                        arq_data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", len(arq_data))
                    disp = "inline" if eh_pdf else "attachment"
                    self.send_header("Content-Disposition",
                                     f'{disp}; filename="contrato_{nome_safe}.{ext}"')
                    self.end_headers()
                    self.wfile.write(arq_data)
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    _meta = _projeto_da_loja(db, nome_safe, loja_id)
                    if _meta is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato)\
                                 .filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc())\
                                 .first()
                    if not contrato:
                        self.send_json({"ok": True, "contrato": None})
                        return
                    assinaturas = [{
                        "parte":       a.parte,
                        "nome":        a.nome,
                        "assinado_em": a.assinado_em.isoformat(),
                    } for a in contrato.assinaturas]
                    _pdf_ok = _resolver_pdf_contrato(contrato.pdf_path)
                    tem_arquivo = bool(_pdf_ok)
                    arquivo_tipo = ""
                    if tem_arquivo:
                        arquivo_tipo = "pdf" if _pdf_ok.endswith(".pdf") else "docx"
                    import mod_contrato as _mod_contrato
                    _orc_src = db.get(Orcamento, contrato.orcamento_id)
                    _desatualizado = _mod_contrato.contrato_desatualizado(
                        contrato.pagamento_json,
                        _orc_src.forma_pagamento if _orc_src else None)
                    self.send_json({"ok": True, "contrato": {
                        "id":                   contrato.id,
                        "status":               contrato.status,
                        "endereco_instalacao":  contrato.endereco_instalacao or "",
                        "adendo":               contrato.adendo or "",
                        "gerado_em":            contrato.gerado_em.isoformat() if contrato.gerado_em else None,
                        "tem_pdf":              tem_arquivo,
                        "arquivo_tipo":         arquivo_tipo,
                        "assinaturas":          assinaturas,
                        "desatualizado":        _desatualizado,
                        "orcamento_id":         contrato.orcamento_id,
                        "data_entrega":         _meta.data_entrega.isoformat() if (_meta and _meta.data_entrega) else None,
                        "previsao_medicao":     _meta.previsao_medicao.isoformat() if (_meta and _meta.previsao_medicao) else None,
                        "venda_programada":     bool(_meta.venda_programada) if _meta else False,
                        "data_limite_contratual": _meta.data_limite_contratual.isoformat() if (_meta and _meta.data_limite_contratual) else None,
                    }})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/pe — documentos + revisões + status das subfases
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/pe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    docs = db.query(CicloDocumento).filter_by(projeto_nome=nome_safe)\
                             .order_by(CicloDocumento.enviado_em.desc()).all()
                    revs = db.query(CicloRevisao).filter_by(projeto_nome=nome_safe)\
                             .order_by(CicloRevisao.aberta_em.desc()).all()
                    etapas = db.query(CicloEtapa).filter(CicloEtapa.projeto_nome == nome_safe,
                                                         CicloEtapa.etapa_codigo.like("11%")).all()
                    subfases = {e.etapa_codigo: {"status": e.status,
                                                 "concluido_em": e.concluido_em.isoformat() if e.concluido_em else None}
                                for e in etapas}
                    self.send_json({"ok": True,
                        "subfases": subfases,
                        "documentos": [{"id": d.id, "etapa_codigo": d.etapa_codigo, "tipo": d.tipo,
                                        "nome_original": d.nome_original,
                                        "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None,
                                        "enviado_por_id": d.enviado_por_id} for d in docs],
                        "revisoes": [{"id": r.id, "etapa_codigo": r.etapa_codigo,
                                      "aberta_por_id": r.aberta_por_id,
                                      "aberta_em": r.aberta_em.isoformat() if r.aberta_em else None,
                                      "relatorio_doc_id": r.relatorio_doc_id, "motivo": r.motivo} for r in revs]})
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/documento/<id> — baixa um documento (read-only)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/documento/(\d+)$', path)
            if m:
                nome_safe = unquote(m.group(1)); doc_id = int(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    doc = db.query(CicloDocumento).filter_by(id=doc_id, projeto_nome=nome_safe).first()
                    if not doc:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    caminho = os.path.join(_projeto_path(nome_safe), doc.arquivo_path)
                    if not os.path.exists(caminho):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    conteudo = storage_ler_binario(caminho)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'inline; filename="{doc.nome_original}"')
                    self.send_header("Content-Length", str(len(conteudo)))
                    self.end_headers()
                    self.wfile.write(conteudo)
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/<codigo>/pedido-xml — lista os XMLs da etapa operacional (12)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/pedido-xml$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    tipo = mod_ciclo.tipo_doc_operacional(codigo)
                    docs = (db.query(CicloDocumento)
                              .filter_by(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo)
                              .order_by(CicloDocumento.enviado_em.desc()).all()) if tipo else []
                    out = [{"id": d.id, "nome_original": d.nome_original,
                            "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None} for d in docs]
                    self.send_json({"ok": True, "documentos": out})
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/15/nfe — estado da etapa 15 (XMLs da fábrica
            # + emissões associadas), gated por capacidade fiscal (editar_dados_loja).
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    _bloq, _msg = _bloqueio_modulo(path, db.get(Loja, loja_id) if loja_id else None)
                    if _bloq:
                        self.send_json({"ok": False, "erro": _msg}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    docs = (db.query(CicloDocumento)
                              .filter_by(projeto_nome=nome_safe, etapa_codigo="15", tipo="nfe_fabrica_xml")
                              .order_by(CicloDocumento.enviado_em.desc()).all())
                    emissoes = {e.fabrica_doc_id: e for e in
                                db.query(DocumentoFiscal).filter_by(projeto_nome=nome_safe).all()
                                if e.fabrica_doc_id is not None}
                    _emit_cache = {}
                    def _emitente(eid):
                        if eid is None:
                            return None
                        if eid not in _emit_cache:
                            _emit_cache[eid] = db.get(Emitente, eid)
                        return _emit_cache[eid]
                    out = []
                    for d in docs:
                        e = emissoes.get(d.id)
                        em = _emitente(e.emitente_id) if e else None
                        emissao = None if not e else {
                            "ref": e.ref, "status": e.status, "chave": e.chave_nfe, "numero": e.numero,
                            "serie": e.serie, "mensagem_sefaz": e.mensagem_sefaz,
                            "erros": json.loads(e.erros_json) if e.erros_json else [],
                            "xml_doc_id": e.xml_doc_id, "danfe_doc_id": e.danfe_doc_id,
                            "emitente_cnpj": em.cnpj if em else None,
                            "emitente_razao": em.razao_social if em else None}
                        out.append({"id": d.id, "nome_original": d.nome_original,
                                    "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None,
                                    "emissao": emissao})
                    # Estado da NFS-e (serviço, valor manual) — o DocumentoFiscal tipo="servico"
                    # deste projeto (ref NFSE-<projeto>), serializado como uma emissão de produto.
                    nfse_reg = (db.query(DocumentoFiscal)
                                  .filter_by(projeto_nome=nome_safe, tipo_documento="servico")
                                  .order_by(DocumentoFiscal.id.desc()).first())
                    emn = _emitente(nfse_reg.emitente_id) if nfse_reg else None
                    nfse = None if not nfse_reg else {
                        "ref": nfse_reg.ref, "status": nfse_reg.status, "chave": nfse_reg.chave_nfe,
                        "numero": nfse_reg.numero, "serie": nfse_reg.serie,
                        "mensagem_sefaz": nfse_reg.mensagem_sefaz,
                        "erros": json.loads(nfse_reg.erros_json) if nfse_reg.erros_json else [],
                        "xml_doc_id": nfse_reg.xml_doc_id, "danfe_doc_id": nfse_reg.danfe_doc_id,
                        "emitente_cnpj": emn.cnpj if emn else None,
                        "emitente_razao": emn.razao_social if emn else None}
                    self.send_json({"ok": True, "fabrica_xmls": out, "nfse": nfse})
                finally:
                    db.close()
                return

            # GET /api/admin/lojas/<id>/perfil-fiscal — config fiscal (segredos NUNCA retornados)
            m = _re.match(r'^/api/admin/lojas/(\d+)/perfil-fiscal$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if _sem_acesso_modulo(usuario, "fiscal", handler=self):   # Perfil-4: só Diretoria abre Fiscal
                    self.send_json({"ok": False, "erro": "Sem acesso ao módulo Fiscal.", "precisa_stepup": "fiscal"}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    em, _attr = _emitente_do_dono(db, "loja", loja)
                    out = _fiscal_get(em)
                    # PDV (loja com mãe): a emissão sai pelo CNPJ da mãe — o painel avisa
                    # em vez de parecer "não configurado" (spec PDV 2026-07-22, Desvio 1).
                    if getattr(loja, "loja_mae_id", None):
                        mae = db.get(Loja, loja.loja_mae_id)
                        out["pdv_de"] = mae.nome if mae else "loja-mãe"
                    self.send_json(out)
                finally:
                    db.close()
                return

            # GET /api/admin/lojas/<id>/modulos — domínios ativos (topologia)
            m = _re.match(r'^/api/admin/lojas/(\d+)/modulos$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    import modulos as _mod
                    ativos = mod_tenancy.modulos_ativos_da_loja(loja)
                    dominios = [{"id": x["id"], "rotulo": x["rotulo"], "depende_de": x["depende_de"],
                                 "ativo": x["id"] in ativos} for x in _mod.dominios_com_rotulo()]
                    self.send_json({"ok": True, "ativos": sorted(ativos), "dominios": dominios})
                finally:
                    db.close()
                return

            # GET /api/admin/redes/<id>/perfil-fiscal — config do Emitente central da rede
            m = _re.match(r'^/api/admin/redes/(\d+)/perfil-fiscal$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    rid = int(m.group(1))
                    rede = db.get(Rede, rid)
                    if not rede:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_ver_rede(ator, rid):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    em, _attr = _emitente_do_dono(db, "rede", rede)
                    self.send_json(_fiscal_get(em))
                finally:
                    db.close()
                return

            # GET /api/admin/redes/<id>/perfil-emissao — default de emissão da rede
            m = _re.match(r'^/api/admin/redes/(\d+)/perfil-emissao$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    rid = int(m.group(1))
                    rede = db.get(Rede, rid)
                    if not rede:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_ver_rede(ator, rid):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    self.send_json(_perfil_emissao_get(db, "rede", rid, rede))
                finally:
                    db.close()
                return

            # GET /api/admin/lojas/<id>/perfil-emissao — override de emissão da loja
            m = _re.match(r'^/api/admin/lojas/(\d+)/perfil-emissao$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    self.send_json(_perfil_emissao_get(db, "loja", loja.id, loja))
                finally:
                    db.close()
                return

            # ── Modelos de documento por loja (Task 8) ──────────────────────────
            # GET /api/documentos/marcadores — catálogo do que existe, p/ a tela do wizard
            if path == "/api/documentos/marcadores":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_marcadores as _mmarc
                self.send_json({"ok": True, "catalogo": _mmarc.CATALOGO})
                return

            # GET /api/documentos/tipos — tipos CUSTOMIZADOS da loja ("Novo Documento",
            # spec 2026-07-22). Os 4 nativos são fixos no frontend.
            if path == "/api/documentos/tipos":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_documentos as _mdoc
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    self.send_json({"ok": True, "tipos": [
                        {"slug": t.slug, "nome": t.nome, "etapa_ciclo": t.etapa_ciclo or "",
                         "criado_por_id": t.criado_por_id,
                         "criado_em": t.criado_em.isoformat() if t.criado_em else None}
                        for t in _mdoc.tipos_customizados(db, loja_id)]})
                finally:
                    db.close()
                return

            # GET /api/documentos/modelos — modelos da loja da sessão (tenancy)
            if path == "/api/documentos/modelos":
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_documentos as _mdoc
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    modelos = _mdoc.listar(db, loja_id)
                    self.send_json({
                        "ok": True,
                        "pode_gerir": perfis.pode(ator.get("nivel"), "gerir_documentos"),
                        "modelos": [_serializar_modelo_documento(m) for m in modelos],
                    })
                finally:
                    db.close()
                return

            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
        path   = urlparse(self.path).path
        body   = self._ler_body()
        if body is None: return   # 413 já respondido pelo _ler_body

        # Webhook WhatsApp de ENTRADA (Fatia 7) — NÃO autenticado (a Meta chama). DORMIENTE
        # sem ORIZON_WA_TOKEN (só dá ack). Configurado: exige assinatura HMAC (X-Hub-Signature-256)
        # com ORIZON_WA_APP_SECRET, parseia o payload da Cloud API e roteia por processar_entrada.
        if path == "/webhooks/whatsapp":
            if not (os.environ.get("ORIZON_WA_TOKEN") or "").strip():
                self.send_json({"ok": True}, code=200); return   # dormiente: ack, no-op
            secret = (os.environ.get("ORIZON_WA_APP_SECRET") or "").strip()
            if secret:
                # Alias OBRIGATÓRIO: `import hashlib` sem alias tornaria 'hashlib' LOCAL a todo o
                # do_POST e quebraria o upload do pool (que usa hashlib por outro caminho) —
                # mesma armadilha de escopo já documentada no _carregar_projeto/construir_contexto.
                import hmac as _hmac, hashlib as _hashlib
                sig = self.headers.get("X-Hub-Signature-256", "")
                calc = "sha256=" + _hmac.new(secret.encode(), body or b"", _hashlib.sha256).hexdigest()
                if not _hmac.compare_digest(sig, calc):
                    self.send_json({"ok": False}, code=403); return
            import mod_chat_externo as _ext
            db = get_session()
            try:
                payload = json.loads(body or b'{}')
                for msg in _ext.iter_mensagens_whatsapp(payload):
                    if not msg.get("from"):
                        continue
                    # Fatia 6: primeiro tenta casar com um FUNCIONÁRIO (celular cadastrado) e
                    # rotear como ELE; se não for um usuário conhecido, cai no fluxo externo (cliente).
                    res_u = _ext.processar_entrada_usuario(db, msg["from"], msg["texto"])
                    if res_u is None:
                        res = _ext.processar_entrada(db, "whatsapp", remetente=msg["from"],
                                                     texto=msg["texto"],
                                                     id_externo_ref=msg.get("ref"),
                                                     id_externo=msg.get("id"),
                                                     nome=msg.get("nome"))
                        # Rastro do destino (spec triagem 2026-07-31): nem sucesso nem fila
                        # passam mais em silêncio pelo webhook.
                        logging.getLogger(__name__).info(
                            "webhook whatsapp: %s → %s (conversa=%s triagem=%s)",
                            msg.get("id"), res.get("status"),
                            res.get("conversa_id"), res.get("triagem_id"))
                db.commit()
            except Exception as _e:
                db.rollback()
                logging.getLogger(__name__).warning("webhook whatsapp: %s", _e)
            finally:
                db.close()
            self.send_json({"ok": True}, code=200); return

        if handle_auth_post(self, path, body): return

        # POST /api/documentos/tipos — cria tipo de documento CUSTOMIZADO ("Novo Documento",
        # spec 2026-07-22): nome + etapa do ciclo associada. Exige gerir_documentos.
        if path == "/api/documentos/tipos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_documentos as _mdoc
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if not perfis.pode(ator.get("nivel"), "gerir_documentos"):
                    self.send_json({"ok": False, "erro": "Sem permissão para gerir documentos"},
                                   code=403); return
                req = json.loads(body) if body else {}
                try:
                    t = _mdoc.criar_tipo(db, loja_id, req.get("nome"),
                                         req.get("etapa_ciclo"), usuario.get("id"))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "tipo": {"slug": t.slug, "nome": t.nome,
                                                     "etapa_ciclo": t.etapa_ciclo or ""}})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Modelos de documento por loja (Task 8) ──────────────────────────────
        # Os 3 POST exigem sessão + capacidade 'gerir_documentos' (só master por padrão).
        if path == "/api/documentos/modelos/importar":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_documentos as _mdoc
            import mod_documentos_import as _mdocimp
            import mod_marcadores as _mmarc
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if not perfis.pode(ator.get("nivel"), "gerir_documentos"):
                    self.send_json({"ok": False, "erro": "Sem permissão para gerir documentos"}, code=403); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                tipo = (campos.get("tipo") or "").strip()
                if not _mdoc.tipo_existe(db, loja_id, tipo):
                    self.send_json({"ok": False, "erro": "tipo inválido: %r (aceitos: %s ou um "
                                    "documento customizado da loja)" %
                                    (tipo, ", ".join(_mdoc.TIPOS))}, code=400); return
                if "arquivo" not in arquivos:
                    self.send_json({"ok": False, "erro": "Anexe o arquivo do modelo."}, code=400); return
                fname, dados = arquivos["arquivo"]
                staging_path, sha = _mdoc.guardar_staging(loja_id, tipo, fname, dados)
                # importa e analisa SEM salvar versão — o lojista pode desistir na revisão.
                try:
                    texto = _mdocimp.normalizar(staging_path)
                    corpo_md = _mdocimp.extrair_corpo(texto)
                except _mdocimp.FormatoNaoSuportado as e:
                    _remover_staging_seguro(staging_path)
                    self.send_json({"ok": False, "erro": str(e)}, code=400); return
                except Exception as e:
                    _remover_staging_seguro(staging_path)
                    self.send_json({"ok": False, "erro": "Falha ao converter o arquivo: %s" % e}, code=400); return
                if not (corpo_md or "").strip():
                    _remover_staging_seguro(staging_path)
                    self.send_json({"ok": False, "erro": "Não foi possível extrair conteúdo do documento."}, code=400); return
                loja_dict = _loja_dict_para_contrato(db, loja_id)
                analise = _mmarc.analisar_corpo(corpo_md, loja_dict)
                self.send_json({
                    "ok": True, "corpo_md": corpo_md, "origem_nome": fname, "tipo": tipo,
                    "staging": os.path.basename(staging_path),   # só o basename — nunca o caminho
                    "origem_sha256": sha, "analise": analise,
                })
            finally:
                db.close()
            return

        if path == "/api/documentos/modelos/preview":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if not perfis.pode(ator.get("nivel"), "gerir_documentos"):
                    self.send_json({"ok": False, "erro": "Sem permissão para gerir documentos"}, code=403); return
                req = json.loads(body) if body else {}
                corpo_md = req.get("corpo_md") or ""
                tipo_prev = (req.get("tipo") or "contrato").strip()
                import mod_documentos as _mdoc
                import mod_contrato as _mc
                if not _mdoc.tipo_existe(db, loja_id, tipo_prev):
                    self.send_json({"ok": False, "erro": "tipo inválido: %r" % (tipo_prev,)},
                                   code=400); return
                # Sem corpo_md no request = "Ver exemplo" do card: usa o modelo ATIVO da loja
                # (fallback: padrão do sistema p/ contrato e termo_aditivo). Com corpo_md, é o
                # texto recém-importado no wizard (comportamento original).
                if not corpo_md and tipo_prev != "contrato":
                    mv = _mdoc.ativo_de(db, loja_id, tipo_prev)
                    if mv is not None:
                        corpo_md = _mdoc.corpo_da_versao(db, mv.id) or ""
                    elif tipo_prev == "termo_aditivo":
                        corpo_md = _mc.corpo_modelo_aditivo_padrao()
                    if not corpo_md and tipo_prev != "proposta":
                        self.send_json({"ok": False, "erro": "Nenhum modelo ativo deste documento "
                                        "— importe um antes de visualizar."}, code=400); return
                loja_dict = _loja_dict_para_contrato(db, loja_id)
                # Cliente de EXEMPLO (o preview não pertence a nenhum projeto real); a loja é a
                # de verdade — é o que deixa o lojista conferir os cravados (CNPJ, endereço...).
                cliente_exemplo = {
                    "nome": "Cliente de Exemplo", "cpf": "000.000.000-00",
                    "email": "cliente@exemplo.com", "telefone": "(12) 90000-0000",
                    "logradouro": "Rua Exemplo", "numero": "123", "complemento": "",
                    "bairro": "Centro", "cidade": loja_dict.get("cidade", "") or "Cidade Exemplo",
                    "estado": loja_dict.get("estado", "") or "SP", "cep": "00000-000",
                    "inst_mesmo_residencial": True,
                }
                usuario_ctx = {"nome": usuario.get("nome", ""),
                               "telefone": _get_usuario_telefone(usuario["id"], db),
                               "email": usuario.get("email", "") or ""}
                # Import LOCAL (não o construir_contexto do topo do arquivo): outro bloco
                # deste mesmo do_POST (main.py ~6188) reimporta 'construir_contexto' localmente,
                # o que — pela regra de escopo do Python — torna o nome LOCAL a do_POST inteiro
                # e quebra a referência ao global aqui em cima com UnboundLocalError. Confirmado
                # por execução (pytest), não por leitura.
                from mod_contrato import construir_contexto
                ctx = construir_contexto(cliente_exemplo, usuario_ctx, "", loja_dict)
                ctx["num_contrato"] = "EXEMPLO"
                ctx["_ambientes"] = [("Ambiente de exemplo", 15000.0)]
                import tempfile, shutil
                outdir = tempfile.mkdtemp(prefix="doc_preview_")
                try:
                    hoje_br = datetime.now().strftime("%d/%m/%Y")
                    if tipo_prev == "termo_aditivo":
                        # corpo-só + cabeçalho, com contexto de EXEMPLO dos blocos do wizard
                        exemplo = _mc.montar_defaults_aditivo(
                            lista_integral=[("Cozinha", 93333.33), ("Suíte Master", 10000.0)],
                            inclusoes=[("Adega", 10000.0)], exclusoes=[],
                            valor_original=88888.89, valor_novo=103333.33, diferenca=14444.44,
                            condicoes="à vista, na data de assinatura deste TERMO ADITIVO")
                        ctx["num_contrato"] = "TA-EXEMPLO"
                        ctx["_corpo_md_aditivo"] = corpo_md
                        ctx["_aditivo"] = {"num_aditivo": "TA-EXEMPLO",
                                           "num_contrato_original": "CT-EXEMPLO",
                                           "ambientes_txt": "Cozinha: R$ 88.888,89 → R$ 93.333,33",
                                           "valor_original": "R$ 88.888,89",
                                           "valor_novo": "R$ 103.333,33",
                                           "diferenca": "R$ 14.444,44",
                                           "ordinal": "PRIMEIRO", "data_aditivo": hoje_br,
                                           "data_contrato_original": hoje_br, **exemplo}
                        pdf_path = _mc.gerar_pdf_aditivo(ctx, os.path.join(outdir, "preview.pdf"))
                    elif tipo_prev == "aprovacao_pe":
                        ctx["num_contrato"] = "AP-EXEMPLO"
                        ctx["_aprovacao_pe"] = {"num_aprovacao": "AP-EXEMPLO",
                                                "ambientes_txt": "- Cozinha\n- Suíte Master"}
                        ctx["_corpo_md_aprovacao"] = corpo_md
                        pdf_path = _mc.gerar_pdf_aprovacao_pe(ctx, os.path.join(outdir, "preview.pdf"))
                    elif tipo_prev.startswith("doc_"):
                        pdf_path = _mc.gerar_pdf_documento_generico(
                            ctx, corpo_md, os.path.join(outdir, "preview.pdf"))
                    else:
                        # contrato/proposta: capa + corpo, como sempre. NÃO passa ctx['_db'] nem
                        # ctx['_modelo_versao_id']: _corpo_md_preview é checado primeiro em
                        # _resolver_corpo_contrato e nunca toca o banco/versão real; sem corpo,
                        # o resolvedor cai sozinho no modelo ativo → global do sistema.
                        if corpo_md:
                            ctx["_corpo_md_preview"] = corpo_md
                        elif tipo_prev == "contrato":
                            ctx["_db"] = db          # "Ver exemplo": resolve ativo → global
                        pdf_path = gerar_pdf_contrato("preview", ctx, destino=outdir)
                    with open(pdf_path, "rb") as fh:
                        dados_pdf = fh.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", len(dados_pdf))
                    self.send_header("Content-Disposition", 'inline; filename="preview.pdf"')
                    self.end_headers()
                    self.wfile.write(dados_pdf)
                finally:
                    shutil.rmtree(outdir, ignore_errors=True)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        if path == "/api/documentos/modelos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_documentos as _mdoc
            import mod_marcadores as _mmarc
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if not perfis.pode(ator.get("nivel"), "gerir_documentos"):
                    self.send_json({"ok": False, "erro": "Sem permissão para gerir documentos"}, code=403); return
                req = json.loads(body) if body else {}
                tipo = (req.get("tipo") or "").strip()
                if not _mdoc.tipo_existe(db, loja_id, tipo):
                    self.send_json({"ok": False, "erro": "tipo inválido: %r (aceitos: %s ou um "
                                    "documento customizado da loja)" %
                                    (tipo, ", ".join(_mdoc.TIPOS))}, code=400); return
                corpo_md = req.get("corpo_md") or ""
                origem_nome = req.get("origem_nome") or None
                origem_sha256 = req.get("origem_sha256") or None
                cravados_aprovados = req.get("cravados_aprovados") or []
                loja_dict = _loja_dict_para_contrato(db, loja_id)
                corpo_final = _mmarc.aplicar_cravados(corpo_md, loja_dict, cravados_aprovados)
                analise = _mmarc.analisar_corpo(corpo_final, loja_dict)
                if analise["bloqueia_ativacao"]:
                    self.send_json({
                        "ok": False,
                        "erro": "O documento tem marcador desconhecido (%s), que sairia impresso "
                                "literal no PDF. Corrija o texto ou aprove o cravamento antes de ativar." %
                                ", ".join(analise["desconhecidos"]),
                        "analise": analise,
                    }, code=400)
                    return
                # SEGURANÇA — path traversal: quem valida/confina o 'staging' do cliente é
                # mod_documentos.resolver_staging (regex do nome + realpath/commonpath + isfile),
                # que é o módulo dono da convenção de nome. Nunca se aceita caminho pronto do
                # cliente, e basename() NÃO basta ('.' e '..' passam inteiros por ele — ver o
                # docstring de resolver_staging). Não resolveu -> segue sem trilha de origem.
                staging_path = _mdoc.resolver_staging(loja_id, tipo, req.get("staging"))
                try:
                    modelo = _mdoc.criar_versao(db, loja_id, tipo, corpo_final, origem_nome,
                                                usuario["id"], staging_path=staging_path,
                                                origem_sha256=origem_sha256)
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400); return
                except OSError as e:
                    # criar_versao commita a LINHA antes de mover o original (ordem deliberada,
                    # ver o docstring dele) e deixa a exceção do move subir. Então aqui a versão
                    # EXISTE e é válida — só ficou sem trilha de origem. Responder erro faria o
                    # lojista tentar de novo e criar uma versão DUPLICADA: exatamente a armadilha
                    # que criar_versao descreve. Recupera-se a linha (listar ordena versao desc,
                    # a 1ª do tipo é a recém-criada), ativa e reporta ok com aviso.
                    db.rollback()
                    modelo = next((m for m in _mdoc.listar(db, loja_id) if m.tipo == tipo), None)
                    if modelo is None:
                        self.send_json({"ok": False, "erro": "Falha ao gravar o modelo: %s" % e}, code=500); return
                    _mdoc.ativar(db, modelo.id)
                    self.send_json({"ok": True, "modelo": _serializar_modelo_documento(modelo),
                                    "aviso": "Modelo ativado, mas o arquivo original não pôde ser "
                                             "arquivado (%s). O modelo vale; só a trilha de origem "
                                             "desta versão se perdeu." % e})
                    return
                _mdoc.ativar(db, modelo.id)
                self.send_json({"ok": True, "modelo": _serializar_modelo_documento(modelo)})
            finally:
                db.close()
            return

        # ── Desmembramento OPERACIONAL (Fatia 1): ambientes retidos pela obra ──────────────────
        m_rnew = re.match(r'^/api/projetos/([^/]+)/retencoes$', path)
        if m_rnew:
            # Retenção RECORRENTE (2026-08-02): a GERÊNCIA retém ambientes em qualquer momento
            # entre a Solicitação de Medição e a Montagem. Body: {ambientes: [ids], motivo,
            # liberacao_prevista: 'AAAA-MM-DD', etapa_codigo}. Cria/derrama fases (split se
            # preciso) e registra o evento em RetencaoObra.
            import mod_retido as _mret
            nome = unquote(m_rnew.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not perfis.pode(usuario.get("nivel"), "autorizar"):
                    self.send_json({"ok": False, "erro": "Reter exige gerência (autorizar)."}, code=403); return
                contrato = (db.query(Contrato).filter_by(projeto_nome=nome)
                              .order_by(Contrato.id.desc()).first())
                if contrato is None:
                    self.send_json({"ok": False, "erro": "Retenção só após o contrato."}, code=409); return
                lib_prev = None
                if req.get("liberacao_prevista"):
                    try:
                        lib_prev = datetime.strptime(str(req["liberacao_prevista"])[:10],
                                                     "%Y-%m-%d").date()
                    except ValueError:
                        self.send_json({"ok": False, "erro": "liberacao_prevista inválida (AAAA-MM-DD)."},
                                       code=400); return
                # rev 2026-08-03 (auditoria): motivo vem do CATÁLOGO; descrição livre à parte
                motivo_tipo = (req.get("motivo_tipo") or "").strip()
                if motivo_tipo not in _mret.MOTIVOS_RETENCAO:
                    self.send_json({"ok": False, "erro": "Escolha o motivo da retenção (%s)."
                                    % ", ".join(_mret.MOTIVOS_RETENCAO)}, code=400); return
                valores, val_cont = _valores_contrato_por_ambiente(contrato.orcamento_id, db)
                liquidos, val_liq = _liquidos_contrato_por_ambiente(contrato.orcamento_id, db)
                ok, erro, resumo = _mret.reter(
                    db, nome, req.get("ambientes") or [], contrato.orcamento_id, valores,
                    val_cont, usuario.get("id"), motivo_tipo=motivo_tipo,
                    motivo=(req.get("descricao") or req.get("motivo") or "").strip() or None,
                    liberacao_prevista=lib_prev,
                    etapa_codigo=(req.get("etapa_codigo") or "").strip() or None,
                    liquidos_por_ambiente=liquidos, val_liq=val_liq)
                if not ok:
                    db.rollback()
                    self.send_json({"ok": False, "erro": erro}, code=409); return
                db.commit()
                self.send_json({"ok": True, **resumo})
            finally:
                db.close()
            return

        # POST .../retido/sinalizar — MEDIDOR marca ambientes retidos. Body: {pool_ambiente_ids, motivo}.
        m_rsig = re.match(r'^/api/projetos/([^/]+)/retido/(sinalizar|limpar|confirmar|liberar)$', path)
        if m_rsig:
            nome = unquote(m_rsig.group(1)); acao = m_rsig.group(2)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                import mod_retido as _mret
                req = json.loads(body) if body else {}
                if acao in ("sinalizar", "limpar"):
                    if not perfis.pode(usuario.get("nivel"), "registrar_medicao"):
                        self.send_json({"ok": False, "erro": "Ação do medidor (registrar_medicao)."}, code=403); return
                    if acao == "sinalizar":
                        marcados = _mret.sinalizar(db, nome, req.get("pool_ambiente_ids") or [],
                                                   usuario.get("id"), req.get("motivo"))
                        db.commit()
                        self.send_json({"ok": True, "marcados": marcados})
                    else:
                        _mret.limpar_sinal(db, nome, req.get("pool_ambiente_id"))
                        db.commit()
                        self.send_json({"ok": True})
                    return
                # confirmar / liberar — GERÊNCIA
                if not perfis.pode(usuario.get("nivel"), "autorizar"):
                    self.send_json({"ok": False, "erro": "Ação exige gerência (autorizar)."}, code=403); return
                if acao == "liberar":
                    ok, erro, afetadas = _mret.liberar(db, nome, req.get("pool_ambiente_ids") or [],
                                                       usuario.get("id"))
                    if not ok:
                        db.rollback()
                        self.send_json({"ok": False, "erro": erro}, code=409); return
                    # fecha os registros de retenção cujos ambientes já saíram todos de fase retida
                    _mret.estampar_liberacoes(db, nome, usuario.get("id"))
                    db.commit()
                    self.send_json({"ok": True, "parcelas": afetadas}); return
                contrato = (db.query(Contrato).filter_by(projeto_nome=nome)
                              .order_by(Contrato.id.desc()).first())
                if contrato is None:
                    self.send_json({"ok": False, "erro": "Desmembre após o contrato assinado."}, code=409); return
                valores, val_cont = _valores_contrato_por_ambiente(contrato.orcamento_id, db)
                liquidos, val_liq = _liquidos_contrato_por_ambiente(contrato.orcamento_id, db)
                ok, erro, parcelas = _mret.confirmar(db, nome, contrato.orcamento_id, valores,
                                                     val_cont, usuario.get("id"),
                                                     liquidos_por_ambiente=liquidos, val_liq=val_liq)
                if not ok:
                    db.rollback()
                    self.send_json({"ok": False, "erro": erro}, code=409); return
                db.commit()
                self.send_json({"ok": True, "parcelas": parcelas})
            finally:
                db.close()
            return

        m_pcreate = re.match(r'^/api/projetos/([^/]+)/parcelas$', path)
        if m_pcreate:
            # Fatia 2 (desmembramento): desmembra o projeto em parcelas (grupos de ambientes). Valida a
            # partição (#1), congela a fração do Val_Cont (#5) e grava parcela_projeto + parcela_ambiente.
            # Operacional (não lança contábil) — o efeito no ciclo/contábil vem nas etapas seguintes.
            import mod_parcelas as _mpar
            nome = unquote(m_pcreate.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            parcelas_ids = req.get("parcelas") or []
            if not isinstance(parcelas_ids, list) or len(parcelas_ids) < 2:
                self.send_json({"ok": False, "erro": "Desmembrar exige ao menos 2 parcelas"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if db.query(ParcelaProjeto).filter_by(projeto_nome=nome).first() is not None:
                    self.send_json({"ok": False, "erro": "Projeto já desmembrado"}, code=409); return
                contrato = (db.query(Contrato).filter_by(projeto_nome=nome).order_by(Contrato.id.desc()).first())
                if contrato is None:
                    self.send_json({"ok": False, "erro": "Desmembre após o contrato assinado"}, code=409); return
                try:
                    parcelas_ids = [[int(x) for x in grupo] for grupo in parcelas_ids]
                except (TypeError, ValueError):
                    self.send_json({"ok": False, "erro": "Ambientes inválidos"}, code=400); return
                # 🟠 Vera E2E 2026-08-03: a partição vale sobre os ambientes do orçamento
                # CONTRATADO — não o pool inteiro do projeto (que ainda contém os ambientes de
                # orçamentos PERDEDORES; exigi-los na fase contaminava a entrega com ambiente
                # nunca vendido).
                pool_ids = [lk.pool_ambiente_id for lk in
                            db.query(OrcamentoAmbiente).filter_by(
                                orcamento_id=contrato.orcamento_id).all()]
                ok, erro = _mpar.validar_particao_parcelas(pool_ids, parcelas_ids)
                if not ok:
                    self.send_json({"ok": False, "erro": erro}, code=400); return
                valores, val_cont = _valores_contrato_por_ambiente(contrato.orcamento_id, db)
                grupos_valores = [[valores.get(aid, 0.0) for aid in grupo] for grupo in parcelas_ids]
                congeladas = _mpar.congelar_parcelas(grupos_valores, val_cont)
                # Agenda Fatia 1: congela também o Val_Liq da fase (mesma partição, Σ exata)
                liquidos, val_liq = _liquidos_contrato_por_ambiente(contrato.orcamento_id, db)
                cong_liq = _mpar.congelar_parcelas(
                    [[liquidos.get(aid, 0.0) for aid in grupo] for grupo in parcelas_ids], val_liq)
                previsoes = _previsoes_fases(req, len(parcelas_ids))
                criadas = []
                for i, (grupo, cong) in enumerate(zip(parcelas_ids, congeladas)):
                    p = ParcelaProjeto(projeto_nome=nome, ordem=cong["ordem"], status="aguardando",
                                       fracao_val_cont=cong["fracao_val_cont"],
                                       val_cont_congelado=cong["val_cont_congelado"],
                                       val_liq_congelado=cong_liq[i]["val_cont_congelado"],
                                       orcamento_id=contrato.orcamento_id,
                                       criado_por_id=getattr(usuario, "id", None),
                                       liberacao_prevista=previsoes[i][0],
                                       entrega_prevista=previsoes[i][1])
                    db.add(p); db.flush()
                    for aid in grupo:
                        db.add(ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=aid))
                    criadas.append({"id": p.id, "ordem": p.ordem, "val_cont_congelado": p.val_cont_congelado})
                db.commit()
                self.send_json({"ok": True, "parcelas": criadas})
            finally:
                db.close()
            return

        m_psub = re.match(r'^/api/projetos/([^/]+)/parcelas/(\d+)/desmembrar$', path)
        if m_psub:
            # Desmembramento SUCESSIVO: divide UMA fase existente em ≥2 novas (decisão pode vir
            # depois, ex. no PE). Preserva exatamente o congelado da mãe (mod_parcelas.desmembrar_fase);
            # a mãe é removida e as fases são renumeradas 1..N. Bloqueado se a fase já está em
            # expedição (CicloLogistico) ou liquidada.
            import mod_parcelas as _mpar
            nome = unquote(m_psub.group(1)); pid = int(m_psub.group(2))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            grupos = req.get("parcelas") or []
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                mae = db.get(ParcelaProjeto, pid)
                if mae is None or mae.projeto_nome != nome:
                    self.send_json({"ok": False, "erro": "Fase não encontrada"}, code=404); return
                if mae.status == "liquidada":
                    self.send_json({"ok": False, "erro": "Fase já liquidada — não pode ser desmembrada"}, code=409); return
                if db.query(CicloLogistico).filter_by(projeto_nome=nome, parcela_id=pid).first():
                    self.send_json({"ok": False, "erro": "Fase já em expedição — não pode ser desmembrada"}, code=409); return
                try:
                    grupos = [[int(x) for x in g] for g in grupos]
                except (TypeError, ValueError):
                    self.send_json({"ok": False, "erro": "Ambientes inválidos"}, code=400); return
                amb_ids = [a.pool_ambiente_id for a in
                           db.query(ParcelaAmbiente).filter_by(parcela_id=pid).all()]
                valores, _vc = _valores_contrato_por_ambiente(mae.orcamento_id, db)
                ok, erro, novas = _mpar.desmembrar_fase(
                    amb_ids, grupos, mae.val_cont_congelado, mae.fracao_val_cont, valores)
                if not ok:
                    self.send_json({"ok": False, "erro": erro}, code=400); return
                # Agenda Fatia 1: reparte também o Val_Liq congelado da mãe (mesma partição).
                # Mãe legada sem o campo (pré-backfill): aproxima pelo rateio líquido atual.
                liquidos, _vl = _liquidos_contrato_por_ambiente(mae.orcamento_id, db)
                mae_liq = (mae.val_liq_congelado if mae.val_liq_congelado is not None
                           else round(sum(liquidos.get(a, 0.0) for a in amb_ids), 2))
                _okl, _errl, novas_liq = _mpar.desmembrar_fase(
                    amb_ids, grupos, mae_liq, 0.0, liquidos)
                criadas = []
                previsoes = _previsoes_fases(req, len(grupos))
                # novas herdam a POSIÇÃO da mãe (ordem; desempate por id = ordem dos grupos)
                for i, (grupo, ng) in enumerate(zip(grupos, novas)):
                    p = ParcelaProjeto(projeto_nome=nome, ordem=mae.ordem, status=mae.status,
                                       fracao_val_cont=ng["fracao_val_cont"],
                                       val_cont_congelado=ng["val_cont_congelado"],
                                       val_liq_congelado=novas_liq[i]["val_cont_congelado"],
                                       orcamento_id=mae.orcamento_id,
                                       criado_por_id=(usuario.get("id") if isinstance(usuario, dict)
                                                      else getattr(usuario, "id", None)),
                                       liberacao_prevista=(previsoes[i][0] or mae.liberacao_prevista),
                                       entrega_prevista=(previsoes[i][1] or mae.entrega_prevista))
                    db.add(p); db.flush()
                    for aid in grupo:
                        db.add(ParcelaAmbiente(parcela_id=p.id, pool_ambiente_id=aid))
                    criadas.append(p)
                db.query(ParcelaAmbiente).filter_by(parcela_id=pid).delete()
                db.delete(mae); db.flush()
                # renumera 1..N (ordem estável: ordem antiga, depois id) — rótulo "Fase N" denso
                todas = (db.query(ParcelaProjeto).filter_by(projeto_nome=nome)
                           .order_by(ParcelaProjeto.ordem.asc(), ParcelaProjeto.id.asc()).all())
                for i, p in enumerate(todas, start=1):
                    p.ordem = i
                db.commit()
                self.send_json({"ok": True, "parcelas": [
                    {"id": p.id, "ordem": p.ordem, "val_cont_congelado": p.val_cont_congelado}
                    for p in criadas]})
            finally:
                db.close()
            return

        m_conf = re.match(r'^/api/projetos/([^/]+)/conferencia$', path)
        if m_conf:
            # Fatia 2 #13 — Conferência e Implantação do Pedido: ajuste do Custo de Fábrica (PE) +
            # reclassificação p/ Outros Fornecedores. Dois lançamentos (ativo × provisão, nunca DRE).
            import mod_contabil as _mc
            nome = unquote(m_conf.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            try:
                custo_novo = round(float(req.get("custo_fabrica_novo") or 0), 2)
                outros = round(float(req.get("valor_outros_forn") or 0), 2)
            except (TypeError, ValueError):
                self.send_json({"ok": False, "erro": "Valores inválidos"}, code=400); return
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"), sessao=usuario)
                if not aprovador:
                    self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ot, own_id = _mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                # efeito líquido dos ajustes excepcionais JÁ aplicados neste projeto (acréscimo
                # soma, desconto subtrai; reversões negativas se anulam) — a conferência mira o
                # custo_novo SEM esse efeito, senão re-rodá-la reverteria os ajustes
                net_ajx = 0.0
                for _r in db.query(AjusteFabricaAplicacao).filter_by(projeto_nome=nome).all():
                    _aj = db.get(AjusteFabrica, _r.ajuste_id)
                    if _aj is not None:
                        net_ajx += _r.valor if _aj.tipo == "acrescimo" else -_r.valor
                out = _mc.conferencia_pedido(db, ot, own_id, nome, custo_novo, outros,
                                             ref_base="conf:" + nome,
                                             excluir_ajustes=round(net_ajx, 2))
                # Ajustes Excepcionais de Fábrica (spec 2026-07-21): descontos sobre o conferido,
                # acréscimos sobre o pós-descontos; caps/idempotência no helper. Opt-out explícito.
                ajustes_out = None
                if req.get("aplicar_ajustes", True):
                    ajustes_out = _aplicar_ajustes_conferencia(db, ot, own_id, loja_id, nome, custo_novo)
                db.commit()
                self.send_json({"ok": True, "lancamentos": out, "ajustes": ajustes_out})
            finally:
                db.close()
            return

        # ── Ajustes Excepcionais de Fábrica — painel Admin (spec 2026-07-21) ──────────────────
        # Gate: mesma capacidade do config-financeira (editar_dados_loja) + escopo de loja(s).
        if path in ("/api/admin/acordos-fabrica", "/api/admin/contrapartes-financeiras") \
                or re.match(r'^/api/admin/contrapartes-financeiras/\d+$', path) \
                or re.match(r'^/api/admin/(acordos|ajustes)-fabrica/', path):
            import mod_contabil as _mcaf
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                req = json.loads(body or b'{}')

                def _ve_loja(lid):
                    lj = db.get(Loja, int(lid)) if lid else None
                    return lj if (lj and mod_tenancy.pode_ver_loja(
                        ator, {"id": lj.id, "rede_id": lj.rede_id})) else None

                _CP_CAMPOS = ("cnpj", "telefone", "email", "cep", "logradouro", "numero",
                              "complemento", "bairro", "cidade", "uf")

                def _cp_aplicar_campos(cp_obj):
                    for _c in _CP_CAMPOS:
                        if _c in req:
                            setattr(cp_obj, _c, (str(req.get(_c) or "").strip() or None))

                if path == "/api/admin/contrapartes-financeiras":
                    # Revisão 2026-07-22: cadastro de Credor/Devedor — o papel vem do TIPO de
                    # cada acordo lançado contra a contraparte. Cadastro completo: CNPJ,
                    # contato financeiro (telefone/e-mail) e endereço.
                    nome_cp = (req.get("nome") or "").strip()
                    tipo_cp = (req.get("tipo") or "").strip()
                    if not nome_cp or tipo_cp not in ("fabrica", "empresa", "banco"):
                        self.send_json({"ok": False, "erro": "Informe nome e tipo "
                                        "(fabrica|empresa|banco)."}, code=400); return
                    ja_cp = (db.query(ContraparteFinanceira)
                               .filter(ContraparteFinanceira.tipo == tipo_cp).all())
                    if any((c.nome or "").strip().lower() == nome_cp.lower() for c in ja_cp):
                        self.send_json({"ok": False, "erro": "Contraparte já cadastrada com "
                                        "este nome."}, code=400); return
                    cp = ContraparteFinanceira(nome=nome_cp, tipo=tipo_cp,
                                               criado_por_id=usuario.get("id"))
                    _cp_aplicar_campos(cp)
                    db.add(cp); db.commit()
                    self.send_json({"ok": True, "contraparte": _contraparte_dict(cp)})
                    return

                m_cp = re.match(r'^/api/admin/contrapartes-financeiras/(\d+)$', path)
                if m_cp:
                    # editar (nome/tipo) ou apagar contraparte (pedido do usuário, 2026-07-22).
                    # Apagar só sem acordos vinculados — o histórico contábil não pode órfãr.
                    cp = db.get(ContraparteFinanceira, int(m_cp.group(1)))
                    if cp is None:
                        self.send_json({"ok": False, "erro": "Não encontrada"}, code=404); return
                    if req.get("apagar"):
                        n_ac = db.query(AcordoFabrica).filter_by(contraparte_id=cp.id).count()
                        if n_ac:
                            self.send_json({"ok": False, "erro": "Contraparte tem %d acordo(s) "
                                            "vinculado(s) — encerre/reatribua antes de apagar."
                                            % n_ac}, code=400); return
                        db.delete(cp); db.commit()
                        self.send_json({"ok": True, "apagada": True})
                        return
                    nome_cp = (req.get("nome") or "").strip()
                    tipo_cp = (req.get("tipo") or cp.tipo).strip()
                    if not nome_cp or tipo_cp not in ("fabrica", "empresa", "banco"):
                        self.send_json({"ok": False, "erro": "Informe nome e tipo válidos."},
                                       code=400); return
                    dup = (db.query(ContraparteFinanceira)
                             .filter(ContraparteFinanceira.tipo == tipo_cp,
                                     ContraparteFinanceira.id != cp.id).all())
                    if any((c.nome or "").strip().lower() == nome_cp.lower() for c in dup):
                        self.send_json({"ok": False, "erro": "Já existe contraparte com este "
                                        "nome."}, code=400); return
                    cp.nome = nome_cp
                    cp.tipo = tipo_cp
                    _cp_aplicar_campos(cp)
                    # espelha o nome denormalizado nos acordos vinculados
                    for ac_upd in db.query(AcordoFabrica).filter_by(contraparte_id=cp.id).all():
                        ac_upd.contraparte_nome = nome_cp
                        ac_upd.contraparte_tipo = tipo_cp
                    db.commit()
                    self.send_json({"ok": True, "contraparte": _contraparte_dict(cp)})
                    return

                if path == "/api/admin/acordos-fabrica":
                    # Acordos Financeiros (revisão 2026-07-21): cria o ACORDO com contraparte
                    # generalizada (fábrica|empresa|banco) e dispara a implantação no owner
                    # titular — pelo PL (×3.5, saldo pré-existente) ou por CAPTAÇÃO (empréstimo
                    # novo: o dinheiro entra no caixa). Conta corrente com empresa pode nascer
                    # zerada (acumula com o uso).
                    tipo = (req.get("tipo") or "").strip()
                    cp = db.get(ContraparteFinanceira, int(req.get("contraparte_id") or 0))
                    if cp is not None:      # revisão 2026-07-22: seletor do cadastro
                        ctp = cp.tipo
                        req["contraparte_nome"] = cp.nome
                    else:
                        ctp = (req.get("contraparte_tipo") or "fabrica").strip()
                    if tipo not in ("credito", "divida") or ctp not in ("fabrica", "empresa", "banco"):
                        self.send_json({"ok": False, "erro": "tipo deve ser credito|divida; "
                                        "contraparte fabrica|empresa|banco"}, code=400); return
                    _CONTAS_ACORDO = {("fabrica", "credito"): "1.1.08", ("fabrica", "divida"): "2.1.08",
                                      ("empresa", "credito"): "1.1.09", ("empresa", "divida"): "2.1.09",
                                      ("banco", "divida"): "2.1.10"}
                    conta = _CONTAS_ACORDO.get((ctp, tipo))
                    if conta is None:
                        self.send_json({"ok": False, "erro": "Combinação inválida (banco só como "
                                        "dívida/empréstimo)."}, code=400); return
                    loja = _ve_loja(req.get("loja_titular_id"))
                    if loja is None:
                        self.send_json({"ok": False, "erro": "Loja titular fora do escopo"}, code=403); return
                    try:
                        valor = round(float(req.get("valor") or 0), 2)
                    except (TypeError, ValueError):
                        valor = 0.0
                    if valor < 0 or (valor <= 0 and ctp != "empresa"):
                        self.send_json({"ok": False, "erro": "Informe o valor (> 0; conta corrente "
                                        "com empresa pode nascer zerada)."}, code=400); return
                    ac = AcordoFabrica(descricao=(req.get("descricao") or "").strip() or tipo,
                                       tipo=tipo, contraparte_tipo=ctp,
                                       contraparte_id=cp.id if cp else None,
                                       contraparte_nome=(req.get("contraparte_nome") or "").strip() or None,
                                       loja_titular_id=loja.id, conta_saldo=conta,
                                       valor_implantado=valor, criado_por_id=usuario.get("id"))
                    db.add(ac); db.flush()
                    if valor > 0:
                        ot_t, own_t = mod_contabil_owner(db, loja.id)
                        if ctp == "banco" and req.get("captacao"):
                            ev = "captacao_emprestimo"          # dinheiro entra AGORA no caixa
                        else:
                            ev = {("fabrica", "credito"): "implantacao_credito_fabrica",
                                  ("fabrica", "divida"): "implantacao_divida_fabrica",
                                  ("empresa", "credito"): "implantacao_credito_empresa",
                                  ("empresa", "divida"): "implantacao_divida_empresa",
                                  ("banco", "divida"): "implantacao_divida_banco"}[(ctp, tipo)]
                        _mcaf.registrar_evento(db, ot_t, own_t, ev, valor, ref="impl:acordo:%d" % ac.id)
                    db.commit()
                    self.send_json({"ok": True, "acordo": {"id": ac.id, "descricao": ac.descricao,
                                    "tipo": ac.tipo, "contraparte_tipo": ac.contraparte_tipo,
                                    "contraparte_nome": ac.contraparte_nome or "",
                                    "loja_titular_id": ac.loja_titular_id,
                                    "conta_saldo": ac.conta_saldo, "status": ac.status,
                                    "valor_implantado": ac.valor_implantado,
                                    "saldos": _acordo_saldos(db, ac)}})
                    return

                m_aj = re.match(r'^/api/admin/ajustes-fabrica/(\d+)/ativo$', path)
                if m_aj:
                    aj = db.get(AjusteFabrica, int(m_aj.group(1)))
                    if aj is None or _ve_loja(aj.loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    aj.ativo = 1 if req.get("ativo") else 0
                    db.commit()
                    self.send_json({"ok": True, "ajuste": _ajuste_fabrica_dict(aj)})
                    return

                m_mov = re.match(r'^/api/admin/acordos-fabrica/(\d+)/movimento$', path)
                if m_mov:
                    # Acordos Financeiros (revisão 2026-07-21): movimento manual no acordo —
                    # pagar (dívida), receber (crédito), atualizar (juros/encargos, só dívida:
                    # DR 5.5.02 — despesa corrente legítima) e transferir (crédito→crédito da
                    # MESMA loja; ex.: Verano move crédito da fábrica p/ a conta corrente da
                    # Inspirium). Tudo no razão da titular, capado ao saldo quando reduz.
                    ac = db.get(AcordoFabrica, int(m_mov.group(1)))
                    if ac is None or _ve_loja(ac.loja_titular_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if ac.status == "encerrado":
                        self.send_json({"ok": False, "erro": "Acordo encerrado."}, code=400); return
                    acao = (req.get("acao") or "").strip()
                    dest = None   # preenchido no branch "transferir"
                    try:
                        valor = round(float(req.get("valor") or 0), 2)
                    except (TypeError, ValueError):
                        valor = 0.0
                    # "pagar" aceita valor 0 quando há juros (parcela só-juros — QA Vera);
                    # as demais ações exigem valor > 0
                    if valor <= 0 and acao != "pagar":
                        self.send_json({"ok": False, "erro": "Informe o valor (> 0)."}, code=400); return
                    ot_t, own_t = mod_contabil_owner(db, ac.loja_titular_id)
                    ctp = (ac.contraparte_tipo or "fabrica")
                    # idempotência (QA Vera): nonce do cliente compõe o ref — duplo clique/retry
                    # de rede não lança duas vezes (crítico p/ "atualizar", que não tem cap)
                    nonce = str(req.get("nonce") or "")[:40]
                    if nonce:
                        ref = "mov:%d:%s" % (ac.id, nonce)
                    else:
                        seq = 1 + db.query(AcordoMovimento).filter_by(acordo_id=ac.id).count()
                        ref = "mov:%d:%d" % (ac.id, seq)
                    if _mcaf.lancamento_por_ref(db, ot_t, own_t, ref) is not None:
                        self.send_json({"ok": False, "erro": "Movimento já registrado "
                                        "(repetição detectada)."}, code=400); return
                    saldo = _acordo_saldos(db, ac)["contabil"]

                    if acao == "pagar":
                        # Revisão 2026-07-22: pagamento com NOMINAL (baixa o passivo) + JUROS
                        # (despesa 5.5.02 × caixa, direto no ato) — campos separados.
                        if ac.tipo != "divida":
                            self.send_json({"ok": False, "erro": "Pagar é para acordos de DÍVIDA."},
                                           code=400); return
                        try:
                            juros = round(float(req.get("juros") or 0), 2)
                        except (TypeError, ValueError):
                            juros = 0.0
                        v = round(min(valor, max(saldo, 0.0)), 2)
                        if v <= 0 and juros <= 0:
                            self.send_json({"ok": False, "erro": "Sem saldo a pagar."}, code=400); return
                        if v > 0:
                            ev = {"fabrica": "pagamento_divida_fabrica_caixa",
                                  "empresa": "liquidacao_conta_corrente_devedora",
                                  "banco": "pagamento_emprestimo"}[ctp]
                            _mcaf.registrar_evento(db, ot_t, own_t, ev, v, ref=ref)
                            db.add(AcordoMovimento(acordo_id=ac.id, tipo="pagamento", valor=v,
                                                   lancamento_ref=ref, criado_por_id=usuario.get("id")))
                        if juros > 0:
                            _mcaf.registrar_evento(db, ot_t, own_t, "pagamento_juros_acordo", juros,
                                                   ref=ref + ":juros")
                            db.add(AcordoMovimento(acordo_id=ac.id, tipo="juros_pagos", valor=juros,
                                                   lancamento_ref=ref + ":juros",
                                                   criado_por_id=usuario.get("id")))
                    elif acao == "receber":
                        if ac.tipo != "credito":
                            self.send_json({"ok": False, "erro": "Receber é para acordos de CRÉDITO."},
                                           code=400); return
                        v = round(min(valor, max(saldo, 0.0)), 2)
                        if v <= 0:
                            self.send_json({"ok": False, "erro": "Sem saldo a receber."}, code=400); return
                        ev = {"fabrica": "recebimento_credito_fabrica",
                              "empresa": "liquidacao_conta_corrente_credora"}.get(ctp)
                        if ev is None:
                            self.send_json({"ok": False, "erro": "Combinação inválida."}, code=400); return
                        _mcaf.registrar_evento(db, ot_t, own_t, ev, v, ref=ref)
                        db.add(AcordoMovimento(acordo_id=ac.id, tipo="recebimento", valor=v,
                                               lancamento_ref=ref, criado_por_id=usuario.get("id")))
                    elif acao == "atualizar":
                        if ac.tipo != "divida":
                            self.send_json({"ok": False, "erro": "Atualização (juros) é para "
                                            "acordos de DÍVIDA."}, code=400); return
                        ev = {"fabrica": "atualizacao_divida_fabrica",
                              "empresa": "atualizacao_divida_empresa",
                              "banco": "atualizacao_emprestimo"}[ctp]
                        v = valor
                        _mcaf.registrar_evento(db, ot_t, own_t, ev, v, ref=ref)
                        db.add(AcordoMovimento(acordo_id=ac.id, tipo="atualizacao", valor=v,
                                               lancamento_ref=ref, criado_por_id=usuario.get("id")))
                    elif acao == "transferir":
                        dest = db.get(AcordoFabrica, int(req.get("destino_acordo_id") or 0))
                        if (ac.tipo != "credito" or dest is None or dest.tipo != "credito"
                                or dest.loja_titular_id != ac.loja_titular_id or dest.id == ac.id
                                or dest.status == "encerrado"):
                            self.send_json({"ok": False, "erro": "Transferência exige DOIS acordos "
                                            "de crédito da mesma loja."}, code=400); return
                        v = round(min(valor, max(saldo, 0.0)), 2)
                        if v <= 0:
                            self.send_json({"ok": False, "erro": "Sem saldo a transferir."}, code=400); return
                        _mcaf.seed_plano(db, ot_t, own_t)
                        cd = _mcaf._conta_por_codigo(db, ot_t, own_t, dest.conta_saldo)
                        cc = _mcaf._conta_por_codigo(db, ot_t, own_t, ac.conta_saldo)
                        if cd.id == cc.id:   # mesma conta do razão (dois acordos de empresa): só a trilha
                            pass
                        else:
                            _mcaf.lancar(db, ot_t, own_t, cd.id, cc.id, v, origem="acordo_financeiro",
                                         historico="Transferência de saldo entre acordos financeiros",
                                         ref=ref)
                        db.add(AcordoMovimento(acordo_id=ac.id, tipo="transferencia_out", valor=v,
                                               lancamento_ref=ref, criado_por_id=usuario.get("id")))
                        db.add(AcordoMovimento(acordo_id=dest.id, tipo="transferencia_in", valor=v,
                                               lancamento_ref=ref, criado_por_id=usuario.get("id")))
                    elif acao in ("acrescer", "abater"):
                        # movimentos SEM caixa. Opção B (2026-07-22, decisão do Diretor): a
                        # CONTRAPARTIDA é escolhida no ato — "pl" (3.5, só p/ saldos de fatos
                        # PASSADOS, CPC 23) ou "resultado" (evento do período corrente:
                        # ganho 4.4.03 / perda 5.5.05 — não distorce a leitura da DRE×PL).
                        if acao == "abater":
                            v = round(min(valor, max(saldo, 0.0)), 2)
                            if v <= 0:
                                self.send_json({"ok": False, "erro": "Sem saldo a abater."}, code=400); return
                        else:
                            v = valor
                        contrapart = (req.get("contrapartida") or "pl").strip()
                        if contrapart not in ("pl", "resultado"):
                            self.send_json({"ok": False, "erro": "contrapartida deve ser "
                                            "pl|resultado"}, code=400); return
                        _mcaf.seed_plano(db, ot_t, own_t)
                        c_ac = _mcaf._conta_por_codigo(db, ot_t, own_t, ac.conta_saldo)
                        aumenta = (acao == "acrescer")
                        # ganho patrimonial: abater dívida OU acrescer crédito; perda: o inverso
                        ganho = (ac.tipo == "divida") != aumenta
                        if contrapart == "pl":
                            c_cp = _mcaf._conta_por_codigo(db, ot_t, own_t, "3.5")
                        else:
                            c_cp = _mcaf._conta_por_codigo(db, ot_t, own_t,
                                                           "4.4.04" if ganho else "5.5.05")
                        if ac.tipo == "divida":
                            cd, cc = ((c_cp, c_ac) if aumenta else (c_ac, c_cp))
                        else:
                            cd, cc = ((c_ac, c_cp) if aumenta else (c_cp, c_ac))
                        _mcaf.lancar(db, ot_t, own_t, cd.id, cc.id, v, origem="acordo_financeiro",
                                     historico=("Acréscimo manual de saldo do acordo (sem caixa, "
                                                if aumenta else
                                                "Abatimento manual de saldo do acordo (sem caixa, ")
                                               + ("contrapartida PL)" if contrapart == "pl"
                                                  else "contrapartida resultado)"),
                                     ref=ref)
                        db.add(AcordoMovimento(acordo_id=ac.id,
                                               tipo="acrescimo_manual" if aumenta else "abatimento_manual",
                                               valor=v, lancamento_ref=ref,
                                               criado_por_id=usuario.get("id")))
                    else:
                        self.send_json({"ok": False, "erro": "acao deve ser pagar|receber|"
                                        "atualizar|transferir|acrescer|abater"}, code=400); return
                    # recalcula o status SEMPRE (QA Vera: juros/transferência recebida devolvem
                    # saldo a um acordo esgotado — ele REATIVA; zerou → esgota)
                    for _ac_st in ({ac} | ({dest} if dest is not None else set())):
                        s2 = _acordo_saldos(db, _ac_st)
                        if s2["contabil"] <= 0.005 and _ac_st.status == "ativo":
                            _ac_st.status = "esgotado"
                        elif s2["contabil"] > 0.005 and _ac_st.status == "esgotado":
                            _ac_st.status = "ativo"
                    db.commit()
                    self.send_json({"ok": True, "valor": v, "saldos": _acordo_saldos(db, ac)})
                    return

                m_enc = re.match(r'^/api/admin/acordos-fabrica/(\d+)/encerrar$', path)
                if m_enc:
                    ac = db.get(AcordoFabrica, int(m_enc.group(1)))
                    if ac is None or _ve_loja(ac.loja_titular_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    s = _acordo_saldos(db, ac)
                    if s["contabil"] > 0.005:
                        if not req.get("baixar_residuo"):
                            self.send_json({"ok": False, "erro": "Saldo residual de R$ %.2f — "
                                            "confirme baixar_residuo para encerrar (baixa × 3.5)."
                                            % s["contabil"]}, code=400); return
                        ot_t, own_t = mod_contabil_owner(db, ac.loja_titular_id)
                        ctp_enc = (ac.contraparte_tipo or "fabrica")
                        if ctp_enc == "fabrica":
                            ev = ("baixa_credito_fabrica" if ac.tipo == "credito"
                                  else "baixa_divida_fabrica")
                            _mcaf.registrar_evento(db, ot_t, own_t, ev, s["contabil"],
                                                   ref="baixa:acordo:%d" % ac.id)
                        else:   # empresa/banco: baixa espelho da implantação (conta × 3.5)
                            _mcaf.seed_plano(db, ot_t, own_t)
                            c_ac = _mcaf._conta_por_codigo(db, ot_t, own_t, ac.conta_saldo)
                            c_pl = _mcaf._conta_por_codigo(db, ot_t, own_t, "3.5")
                            cd, cc = ((c_pl, c_ac) if ac.tipo == "credito" else (c_ac, c_pl))
                            _mcaf.lancar(db, ot_t, own_t, cd.id, cc.id, s["contabil"],
                                         origem="acordo_financeiro",
                                         historico="Baixa de resíduo no encerramento do acordo",
                                         ref="baixa:acordo:%d" % ac.id)
                        db.add(AcordoMovimento(acordo_id=ac.id, tipo="baixa_encerramento",
                                               valor=s["contabil"],
                                               lancamento_ref="baixa:acordo:%d" % ac.id,
                                               criado_por_id=usuario.get("id")))

                    ac.status = "encerrado"
                    db.commit()
                    self.send_json({"ok": True, "status": ac.status})
                    return

                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
            finally:
                db.close()
            return

        if path == "/api/admin/ajustes-fabrica":
            # cria a REGRA de consumo (% por loja). Validações da spec.
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                req = json.loads(body or b'{}')

                def _ve_loja2(lid):
                    lj = db.get(Loja, int(lid)) if lid else None
                    return lj if (lj and mod_tenancy.pode_ver_loja(
                        ator, {"id": lj.id, "rede_id": lj.rede_id})) else None

                loja = _ve_loja2(req.get("loja_id"))
                if loja is None:
                    self.send_json({"ok": False, "erro": "Loja fora do escopo"}, code=403); return
                tipo = (req.get("tipo") or "").strip()
                # Revisão 2026-07-22: descontos/acréscimos são SEMPRE de custo (mexem na provisão
                # de Custo de Fábrica na conferência, com vigência avaliada pela DATA DA VENDA).
                # O lado financeiro de créditos/dívidas é MANUAL, no painel de acordos —
                # consumir_saldo foi descontinuado.
                if (req.get("tratamento") or "custo") == "consumir_saldo" or req.get("acordo_id"):
                    self.send_json({"ok": False, "erro": "Descontos/acréscimos não se vinculam "
                                    "mais a acordos — o %% ajusta o Custo de Fábrica; o lado "
                                    "financeiro é lançado manualmente no acordo (acrescer/abater)."},
                                   code=400); return
                trat = "custo"
                natureza = (req.get("natureza") or "recorrente").strip()
                base = (req.get("base") or "pos_descontos").strip()
                try:
                    pct = round(float(req.get("pct")), 4)
                except (TypeError, ValueError):
                    pct = 0.0
                if tipo not in ("desconto", "acrescimo") or natureza not in ("recorrente", "pontual") \
                        or base not in ("pos_descontos", "valor_conferido") or not (0 < pct <= 100):
                    self.send_json({"ok": False, "erro": "Dados inválidos (tipo/natureza/base/pct)."},
                                   code=400); return
                acordo = None
                projetos = req.get("projetos")
                if natureza == "pontual" and not projetos:
                    self.send_json({"ok": False, "erro": "Ajuste pontual exige a lista de "
                                    "projetos vinculados."}, code=400); return
                # guarda (QA Vera 🟡): a soma dos descontos recorrentes ativos da loja não pode
                # passar de 100% do conferido (pós-descontos negativo corromperia as bases)
                if tipo == "desconto" and natureza == "recorrente":
                    soma = pct + sum(a.pct or 0 for a in
                                     db.query(AjusteFabrica).filter_by(
                                         loja_id=loja.id, tipo="desconto",
                                         natureza="recorrente", ativo=1).all())
                    if soma > 100.0:
                        self.send_json({"ok": False, "erro": "Descontos recorrentes ativos da "
                                        "loja somariam %.2f%% (> 100%%)." % soma}, code=400); return
                def _dt_vig(campo):
                    v = (req.get(campo) or "").strip()
                    if not v:
                        return None
                    try:
                        return datetime.fromisoformat(v[:10] + "T00:00:00")
                    except ValueError:
                        return None
                aj = AjusteFabrica(acordo_id=acordo.id if acordo else None, loja_id=loja.id,
                                   descricao=(req.get("descricao") or "").strip() or None,
                                   tipo=tipo, natureza=natureza, pct=pct, base=base,
                                   tratamento=trat,
                                   vigencia_de=_dt_vig("vigencia_de"),
                                   vigencia_ate=_dt_vig("vigencia_ate"),
                                   projetos_json=json.dumps(projetos) if projetos else None,
                                   criado_por_id=usuario.get("id"))
                db.add(aj); db.commit()
                self.send_json({"ok": True, "ajuste": _ajuste_fabrica_dict(aj)})
            finally:
                db.close()
            return

        m_peup = re.match(r'^/api/projetos/([^/]+)/pe/upload$', path)
        if m_peup:
            # Fatia 1 (desmembramento PE): upload de XML/Promob de PE FORA do pool (#2) — grava em
            # arquivo_pe, NÃO toca pool_ambientes (não dispara _contrato_assinado). CFO extraído do XML (#4).
            nome = unquote(m_peup.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()   # mod_tenancy/mod_pe_comparacao são module-level (não reimportar local)
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                if not arquivos:
                    self.send_json({"ok": False, "erro": "Nenhum arquivo recebido"}); return
                try:
                    pool_ambiente_id = int(campos.get("pool_ambiente_id"))
                except (TypeError, ValueError):
                    self.send_json({"ok": False, "erro": "pool_ambiente_id ausente/inválido"}); return
                pa = db.get(PoolAmbiente, pool_ambiente_id)
                if pa is None or pa.projeto_id != nome:
                    self.send_json({"ok": False, "erro": "Ambiente não pertence ao projeto"}, code=400); return
                import mod_retido as _mret   # gate operacional: parcela retida não avança (Fatia 2)
                _ok, _err = _mret.gate_operacao_ambiente(db, nome, pool_ambiente_id)
                if not _ok:
                    self.send_json({"ok": False, "erro": _err}, code=409); return
                filename, conteudo = next(iter(arquivos.values()))
                data = conteudo if isinstance(conteudo, (bytes, bytearray)) else str(conteudo).encode("utf-8")
                is_xml  = str(filename).lower().endswith(".xml")
                # Correção Fatia 3: finalidade=complemento grava o 3º XML do ambiente
                # (contrato=pool, executivo=xml_pe, complemento=xml_compl) — só p/ ambientes
                # MARCADOS na 11c, e obrigatoriamente .xml (a diferença precisa dos valores).
                finalidade = (campos.get("finalidade") or "pe").strip().lower()
                if finalidade == "complemento":
                    if not is_xml:
                        self.send_json({"ok": False, "erro": "Complemento de projeto exige "
                                        "arquivo XML."}); return
                    if not pa.renegociar_pe:
                        self.send_json({"ok": False, "erro": "Ambiente não está marcado para "
                                        "complemento na Revisão de PE."}, code=400); return
                    formato = "xml_compl"
                else:
                    formato = "xml_pe" if is_xml else "promob_pe"
                pe_dir = os.path.join(PROJETOS_DIR, nome, "pe", str(pool_ambiente_id))
                if finalidade == "complemento":
                    pe_dir = os.path.join(pe_dir, "compl")   # não colide com o arquivo do PE
                os.makedirs(pe_dir, exist_ok=True)
                dest = os.path.join(pe_dir, os.path.basename(str(filename)))
                with open(dest, "wb") as f:
                    f.write(data)
                valor = None
                if is_xml:
                    try:
                        valor = mod_pe_comparacao.extrair_cfo_pe(filename, data)
                        venda = mod_pe_comparacao.extrair_venda_pe(filename, data)
                    except Exception as e:
                        self.send_json({"ok": False, "erro": "XML de PE inválido: %s" % e}); return
                else:
                    venda = None
                reg = (db.query(ArquivoPE)
                         .filter_by(projeto_nome=nome, pool_ambiente_id=pool_ambiente_id, formato=formato).first())
                if reg is None:
                    reg = ArquivoPE(projeto_nome=nome, pool_ambiente_id=pool_ambiente_id, formato=formato)
                    db.add(reg)
                reg.arquivo_path     = dest
                reg.valor_atualizado = valor
                reg.valor_venda      = venda
                reg.carregado_em     = datetime.utcnow()
                reg.carregado_por_id = usuario.get("id")
                db.commit()
                self.send_json({"ok": True, "formato": formato, "valor_atualizado": valor})
            finally:
                db.close()
            return

        m_pereneg = re.match(r'^/api/projetos/([^/]+)/pe/renegociar$', path)
        if m_pereneg:
            # Fatia venda (2026-07-21): marca/desmarca "Renegociar" num ambiente da Revisão de PE.
            # Os marcados aparecem na Aprovação do PE pelo Cliente (11e) para o Negociar Complemento.
            nome = unquote(m_pereneg.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                req = json.loads(body or b'{}')
                try:
                    pa_id = int(req.get("pool_ambiente_id"))
                except (TypeError, ValueError):
                    self.send_json({"ok": False, "erro": "pool_ambiente_id ausente/inválido"}, code=400); return
                pa = db.get(PoolAmbiente, pa_id)
                if pa is None or pa.projeto_id != nome:
                    self.send_json({"ok": False, "erro": "Ambiente não pertence ao projeto"}, code=400); return
                pa.renegociar_pe = 1 if req.get("renegociar") else 0
                db.commit()
                self.send_json({"ok": True, "pool_ambiente_id": pa_id,
                                "renegociar": bool(pa.renegociar_pe)})
            finally:
                db.close()
            return

        m_peaj = re.match(r'^/api/projetos/([^/]+)/pe/complemento/orcamento$', path)
        if m_peaj:
            # Fatia 3 PE: get-or-create do ORÇAMENTO DE COMPLEMENTO (11e "Negociar Complemento") — contém só
            # os ambientes marcados Renegociar na 11c; base de valores = PE (breakdown complemento_pe).
            # Deliberadamente permitido com contrato assinado (é a razão de existir); nunca vira o
            # contratado (carregarOrcamentos sempre trava o default no contratado_id).
            nome = unquote(m_peaj.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                marcados = [pa.id for pa in db.query(PoolAmbiente)
                            .filter_by(projeto_id=nome).order_by(PoolAmbiente.id.asc()).all()
                            if pa.renegociar_pe]
                if not marcados:
                    self.send_json({"ok": False, "erro": "Nenhum ambiente marcado para complemento "
                                    "na Revisão de PE."}, code=400); return
                orc = (db.query(Orcamento).filter_by(projeto_id=nome, complemento_pe=1)
                         .order_by(Orcamento.id.desc()).first())
                if orc is None:
                    maior = max([o.ordem or 0 for o in
                                 db.query(Orcamento).filter_by(projeto_id=nome).all()] or [0])
                    orc = Orcamento(projeto_id=nome, nome="Complemento PE", ordem=maior + 1,
                                    desconto_pct=0.0, complemento_pe=1, loja_id=loja_id,
                                    created_by=usuario.get("id"))
                    db.add(orc); db.flush()
                # sincroniza os vínculos com as marcas atuais (marcar/desmarcar na 11c reflete aqui)
                atuais = {oa.pool_ambiente_id: oa for oa in
                          db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all()}
                for i, pid in enumerate(marcados):
                    if pid not in atuais:
                        db.add(OrcamentoAmbiente(orcamento_id=orc.id, pool_ambiente_id=pid, ordem=i + 1))
                for pid, oa in atuais.items():
                    if pid not in set(marcados):
                        db.delete(oa)
                # Correção (teste do usuário): a negociação do complemento PARTE do padrão À VISTA
                # com entrada R$ 0,00 — cada "Negociar Complemento" zera o plano de pagamento salvo.
                # Também descontamina o vazamento antigo (o painel do contratado era capturado pela
                # tela e persistido aqui via auto-save, puxando o total_cliente do CONTRATO para o
                # cust_fin do complemento → Val_Cont virava o total do contrato).
                orc.forma_pagamento = None
                orc.negociacao_json = None
                db.flush()
                try:
                    _recalcular_orcamento(orc, db)
                except Exception as _e:
                    print("[AJUSTE-PE] recálculo falhou:", _e)
                orc.updated_at = datetime.utcnow()
                db.commit()
                self.send_json({"ok": True, "orcamento": _orcamento_dict(orc)})
            finally:
                db.close()
            return

        # POST /api/projetos/<nome>/contatos-comunicacao/confirmar — decisão 13: registra a
        # escolha explícita do operador ('confirmado' | 'sem_whatsapp') com snapshot.
        m_ccf = re.match(r'^/api/projetos/([^/]+)/contatos-comunicacao/confirmar$', path)
        if m_ccf:
            nome = unquote(m_ccf.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                import mod_chat
                # Alias OBRIGATÓRIO — ver comentário no GET /contatos-comunicacao (escopo local).
                from integracoes.projetos_store import _carregar_projeto as _cp_chat
                dd = json.loads(body or b'{}')
                p_meta = db.query(Projeto).filter_by(nome_safe=nome).first()
                pj = _cp_chat(nome) or {}
                contatos = mod_chat.contatos_do_projeto(
                    db, cliente_id=(p_meta.cliente_id if p_meta else None),
                    parceiro_id=pj.get("parceiro_id"))
                try:
                    reg = mod_chat.registrar_confirmacao(db, loja_id, nome, usuario.get("id"),
                                                         (dd.get("modo") or "").strip(), contatos)
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "confirmacao": mod_chat.serializar_confirmacao(
                    reg, usuario.get("nome"))})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # POST .../conversa/mensagens/externo — Fatias 6-7: mensagem por canal EXTERNO
        # (e-mail/WhatsApp). Cria a Mensagem no canal-segmento + o EnvioExterno; o disparo ao
        # vivo é gated por credencial (sem ela, status pendente_config, sem tocar a rede).
        m_ext = re.match(r'^/api/projetos/([^/]+)/conversa/mensagens/externo$', path)
        if m_ext:
            nome = unquote(m_ext.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_visivel_da_loja(db, nome, loja_id, usuario) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                import mod_chat, mod_chat_externo as _ext
                dd = json.loads(body or b'{}')
                meio = (dd.get("meio") or "").strip()
                canal = (dd.get("canal") or "").strip()
                dtipo = (dd.get("destinatario_tipo") or "").strip()
                did_raw = dd.get("destinatario_id")
                try:
                    did = int(did_raw) if did_raw not in (None, "") else None
                except (TypeError, ValueError):
                    did = None
                avulso = dd.get("destino_avulso")
                if meio not in _ext.MEIOS:
                    self.send_json({"ok": False, "erro": "Meio inválido (email|whatsapp)."},
                                   code=400); return
                if canal not in _ext.CANAIS_EXTERNOS:
                    self.send_json({"ok": False, "erro": "Canal externo inválido."},
                                   code=400); return
                destino, derr = _ext.resolver_destino(db, meio, dtipo, did, avulso)
                if derr:
                    self.send_json({"ok": False, "erro": derr}, code=400); return
                p_meta = db.query(Projeto).filter_by(nome_safe=nome).first()
                conv = mod_chat.get_or_create_conversa_projeto(
                    db, loja_id, nome, cliente_id=(p_meta.cliente_id if p_meta else None))
                try:
                    msg = mod_chat.enviar_mensagem(db, conv, usuario.get("id"), dd.get("corpo"),
                                                   canal=canal, _permitir_externo=True)
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                env = _ext.registrar_envio(db, msg, meio, canal, dtipo, did, destino)
                if env.status == "enfileirado":
                    ok, id_ext, erro = _ext.despachar(env, msg.corpo)
                    if ok:
                        env.status = "enviado"; env.id_externo = id_ext
                    else:
                        env.status = "falhou"; env.erro = erro
                db.commit()
                self.send_json({"ok": True,
                                "envio": {"id": env.id, "meio": env.meio, "canal": env.canal,
                                          "status": env.status, "destino": env.destino,
                                          "erro": env.erro}}, code=201)
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # POST .../conversa/mensagens/<id>/resolver — Fatia 3: resolução NORMAL do bloqueador.
        # EXCLUSIVA de quem recebeu a transferência (ponte Usuário↔Funcionário).
        # POST .../conversa/mensagens/<id>/destravar-emergencia — válvula: capacidade
        # 'autorizar' (master/gerencial), motivo obrigatório, LogAcaoGerencial.
        m_res = re.match(r'^/api/projetos/([^/]+)/conversa/mensagens/(\d+)/'
                         r'(resolver|destravar-emergencia)$', path)
        if m_res:
            nome = unquote(m_res.group(1))
            msg_id = int(m_res.group(2))
            acao_res = m_res.group(3)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_visivel_da_loja(db, nome, loja_id, usuario) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                import mod_chat
                from database import ConversaMensagem as _CM, Conversa as _CV
                row = (db.query(_CM, _CV)
                         .join(_CV, _CM.conversa_id == _CV.id)
                         .filter(_CM.id == msg_id).first())
                if row is None or row[1].projeto_nome != nome or row[1].loja_id != loja_id:
                    self.send_json({"ok": False, "erro": "Mensagem não encontrada."}, code=404)
                    return
                msg = row[0]
                if not msg.bloqueador:
                    self.send_json({"ok": False, "erro": "Esta mensagem não é um bloqueador."},
                                   code=400); return
                if msg.resolvido_em is not None:
                    self.send_json({"ok": False, "erro": "Bloqueador já resolvido."},
                                   code=400); return
                req = json.loads(body or b'{}')
                if acao_res == "resolver":
                    fid = _funcionario_do_usuario(db, usuario.get("id"))
                    if not fid or fid != msg.transferido_para_funcionario_id:
                        self.send_json({"ok": False, "erro": "Só quem recebeu a transferência "
                                        "pode resolvê-la (use a válvula de emergência da "
                                        "gerência se necessário)."}, code=403); return
                else:
                    motivo = (req.get("motivo") or "").strip()
                    if not motivo:
                        self.send_json({"ok": False, "erro": "Informe o motivo do "
                                        "destravamento de emergência."}, code=400); return
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    autorizador = _usuario_com_capacidade(db, login, senha, "autorizar",
                                                          sessao=usuario)
                    if not autorizador:
                        self.send_json({"ok": False, "erro": "Credenciais inválidas ou perfil "
                                        "sem permissão (Gerente/Diretor)."}, code=403); return
                    db.add(LogAcaoGerencial(
                        solicitante_id=usuario["id"],
                        autorizador_id=autorizador.id,
                        acao="destravar_bloqueador",
                        projeto_nome=nome,
                        etapa_alvo=msg.etapa_codigo,
                        contexto=json.dumps({"mensagem_id": msg.id, "motivo": motivo},
                                            ensure_ascii=False)))
                msg.resolvido_em = datetime.utcnow()
                db.commit()
                nome_transf = None
                if msg.transferido_para_funcionario_id:
                    _ft = db.get(Funcionario, msg.transferido_para_funcionario_id)
                    nome_transf = _ft.nome if _ft else None
                self.send_json({"ok": True, "mensagem": mod_chat.serializar_mensagem(
                    msg, None, nome_transf)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # POST /api/comunicacao/assuntos — Orizon Chat (Fatia 2): cria um assunto custom na loja.
        if path == "/api/comunicacao/assuntos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                try:
                    a = mod_chat.criar_assunto(db, loja_id, usuario["id"], dd.get("nome"))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "assunto": {"id": a.id, "nome": a.nome}}, code=201)
            finally:
                db.close()
            return

        # POST /api/comunicacao/forum — Fatia 4: cria um DEBATE no Fórum da Loja (escopo=loja) ou
        # no Fórum Orizon (escopo=orizon, cross-loja pela rede). Título + assunto.
        if path == "/api/comunicacao/forum":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                escopo = (dd.get("escopo") or "loja")
                a_tipo = (dd.get("assunto_tipo") or "livre").strip()
                a_proj = dd.get("projeto_nome")
                if escopo == "loja" and a_tipo == "projeto":
                    if not a_proj or _projeto_da_loja(db, a_proj, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Projeto do assunto inválido nesta loja."},
                                       code=400); return
                rede = mod_chat._rede_da_loja(db, loja_id)
                try:
                    conv = mod_chat.criar_debate(db, escopo, loja_id, rede, usuario["id"],
                                                 dd.get("titulo"), assunto_tipo=a_tipo,
                                                 projeto_nome=a_proj, assunto_id=dd.get("assunto_id"))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "debate": {"id": conv.id, "titulo": conv.titulo,
                                "tipo": conv.tipo}}, code=201)
            finally:
                db.close()
            return

        # POST /api/comunicacao/conversas — Central de Comunicação (Fatia 1): abre uma conversa
        # direct (idempotente pela dupla) ou grupo. Participantes têm que ser da loja ativa.
        if path == "/api/comunicacao/conversas":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                # assunto=projeto NÃO cria direct/grupo — ABRE a CONVERSA DO PROJETO (unificação
                # 2026-07-27), com a equipe derivada já sincronizada.
                if (dd.get("assunto_tipo") or "").strip() == "projeto":
                    _pn = dd.get("projeto_nome")
                    if not _pn or _projeto_da_loja(db, _pn, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Projeto inválido nesta loja."}, code=400); return
                    import mod_equipe
                    _pm = db.query(Projeto).filter_by(nome_safe=_pn).first()
                    conv = mod_chat.get_or_create_conversa_projeto(
                        db, loja_id, _pn, cliente_id=(_pm.cliente_id if _pm else None))
                    try:
                        _eqp = mod_equipe.equipe_do_projeto(db, _pn, loja_id)
                        mod_chat.sincronizar_participantes_projeto(db, conv, _eqp["membros_usuarios"])
                    except Exception as _es:
                        print("[EQUIPE] sync na abertura via chat falhou:", _es)
                    db.commit()
                    self.send_json({"ok": True,
                                    "conversa": mod_chat.serializar_conversa(db, conv, usuario["id"])},
                                   code=201)
                    return
                tipo = (dd.get("tipo") or "").strip()
                if tipo not in ("direct", "grupo"):
                    self.send_json({"ok": False, "erro": "Tipo inválido (direct|grupo)."}, code=400); return
                # participantes solicitados precisam ser usuários ATIVOS da loja ativa
                raw_ids = dd.get("participante_ids") or ([] if tipo == "grupo" else
                          ([dd.get("usuario_id")] if dd.get("usuario_id") else []))
                try:
                    pedidos = [int(x) for x in raw_ids if x]
                except (TypeError, ValueError):
                    self.send_json({"ok": False, "erro": "Participantes inválidos."}, code=400); return
                if pedidos:
                    validos = {u.id for u in db.query(Usuario)
                               .filter(Usuario.id.in_(pedidos), Usuario.loja_id == loja_id,
                                       Usuario.ativo == 1).all()}
                    if set(pedidos) - validos:
                        self.send_json({"ok": False, "erro": "Escolha usuários desta loja."},
                                       code=400); return
                # Assunto (Fatia 2): livre (default) | projeto (projeto_nome, tem que ser da loja)
                # | custom (assunto_id da loja). Projeto do assunto valida via _projeto_da_loja.
                a_tipo = (dd.get("assunto_tipo") or "livre").strip()
                a_proj = dd.get("projeto_nome")
                a_id = dd.get("assunto_id")
                if a_tipo == "projeto":
                    if not a_proj or _projeto_da_loja(db, a_proj, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Projeto do assunto inválido nesta loja."},
                                       code=400); return
                # Participantes EXTERNOS (contato WhatsApp/e-mail, sem Usuario) — Orizon Chat 2026-07-28.
                externos = dd.get("externos") or []
                if not isinstance(externos, list):
                    externos = []
                try:
                    if tipo == "direct":
                        if len(pedidos) == 1 and not externos:
                            conv = mod_chat.get_or_create_direct(db, loja_id, usuario["id"], pedidos[0],
                                                                 assunto_tipo=a_tipo, projeto_nome=a_proj,
                                                                 assunto_id=a_id)
                        elif not pedidos and externos:
                            # Individual com CONTATO EXTERNO → grupo com o criador + o externo.
                            _tit = (externos[0].get("nome") or "Contato externo").strip()
                            conv = mod_chat.criar_grupo(db, loja_id, usuario["id"], _tit, [],
                                                        assunto_tipo=a_tipo, projeto_nome=a_proj,
                                                        assunto_id=a_id, exige_dois=False)
                        else:
                            self.send_json({"ok": False, "erro": "Individual: escolha 1 destinatário interno "
                                            "OU 1 contato externo."}, code=400); return
                    else:
                        conv = mod_chat.criar_grupo(db, loja_id, usuario["id"],
                                                    dd.get("titulo"), pedidos,
                                                    assunto_tipo=a_tipo, projeto_nome=a_proj,
                                                    assunto_id=a_id, exige_dois=(not externos))
                    for ex in externos:
                        mod_chat.adicionar_externo(db, conv, ex.get("nome"), ex.get("telefone"),
                                                   ex.get("email"), (ex.get("meio") or "whatsapp"),
                                                   usuario["id"])
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True,
                                "conversa": mod_chat.serializar_conversa(db, conv, usuario["id"])},
                               code=201)
            finally:
                db.close()
            return

        # POST /api/comunicacao/iniciar-conversa — Atendimentos UI (spec 2026-08-04 §11): fecha o
        # modal de 3 etapas ("Novo Contato"/"Iniciar Conversa"). Body:
        # {contato:{cliente_id} | {nome,telefone,email?}, template_id | livre:true, valores:{}}.
        if path == "/api/comunicacao/iniciar-conversa":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                try:
                    conv = mod_chat.iniciar_conversa_externa(
                        db, loja_id, usuario["id"], dd.get("contato") or {},
                        template_id=dd.get("template_id"), livre=bool(dd.get("livre")),
                        valores=dd.get("valores") or {})
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True,
                                "conversa": mod_chat.serializar_conversa(db, conv, usuario["id"])},
                               code=201)
            finally:
                db.close()
            return

        # POST /api/comunicacao/presenca — Fatia 6: heartbeat de presença (ponte WhatsApp).
        if path == "/api/comunicacao/presenca":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                import mod_chat_externo
                mod_chat_externo.registrar_presenca(db, usuario["id"]); db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # POST /api/comunicacao/conversas/<id>/anexos — Fatia 5: mensagem com ANEXO (foto/arquivo).
        # Multipart: campo 'arquivo' (obrigatório) + 'corpo' (opcional). Mesmas regras de escrita.
        m_anx = re.match(r'^/api/comunicacao/conversas/(\d+)/anexos$', path)
        if m_anx:
            conv_id = int(m_anx.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat, mimetypes
                from database import Conversa as _CV_anx
                conv = db.get(_CV_anx, conv_id)
                _rede = mod_chat._rede_da_loja(db, loja_id)
                _adm = perfis.pode(usuario.get("nivel"), "ver_todas_conversas")
                _pode_ler = conv is not None and (
                    mod_chat.pode_ler_conversa(db, conv, loja_id, usuario["id"], rede_id=_rede)
                    or (_adm and conv.loja_id == loja_id))
                if not _pode_ler:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_chat.pode_escrever_conversa(db, conv, loja_id, usuario["id"],
                                                       rede_id=_rede, is_admin_chat=_adm):
                    self.send_json({"ok": False, "erro": "Sem permissão para postar aqui."}, code=403); return
                if "arquivo" not in arquivos or not arquivos["arquivo"][1]:
                    self.send_json({"ok": False, "erro": "Anexe um arquivo."}, code=400); return
                fname, data = arquivos["arquivo"]
                base_nome = os.path.basename(fname) or "arquivo"
                mime = mimetypes.guess_type(base_nome)[0] or "application/octet-stream"
                unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                rel = os.path.join(str(loja_id or "rede"), unico)
                seg = mod_chat.canal_segmento_do_usuario(db, loja_id, usuario["id"])
                try:
                    msg = mod_chat.enviar_mensagem(db, conv, usuario["id"], campos.get("corpo") or "",
                                                   canal_segmento=seg, permitir_vazio=True)
                    anexo = mod_chat.criar_anexo(db, msg.id, base_nome, mime, len(data), rel)
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                try:
                    import mod_chat_externo as _mce
                    _mce.notificar_conversa(db, conv, msg, usuario["id"])
                    _mce.espelhar_para_externos(db, conv, msg, autor_nome=usuario.get("nome")); db.commit()
                except Exception:
                    db.rollback()   # ponte WhatsApp é best-effort — nunca quebra o anexo
                storage_salvar_binario(os.path.join(_BASE_DIR, "COMUNICACAO", rel), data)
                nome = (db.get(Usuario, usuario["id"]).nome if usuario.get("id") else None)
                self.send_json({"ok": True, "mensagem": mod_chat.serializar_mensagem(
                    msg, autor_nome=nome,
                    anexos=[mod_chat._serializar_anexo(anexo)])}, code=201)
            finally:
                db.close()
            return

        # POST /api/comunicacao/conversas/<id>/segmento — define/troca o segmento MANUAL do
        # atendimento (r3: a triagem indica; entrada sem segmento é a GERÊNCIA quem trata).
        # Body: {segmento: "comercial"|...|""} — vazio limpa (volta a derivar do tráfego).
        m_seg = re.match(r'^/api/comunicacao/conversas/(\d+)/segmento$', path)
        if m_seg:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if not perfis.pode(usuario.get("nivel"), "autorizar"):
                self.send_json({"ok": False, "erro": "Sem permissão (gerência)."}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                from database import Conversa as _CV_seg
                conv = db.get(_CV_seg, int(m_seg.group(1)))
                if conv is None or conv.loja_id != loja_id:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                dd = json.loads(body or b'{}')
                try:
                    seg = mod_chat.definir_segmento(db, conv, dd.get("segmento"))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "segmento": seg})
            finally:
                db.close()
            return

        # POST /api/comunicacao/contatos — "Adicionar Contato" (r3): cadastra o contato como
        # CLIENTE (fonte de contatos) + participante EXTERNO na conversa do projeto associado
        # (ou num grupo de lead novo); o MOTIVO vira evento inline.
        if path == "/api/comunicacao/contatos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                pnome = (dd.get("projeto_nome") or "").strip() or None
                if pnome and _projeto_visivel_da_loja(db, pnome, loja_id, usuario) is None:
                    self.send_json({"ok": False, "erro": "Projeto não encontrado."}, code=404); return
                try:
                    conv, reg = mod_chat.adicionar_contato(
                        db, loja_id, usuario["id"], dd.get("nome"),
                        telefone=dd.get("telefone"), email=dd.get("email"),
                        motivo=dd.get("motivo"), projeto_nome=pnome,
                        segmento=dd.get("segmento"),
                        tipo=dd.get("tipo") or "cliente")
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "conversa_id": conv.id,
                                "cadastro_id": (reg.id if reg is not None else None),
                                "tipo": dd.get("tipo") or "cliente"},
                               code=201)
            finally:
                db.close()
            return

        # POST /api/comunicacao/conversas/<id>/arquivar — arquiva/desarquiva PARA O USUÁRIO
        # (revisão UX 2026-07-31; aba Arquivadas da F7/Chat Interno). Body: {arquivar: bool}.
        m_arq = re.match(r'^/api/comunicacao/conversas/(\d+)/arquivar$', path)
        if m_arq:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                from database import Conversa as _CV_arq
                conv = db.get(_CV_arq, int(m_arq.group(1)))
                if conv is None or conv.loja_id != loja_id:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                dd = json.loads(body or b'{}')
                try:
                    flag = mod_chat.arquivar_conversa(db, conv, usuario["id"],
                                                      arquivar=bool(dd.get("arquivar", True)))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "arquivada": flag})
            finally:
                db.close()
            return

        # POST /api/comunicacao/conversas/<id>/{transferir|urgente|concluir} — Atendimentos UI
        # (spec 2026-08-04): transferir responsável (§7.1-A), urgência manual (§6.1) e conclusão
        # do atendimento (§8, com notificação interna à gerência pós-commit). Participante da
        # conversa ou gerência (ver_todas_conversas).
        m_atd = re.match(r'^/api/comunicacao/conversas/(\d+)/(transferir|urgente|concluir)$', path)
        if m_atd:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                from database import Conversa as _CV_atd
                conv = db.get(_CV_atd, int(m_atd.group(1)))
                if conv is None or conv.loja_id != loja_id:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                _adm = perfis.pode(usuario.get("nivel"), "ver_todas_conversas")
                if not (_adm or mod_chat.eh_participante(db, conv.id, usuario["id"])):
                    self.send_json({"ok": False, "erro": "Você não participa desta conversa."},
                                   code=403); return
                dd = json.loads(body or b'{}')
                acao = m_atd.group(2)
                try:
                    if acao == "transferir":
                        u_dest = mod_chat.transferir_responsavel(db, conv, usuario["id"],
                                                                 dd.get("usuario_id"))
                        db.commit()
                        self.send_json({"ok": True, "responsavel":
                                        {"id": u_dest.id, "nome": u_dest.nome}})
                    elif acao == "urgente":
                        flag = mod_chat.definir_urgencia(db, conv, usuario["id"],
                                                         bool(dd.get("on", True)))
                        db.commit()
                        self.send_json({"ok": True, "urgente": flag})
                    else:   # concluir
                        tpl_id = dd.get("template_id")
                        if tpl_id:
                            from database import TemplateMensagem as _TM_concl
                            import mod_chat_externo as _ext_concl
                            t = db.query(_TM_concl).filter_by(id=int(tpl_id),
                                                               loja_id=loja_id).first()
                            if t is None:
                                self.send_json({"ok": False,
                                                "erro": "Modelo de mensagem não encontrado."},
                                               code=400); return
                            _ext_concl.enviar_template_conversa(db, conv, usuario["id"], t,
                                                                 dd.get("valores") or {})
                        mod_chat.concluir_atendimento(db, conv, usuario["id"],
                                                      dd.get("observacao"))
                        db.commit()
                        # notificação interna à gerência: best-effort PÓS-commit — falha na
                        # notificação nunca desfaz a conclusão (padrão do aviso de montador).
                        notificados = 0
                        try:
                            notificados = mod_chat.notificar_conclusao_gerencia(
                                db, conv, usuario["id"])
                            db.commit()
                        except Exception:
                            db.rollback()
                        self.send_json({"ok": True, "status": "concluida",
                                        "notificados": notificados})
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
            finally:
                db.close()
            return

        # POST /api/comunicacao/conversas/<id>/participantes — override manual da membership
        # (add|remove). Só Gerente/Diretor (ver_todas_conversas). Body: {usuario_id, acao}.
        m_cp = re.match(r'^/api/comunicacao/conversas/(\d+)/participantes$', path)
        if m_cp:
            conv_id = int(m_cp.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if not perfis.pode(usuario.get("nivel"), "ver_todas_conversas"):
                self.send_json({"ok": False, "erro": "Sem permissão para gerir membros."}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                from database import Conversa as _CV_gp
                conv = db.get(_CV_gp, conv_id)
                if conv is None or conv.loja_id != loja_id or conv.tipo not in ("projeto", "grupo"):
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                dd = json.loads(body or b'{}')
                acao = (dd.get("acao") or "").strip()
                try:
                    if acao == "add_externo":
                        mod_chat.adicionar_externo(db, conv, dd.get("nome"), dd.get("telefone"),
                                                   dd.get("email"), (dd.get("meio") or "whatsapp"),
                                                   usuario["id"])
                    elif acao == "remove_externo":
                        mod_chat.remover_externo(db, conv, dd.get("externo_id"))
                    else:
                        alvo = dd.get("usuario_id")
                        if not alvo or db.query(Usuario).filter_by(id=int(alvo), loja_id=loja_id, ativo=1).first() is None:
                            self.send_json({"ok": False, "erro": "Escolha um usuário desta loja."}, code=400); return
                        mod_chat.gerir_participante(db, conv, alvo, acao)
                except ValueError as ve:
                    db.rollback(); self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "participantes": mod_chat.listar_participantes(db, conv)})
            finally:
                db.close()
            return

        # POST /api/comunicacao/templates[/<id>[/remover]] — CRUD da biblioteca de templates (RF-07).
        # Só gerência (autorizar); escopado por loja. Criar (sem id) | editar (<id>) | remover (<id>/remover).
        m_tpl = re.match(r'^/api/comunicacao/templates(?:/(\d+)(/remover)?)?$', path)
        if m_tpl:
            tpl_id, remover = m_tpl.group(1), m_tpl.group(2)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if not perfis.pode(usuario.get("nivel"), "autorizar"):
                self.send_json({"ok": False, "erro": "Sem permissão para gerir templates."}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                try:
                    if remover:
                        if not mod_chat.remover_template(db, loja_id, tpl_id):
                            self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                        db.commit(); self.send_json({"ok": True}); return
                    if tpl_id:
                        t = mod_chat.editar_template(db, loja_id, tpl_id, dd)
                        if t is None:
                            self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    else:
                        t = mod_chat.criar_template(db, loja_id, dd, criado_por_id=usuario.get("id"))
                except ValueError as ve:
                    db.rollback(); self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "template": mod_chat._serializar_template(t)},
                               code=(200 if tpl_id else 201))
            finally:
                db.close()
            return

        # POST /api/comunicacao/triagem — salva a config da pergunta de triagem (RF-08). Gerência.
        if path == "/api/comunicacao/triagem":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if not perfis.pode(usuario.get("nivel"), "autorizar"):
                self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                cfg = mod_chat.triagem_config_salvar(db, loja_id, dd); db.commit()
                self.send_json({"ok": True, "triagem": cfg})
            finally:
                db.close()
            return

        # POST /api/comunicacao/segmentos/criar — '+ novo segmento' (r4): canal de entrada
        # CUSTOM da loja. Gerência. Body: {rotulo}.
        # POST /api/comunicacao/segmentos/apagar — apaga segmento CUSTOM (base só desativa).
        if path in ("/api/comunicacao/segmentos/criar", "/api/comunicacao/segmentos/apagar"):
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if not perfis.pode(usuario.get("nivel"), "autorizar"):
                self.send_json({"ok": False, "erro": "Sem permissão (gerência)."}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                try:
                    if path.endswith("/criar"):
                        mod_chat.criar_segmento(db, loja_id, dd.get("rotulo"))
                    else:
                        mod_chat.apagar_segmento(db, loja_id, dd.get("segmento"))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True, "segmentos": mod_chat.segmentos_config_get(db, loja_id)})
            finally:
                db.close()
            return

        # POST /api/comunicacao/segmentos — salva a config dos segmentos (RF-02). Gerência.
        if path == "/api/comunicacao/segmentos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if not perfis.pode(usuario.get("nivel"), "autorizar"):
                self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                segs = mod_chat.segmentos_config_salvar(db, loja_id, dd.get("itens") or []); db.commit()
                self.send_json({"ok": True, "segmentos": segs})
            finally:
                db.close()
            return

        # POST /api/comunicacao/numeros — salva o número WhatsApp exibível da loja (RF-01). Gerência.
        # Só o número visível ao cliente — token/Phone Number ID NÃO passam por aqui (variável de ambiente).
        if path == "/api/comunicacao/numeros":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            if not perfis.pode(usuario.get("nivel"), "autorizar"):
                self.send_json({"ok": False, "erro": "Sem permissão."}, code=403); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                dd = json.loads(body or b'{}')
                num = mod_chat.numero_conectado_salvar(db, loja_id, dd.get("numero"), dd.get("rotulo")); db.commit()
                self.send_json({"ok": True, "numero": num})
            finally:
                db.close()
            return

        # POST /api/comunicacao/conversas/<id>/mensagens — nova mensagem numa conversa
        # direct/grupo (só participante posta). canal_segmento derivado da função do autor.
        m_cmsg = re.match(r'^/api/comunicacao/conversas/(\d+)/mensagens$', path)
        if m_cmsg:
            conv_id = int(m_cmsg.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                import mod_chat
                from database import Conversa as _CV_post
                conv = db.get(_CV_post, conv_id)
                # Postar: participante (direct/grupo), usuário da loja (forum_loja), usuário da rede
                # (forum_orizon) ou GERÊNCIA (mural). Oversight não permite postar em DM alheia.
                _rede = mod_chat._rede_da_loja(db, loja_id)
                _adm = perfis.pode(usuario.get("nivel"), "ver_todas_conversas")
                _pode_ler = conv is not None and (
                    mod_chat.pode_ler_conversa(db, conv, loja_id, usuario["id"], rede_id=_rede)
                    or (_adm and conv.loja_id == loja_id))
                if not _pode_ler:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_chat.pode_escrever_conversa(db, conv, loja_id, usuario["id"],
                                                       rede_id=_rede, is_admin_chat=_adm):
                    self.send_json({"ok": False, "erro": "Sem permissão para postar aqui."}, code=403); return
                dd = json.loads(body or b'{}')
                seg = mod_chat.canal_segmento_do_usuario(db, loja_id, usuario["id"])
                try:
                    msg = mod_chat.enviar_mensagem(db, conv, usuario["id"], dd.get("corpo"),
                                                   canal_segmento=seg,
                                                   destinatario_usuario_id=dd.get("destinatario_usuario_id"))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                try:
                    import mod_chat_externo as _mce
                    _mce.notificar_conversa(db, conv, msg, usuario["id"])
                    _mce.espelhar_para_externos(db, conv, msg, autor_nome=usuario.get("nome")); db.commit()
                except Exception:
                    db.rollback()   # ponte WhatsApp best-effort — nunca quebra a mensagem
                nome = (db.get(Usuario, usuario["id"]).nome if usuario.get("id") else None)
                self.send_json({"ok": True,
                                "mensagem": mod_chat.serializar_mensagem(msg, autor_nome=nome)},
                               code=201)
            finally:
                db.close()
            return

        # POST /api/projetos/<nome>/conversa/documento/<id>/encaminhar — spec 2026-07-31
        # (decisão 3): encaminha um CicloDocumento pelo WhatsApp da conversa aos participantes
        # EXTERNOS. Dentro da janela de 24h → mídia (config-gated); fora → 400 com instrução de
        # template (F3 pendente).
        m_enc = re.match(r'^/api/projetos/([^/]+)/conversa/documento/(\d+)/encaminhar$', path)
        if m_enc:
            nome = unquote(m_enc.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_visivel_da_loja(db, nome, loja_id, usuario) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                import mod_chat, mod_chat_externo as _ext
                import mimetypes as _mt
                doc = db.get(CicloDocumento, int(m_enc.group(2)))
                if doc is None or doc.projeto_nome != nome:
                    self.send_json({"ok": False, "erro": "Documento não encontrado."}, code=404); return
                conv = mod_chat.get_or_create_conversa_projeto(db, loja_id, nome)
                caminho = os.path.join(_projeto_path(nome), doc.arquivo_path)
                mime = _mt.guess_type(doc.nome_original or "")[0]
                try:
                    msg, envios = _ext.encaminhar_documento_externo(
                        db, conv, doc, usuario["id"], caminho, mime=mime)
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                db.commit()
                self.send_json({"ok": True,
                                "envios": [{"id": e.id, "status": e.status, "destino": e.destino}
                                           for e in envios]}, code=201)
            finally:
                db.close()
            return

        # POST /api/projetos/<nome>/conversa/mensagens — chat Fatia 1: nova mensagem interna.
        m_conv = re.match(r'^/api/projetos/([^/]+)/conversa/mensagens$', path)
        if m_conv:
            nome = unquote(m_conv.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_visivel_da_loja(db, nome, loja_id, usuario) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                import mod_chat
                dd = json.loads(body or b'{}')
                p_meta = db.query(Projeto).filter_by(nome_safe=nome).first()
                # "Transferência de responsabilidade"/Bloqueador via Chat foi REMOVIDA (decisão do
                # usuário, FATIA 7 2026-08-05): o Chat é só canal de comunicação; atribuir
                # responsável por etapa já tem porta própria — cronoResponsavelSalvar() na tela de
                # Etapas do Projeto, POST /api/projetos/<nome>/ciclo/<codigo>/responsavel, MESMO
                # campo CicloEtapa.responsavel_funcionario_id (v12) que a transferência escrevia.
                # Bloqueador de verdade (travar operação) é a Retenção (mod_retido.py, botão
                # dedicado nas etapas 9/10/11/17) — mecanismo diferente, não tocado aqui. A
                # mensageria automática de passagem de fase (mod_chat.mensagem_passagem_fase)
                # continua usando natureza="transferencia" internamente, sem passar por este
                # payload de usuário.
                try:
                    conv = mod_chat.get_or_create_conversa_projeto(
                        db, loja_id, nome,
                        cliente_id=(p_meta.cliente_id if p_meta else None))
                    msg = mod_chat.enviar_mensagem(
                        db, conv, usuario.get("id"), dd.get("corpo"),
                        destinatario_usuario_id=dd.get("destinatario_usuario_id"))
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400); return
                try:
                    import mod_chat_externo as _mce
                    _mce.espelhar_para_externos(db, conv, msg, autor_nome=usuario.get("nome"))
                except Exception:
                    pass   # best-effort: espelho externo nunca quebra a mensagem interna
                db.commit()
                self.send_json({"ok": True,
                                "mensagem": mod_chat.serializar_mensagem(msg, usuario.get("nome"))},
                               code=201)
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m_adger = re.match(r'^/api/projetos/([^/]+)/aditivo$', path)
        if m_adger:
            # Fatia 3 PE: gera/regenera o TERMO ADITIVO — documenta a DIFERENÇA dos ambientes
            # do complemento (orçamento de complemento × contrato original). SEM efeito contábil (decisão
            # do usuário: gerencial; acerto na liquidação/NF-e). Modelo da loja tipo 'termo_aditivo'
            # (obrigatório), versão CONGELADA na 1ª geração (padrão do contrato).
            nome = unquote(m_adger.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                contrato = (db.query(Contrato).filter_by(projeto_nome=nome)
                              .order_by(Contrato.id.desc()).first())
                if contrato is None or not _contrato_assinado(nome, db):
                    self.send_json({"ok": False, "erro": "O termo aditivo exige contrato assinado."},
                                   code=400); return
                orc_aj = (db.query(Orcamento).filter_by(projeto_id=nome, complemento_pe=1)
                            .order_by(Orcamento.id.desc()).first())
                if orc_aj is None:
                    self.send_json({"ok": False, "erro": "Negocie o complemento antes de gerar o termo "
                                    "aditivo (11e → Negociar Complemento)."}, code=400); return
                # Spec 2026-07-22 (modelo jurídico + modais): o request pode trazer os 5 blocos
                # editados no wizard ({"blocos": {...}}; ausente/vazio → default), "preview"
                # (PDF sem persistir NADA) e "novo" (após o último assinado, abre o PRÓXIMO
                # aditivo — o assinado nunca é regerado).
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    req = {}
                preview = bool(req.get("preview"))
                blocos_req = req.get("blocos") or {}
                aditivo = (db.query(Aditivo).filter_by(projeto_nome=nome)
                             .order_by(Aditivo.id.desc()).first())
                if aditivo is not None and aditivo.status == "assinado":
                    if req.get("novo") or preview:
                        aditivo = None            # preview/novo trabalham no PRÓXIMO aditivo
                    else:
                        self.send_json({"ok": False, "erro": "Termo aditivo já assinado — não pode "
                                        "ser regerado."}, code=403); return
                import mod_documentos as _mdoc
                import mod_contrato as _mc
                # corpo do modelo: versão CONGELADA do aditivo aberto; senão o ativo da loja;
                # sem ativo, SEED do modelo jurídico padrão (contrato_template/termo_aditivo.md)
                mv_ativa = None
                if aditivo is not None and aditivo.modelo_versao_id is not None:
                    corpo_md = _mdoc.corpo_da_versao(db, aditivo.modelo_versao_id) or ""
                else:
                    mv_ativa = _mdoc.ativo_de(db, loja_id, "termo_aditivo")
                    if mv_ativa is None:
                        corpo_padrao = _mc.corpo_modelo_aditivo_padrao()
                        if not corpo_padrao:
                            self.send_json({"ok": False, "erro": "Nenhum modelo de Termo Aditivo "
                                            "ativo — importe um em Config → Documentos."},
                                           code=400); return
                        if preview:
                            corpo_md = corpo_padrao        # preview não semeia nada
                        else:
                            mv_ativa = _mdoc.criar_versao(
                                db, loja_id, "termo_aditivo", corpo_padrao,
                                "termo_aditivo.md (modelo padrão do sistema)", usuario.get("id"))
                            _mdoc.ativar(db, mv_ativa.id)
                            corpo_md = corpo_padrao
                    else:
                        corpo_md = _mdoc.corpo_da_versao(db, mv_ativa.id) or ""
                if not preview and aditivo is None:
                    aditivo = Aditivo(projeto_nome=nome, contrato_id=contrato.id,
                                      orcamento_complemento_id=orc_aj.id, loja_id=loja_id)
                    db.add(aditivo); db.flush()
                if not preview and aditivo.modelo_versao_id is None:   # congela na 1ª geração
                    aditivo.modelo_versao_id = mv_ativa.id
                from mod_contrato import _formatar_valor as _fv
                calc = _aditivo_dados_calculo(db, nome, contrato, orc_aj)
                linhas_amb = calc["linhas_amb"]
                tot_orig, tot_novo, dif = (calc["tot_orig_marc"], calc["tot_novo_marc"],
                                           calc["dif"])
                defaults, _ = _aditivo_defaults_blocos(db, nome, contrato, orc_aj)
                blocos = {ch: (str(blocos_req.get(ch) or "").strip() or defaults[ch])
                          for ch in ("considerandos", "lista_integral", "inclusoes",
                                     "exclusoes", "valores")}
                n_ord = _aditivo_ordinal_atual(db, contrato, aditivo)
                dados = {"ambientes": linhas_amb, "valor_original": tot_orig,
                         "valor_novo": tot_novo, "diferenca": dif,
                         "num_contrato_original": contrato.num_contrato or "",
                         "ordinal": n_ord, "blocos": blocos}
                if not preview and not aditivo.num_aditivo:
                    from mod_contrato import gerar_num_contrato as _gnc
                    _existing = [x.num_aditivo for x in db.query(Aditivo)
                                 .filter(Aditivo.num_aditivo.isnot(None)).all()]
                    aditivo.num_aditivo = _gnc(_existing, "", prefixo="TA")
                _proj, cliente_dict, _od = _montar_dados_projeto_para_contrato(
                    nome, contrato.orcamento_id, db)
                loja_dict = _loja_dict_para_contrato(db, loja_id)
                usuario_ctx = {"nome": usuario.get("nome", ""),
                               "telefone": _get_usuario_telefone(usuario["id"], db),
                               "email": usuario.get("email", "") or ""}
                from mod_contrato import construir_contexto as _cc, gerar_pdf_aditivo as _gpa
                from mod_contrato import CONTRATOS_DIR as _CDIR
                # data em que o CONTRATO foi firmado = 1ª assinatura; fallback: geração
                _ass1 = (db.query(ContratoAssinatura).filter_by(contrato_id=contrato.id)
                           .order_by(ContratoAssinatura.assinado_em.asc()).first())
                _dt_ct = (_ass1.assinado_em if _ass1 is not None else None) or contrato.gerado_em
                num_ta = aditivo.num_aditivo if aditivo is not None else ""
                ctx = _cc(cliente_dict, usuario_ctx, "", loja_dict)
                ctx["num_contrato"] = num_ta
                ctx["_corpo_md_aditivo"] = corpo_md
                ctx["_aditivo"] = {
                    "num_aditivo": num_ta,
                    "num_contrato_original": contrato.num_contrato or "",
                    "ambientes_txt": "\n".join(
                        "%s: %s → %s (Δ %s)" % (l["ambiente"], _fv(l["vava_original"]),
                                                _fv(l["vava_novo"]), _fv(l["diferenca"]))
                        for l in linhas_amb),
                    "valor_original": _fv(tot_orig),
                    "valor_novo": _fv(tot_novo),
                    "diferenca": _fv(dif),
                    "ordinal": _mc.ordinal_aditivo(n_ord),
                    "data_aditivo": datetime.now().strftime("%d/%m/%Y"),
                    "data_contrato_original": _dt_ct.strftime("%d/%m/%Y") if _dt_ct else "",
                    **blocos,
                }
                if preview:
                    import tempfile, shutil as _shutil
                    outdir = tempfile.mkdtemp(prefix="aditivo_preview_")
                    try:
                        pdf_path = _gpa(ctx, os.path.join(outdir, "preview.pdf"))
                        with open(pdf_path, "rb") as fh:
                            data_pdf = fh.read()
                    finally:
                        _shutil.rmtree(outdir, ignore_errors=True)
                    db.rollback()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", 'inline; filename="aditivo_preview.pdf"')
                    self.send_header("Content-Length", len(data_pdf))
                    self.end_headers()
                    self.wfile.write(data_pdf)
                    return
                pdf_path = _gpa(ctx, os.path.join(_CDIR, "aditivo_%d.pdf" % aditivo.id))
                aditivo.pdf_path = pdf_path
                aditivo.dados_json = json.dumps(dados, ensure_ascii=False)
                aditivo.orcamento_complemento_id = orc_aj.id
                aditivo.gerado_em = datetime.utcnow()
                aditivo.gerado_por_id = usuario.get("id")
                aditivo.status = "para_assinatura"
                db.commit()
                self.send_json({"ok": True, "aditivo": _aditivo_dict(aditivo)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m_adass = re.match(r'^/api/projetos/([^/]+)/aditivo/assinar$', path)
        if m_adass:
            # Fatia 3 PE: assinatura interna do termo aditivo (loja + cliente), espelho do contrato.
            nome = unquote(m_adass.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                req = json.loads(body or b'{}')
                parte = (req.get("parte") or "").strip()
                nome_ass = (req.get("nome") or "").strip()
                cpf = (req.get("cpf") or "").strip()
                if parte not in ("loja", "cliente"):
                    self.send_json({"ok": False, "erro": "parte deve ser 'loja' ou 'cliente'"},
                                   code=400); return
                if not nome_ass or not cpf:
                    self.send_json({"ok": False, "erro": "Informe nome e CPF."}, code=400); return
                aditivo = (db.query(Aditivo).filter_by(projeto_nome=nome)
                             .order_by(Aditivo.id.desc()).first())
                if aditivo is None or not aditivo.pdf_path:
                    self.send_json({"ok": False, "erro": "Gere o termo aditivo antes de assinar."},
                                   code=400); return
                if aditivo.status == "assinado":
                    self.send_json({"ok": False, "erro": "Termo aditivo já assinado."}, code=400); return
                if any(a.parte == parte for a in aditivo.assinaturas):
                    self.send_json({"ok": False, "erro": "Esta parte já assinou."}, code=400); return
                # ALIAS obrigatório: import não-aliased tornaria calcular_hash_assinatura local
                # ao do_POST inteiro e quebraria o handler de assinatura do CONTRATO acima
                from mod_contrato import calcular_hash_assinatura as _cha
                ts = datetime.utcnow().isoformat()
                # append na RELAÇÃO (não db.add solto): a coleção já carregada precisa enxergar
                # a assinatura nova para o cálculo de "ambas as partes" logo abaixo
                aditivo.assinaturas.append(AditivoAssinatura(
                    parte=parte, nome=nome_ass, cpf=cpf, ip_origem=self.client_address[0],
                    hash_sha256=_cha(nome_ass, cpf, aditivo.id, ts)))
                db.flush()
                partes = {a.parte for a in aditivo.assinaturas}
                aditivo.status = ("assinado" if {"loja", "cliente"}.issubset(partes)
                                  else "assinado_" + parte)
                db.commit()
                self.send_json({"ok": True, "status": aditivo.status})
            finally:
                db.close()
            return

        m_apger = re.match(r'^/api/projetos/([^/]+)/aprovacao-pe$', path)
        if m_apger:
            # Correção Fatia 3: gera/regenera a APROVAÇÃO DO PROJETO EXECUTIVO — documento do
            # sistema (modelo por loja tipo 'aprovacao_pe', versão congelada na 1ª geração) que
            # registra os AMBIENTES APROVADOS (importa no desmembramento) e substitui o upload de
            # "PE Assinado". Imprimível; assinatura interna loja+cliente (integração de assinatura
            # digital = fase futura, mesmo placeholder do contrato).
            nome = unquote(m_apger.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                contrato = (db.query(Contrato).filter_by(projeto_nome=nome)
                              .order_by(Contrato.id.desc()).first())
                if contrato is None:
                    self.send_json({"ok": False, "erro": "Projeto sem contrato."}, code=400); return
                aprov = (db.query(AprovacaoPE).filter_by(projeto_nome=nome)
                           .order_by(AprovacaoPE.id.desc()).first())
                if aprov is not None and aprov.status == "assinado":
                    self.send_json({"ok": False, "erro": "Aprovação do PE já assinada — não pode "
                                    "ser regerada."}, code=403); return
                import mod_documentos as _mdoc
                if aprov is None:
                    aprov = AprovacaoPE(projeto_nome=nome, contrato_id=contrato.id, loja_id=loja_id)
                    db.add(aprov); db.flush()
                if aprov.modelo_versao_id is None:      # congela o modelo na 1ª geração
                    mv = _mdoc.ativo_de(db, loja_id, "aprovacao_pe")
                    if mv is None:
                        self.send_json({"ok": False, "erro": "Nenhum modelo de Aprovação de PE "
                                        "ativo — importe um em Config → Documentos."}, code=400); return
                    aprov.modelo_versao_id = mv.id
                corpo_md = _mdoc.corpo_da_versao(db, aprov.modelo_versao_id) or ""
                # ambientes aprovados = os do orçamento do CONTRATO (fase corrente do projeto)
                pa_nome = {pa.id: (pa.nome_exibicao or pa.nome) for pa in
                           db.query(PoolAmbiente).filter_by(projeto_id=nome).all()}
                ambs_aprov = [{"pool_ambiente_id": oa.pool_ambiente_id,
                               "ambiente": pa_nome.get(oa.pool_ambiente_id, "?")}
                              for oa in db.query(OrcamentoAmbiente)
                              .filter_by(orcamento_id=contrato.orcamento_id).all()]
                if not aprov.num_aprovacao:
                    from mod_contrato import gerar_num_contrato as _gnc2
                    _existing = [x.num_aprovacao for x in db.query(AprovacaoPE)
                                 .filter(AprovacaoPE.num_aprovacao.isnot(None)).all()]
                    aprov.num_aprovacao = _gnc2(_existing, "", prefixo="AP")
                _proj, cliente_dict, _od = _montar_dados_projeto_para_contrato(
                    nome, contrato.orcamento_id, db)
                loja_dict = _loja_dict_para_contrato(db, loja_id)
                usuario_ctx = {"nome": usuario.get("nome", ""),
                               "telefone": _get_usuario_telefone(usuario["id"], db),
                               "email": usuario.get("email", "") or ""}
                from mod_contrato import construir_contexto as _cc2, gerar_pdf_aprovacao_pe as _gpap
                from mod_contrato import CONTRATOS_DIR as _CDIR2
                ctx = _cc2(cliente_dict, usuario_ctx, "", loja_dict)
                ctx["num_contrato"] = aprov.num_aprovacao
                ctx["_corpo_md_aprovacao"] = corpo_md
                ctx["_aprovacao_pe"] = {
                    "num_aprovacao": aprov.num_aprovacao,
                    "ambientes_txt": "\n".join(a["ambiente"] for a in ambs_aprov),
                }
                pdf_path = _gpap(ctx, os.path.join(_CDIR2, "aprovacao_pe_%d.pdf" % aprov.id))
                aprov.pdf_path = pdf_path
                aprov.dados_json = json.dumps({"ambientes": ambs_aprov}, ensure_ascii=False)
                aprov.gerado_em = datetime.utcnow()
                aprov.gerado_por_id = usuario.get("id")
                aprov.status = "para_assinatura"
                db.commit()
                self.send_json({"ok": True, "aprovacao": _aprovacao_pe_dict(aprov)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m_apass = re.match(r'^/api/projetos/([^/]+)/aprovacao-pe/assinar$', path)
        if m_apass:
            # Correção Fatia 3: assinatura interna da Aprovação do PE (loja + cliente).
            nome = unquote(m_apass.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                req = json.loads(body or b'{}')
                parte = (req.get("parte") or "").strip()
                nome_ass = (req.get("nome") or "").strip()
                cpf = (req.get("cpf") or "").strip()
                if parte not in ("loja", "cliente"):
                    self.send_json({"ok": False, "erro": "parte deve ser 'loja' ou 'cliente'"},
                                   code=400); return
                if not nome_ass or not cpf:
                    self.send_json({"ok": False, "erro": "Informe nome e CPF."}, code=400); return
                aprov = (db.query(AprovacaoPE).filter_by(projeto_nome=nome)
                           .order_by(AprovacaoPE.id.desc()).first())
                if aprov is None or not aprov.pdf_path:
                    self.send_json({"ok": False, "erro": "Gere a aprovação do PE antes de assinar."},
                                   code=400); return
                if aprov.status == "assinado":
                    self.send_json({"ok": False, "erro": "Aprovação já assinada."}, code=400); return
                if any(a.parte == parte for a in aprov.assinaturas):
                    self.send_json({"ok": False, "erro": "Esta parte já assinou."}, code=400); return
                from mod_contrato import calcular_hash_assinatura as _cha2
                ts = datetime.utcnow().isoformat()
                aprov.assinaturas.append(AprovacaoPEAssinatura(
                    parte=parte, nome=nome_ass, cpf=cpf, ip_origem=self.client_address[0],
                    hash_sha256=_cha2(nome_ass, cpf, aprov.id, ts)))
                db.flush()
                partes = {a.parte for a in aprov.assinaturas}
                aprov.status = ("assinado" if {"loja", "cliente"}.issubset(partes)
                                else "assinado_" + parte)
                db.commit()
                self.send_json({"ok": True, "status": aprov.status})
            finally:
                db.close()
            return

        # ── Expedição (Modulos_Orizon_v5, módulo 7): CicloLogistico — criar/mover/editar ──
        if path == "/api/expedicao/cards":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "expedicao"):
                    self.send_json({"ok": False, "erro": "Módulo Expedição inativo."}, code=403); return
                req = json.loads(body or b'{}')
                projeto = (req.get("projeto_nome") or "").strip()
                if not projeto:
                    self.send_json({"ok": False, "erro": "Selecione o projeto."}, code=400); return
                if db.query(Projeto).filter_by(nome_safe=projeto, loja_id=lid).first() is None:
                    self.send_json({"ok": False, "erro": "Projeto não encontrado nesta loja."}, code=404); return
                card = mod_expedicao.criar_ciclo(db, lid, projeto, req.get("numero_pedido"),
                                                 req.get("prazos") or {}, usuario.get("id"))
                db.commit()
                self.send_json({"ok": True, "id": card.id}, code=201)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/expedicao/cards/(\d+)/mover$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                card = db.get(CicloLogistico, int(m.group(1)))
                if card is None or (lid and card.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                req = json.loads(body or b'{}')
                ok, err = mod_expedicao.mover(db, card, req.get("novo_status"),
                                              req.get("realizados") or {}, usuario.get("id"))
                if not ok:
                    self.send_json({"ok": False, "erro": err}, code=400); return
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/expedicao/cards/(\d+)$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                card = db.get(CicloLogistico, int(m.group(1)))
                if card is None or (lid and card.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                mod_expedicao.atualizar_detalhe(db, card, json.loads(body or b'{}'))
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Assistências (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6) ─────────────────
        if path == "/api/assistencias/casos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                loja = db.get(Loja, lid) if lid else None
                if loja is not None and not mod_tenancy.modulo_ativo(loja, "assistencias"):
                    self.send_json({"ok": False, "erro": "Módulo Assistências inativo."}, code=403); return
                req = json.loads(body or b'{}')
                projeto = (req.get("projeto_nome") or "").strip() or None
                if projeto and db.query(Projeto).filter_by(nome_safe=projeto, loja_id=lid).first() is None:
                    self.send_json({"ok": False, "erro": "Projeto não encontrado nesta loja."}, code=404); return
                caso = mod_assistencias.criar_caso(db, lid, projeto, req.get("sub_tipo"), req.get("motivo"),
                                                   req.get("descricao"), req.get("valor"), usuario.get("id"))
                db.commit()
                self.send_json({"ok": True, "id": caso.id, "tipo_custo": caso.tipo_custo}, code=201)
            except ValueError as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/assistencias/casos/(\d+)/realizar$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado."}, code=401); return
            import mod_contabil
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                caso = db.get(AssistenciaCaso, int(m.group(1)))
                if caso is None or (lid and caso.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado."}, code=404); return
                ot, oid = mod_contabil.resolver_owner(db, usuario)
                ok, err = mod_assistencias.realizar_caso(db, ot, oid, caso, (json.loads(body or b'{}')).get("valor"))
                if not ok:
                    self.send_json({"ok": False, "erro": err}, code=400); return
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Adiantamentos/Empréstimos: criar (Fase 5) ───────────────────────────────────
        if path == "/api/adiantamentos":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                r = json.loads(body or b'{}')
                fid = int(r.get("funcionario_id") or 0)
                if not db.query(Funcionario).filter_by(id=fid, loja_id=loja_id).first():
                    self.send_json({"ok": False, "erro": "Funcionário inválido"}, code=400); return
                a = AdiantamentoFuncionario(
                    loja_id=loja_id, funcionario_id=fid,
                    tipo=(r.get("tipo") or "adiantamento"), competencia=(r.get("competencia") or ""),
                    valor=float(r.get("valor") or 0.0), abater=(1 if r.get("abater", True) else 0),
                    competencia_abate=(r.get("competencia_abate") or r.get("competencia") or None),
                    observacao=(r.get("observacao") or None))
                db.add(a); db.commit()
                self.send_json({"ok": True, "id": a.id, "tipo": a.tipo, "valor": a.valor,
                                "abater": bool(a.abater)}, code=201)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Folha de Pagamento: gerar folha do período / pagar um registro ───────────────
        if path == "/api/folha/gerar":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                comp = ((json.loads(body or b'{}')).get("competencia") or "").strip()
                if not re.match(r'^\d{4}-\d{2}$', comp):
                    self.send_json({"ok": False, "erro": "Informe a competência AAAA-MM."}, code=400); return
                cfg = _cfg_financeira_loja(db, loja_id)
                mod_folha.gerar_folha(db, loja_id, comp, cfg)
                db.commit()
                self.send_json({"ok": True, "folha": mod_folha.listar(db, loja_id, comp)})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Folha: aprovar (aberta→aprovada) / reabrir (aprovada→aberta) ─────────────────
        m = re.match(r'^/api/folha/(\d+)/(aprovar|reabrir)$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                reg = db.query(FolhaPagamento).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                if reg is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ok, err = (mod_folha.aprovar(db, reg) if m.group(2) == "aprovar"
                           else mod_folha.reabrir(db, reg))
                if not ok:
                    self.send_json({"ok": False, "erro": err}, code=409); return
                db.commit()
                self.send_json({"ok": True, "status": reg.status})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        m = re.match(r'^/api/folha/(\d+)/pagar$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            import mod_contabil
            db = get_session()
            try:
                lid = usuario.get("loja_id")
                reg = db.get(FolhaPagamento, int(m.group(1)))
                if reg is None or (lid and reg.loja_id != lid):
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ot, oid = mod_contabil.resolver_owner(db, usuario)
                ok, err = mod_folha.pagar(db, ot, oid, reg)
                if not ok:
                    self.send_json({"ok": False, "erro": err}, code=400); return
                db.commit()
                self.send_json({"ok": True})
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── Cadastro (Modulos_Orizon_v9/v10): criar/editar Funcionário/Fornecedor/Terceiro/Função ──
        m = re.match(r'^/api/(funcionarios|fornecedores|terceiros|funcoes)(?:/(\d+))?$', path)
        if m:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                ent = m.group(1); rid = m.group(2)
                Model, ser, apl = _cad_ent(ent)
                req = json.loads(body or b'{}')
                if rid:
                    obj = db.query(Model).filter_by(id=int(rid), loja_id=loja_id).first()
                    if obj is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                else:
                    obj = Model(loja_id=loja_id); db.add(obj)
                if not ((req.get("nome") or "").strip() or (rid and obj.nome)):
                    self.send_json({"ok": False, "erro": "Nome é obrigatório."}, code=400); return
                apl(db, obj, req, loja_id)
                db.flush()
                if ent == "funcionarios":   # fronteira: sincroniza a conta de login vinculada
                    okc, errc = mod_cadastro.func_sync_acesso(db, obj, req)
                    if not okc:
                        db.rollback(); self.send_json({"ok": False, "erro": errc}, code=400); return
                db.commit()
                self.send_json({"ok": True, "id": obj.id, "item": ser(obj, db)}, code=(200 if rid else 201))
            except ValueError as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        if path == "/api/financeiro/contas":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                nova = mod_contabil.criar_conta(db, ot, oid, dd.get("pai_id"), dd.get("nome", ""))
                self.send_json({"ok": True, "conta": nova}, code=201)
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/sugerir-conta":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                self.send_json({"ok": True, "sugestao": mod_contabil.sugerir_conta(db, ot, oid, dd.get("texto", ""))})
            finally:
                db.close()
            return
        if path == "/api/financeiro/lancamentos":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                _ia = json.dumps(dd["ia_sugestao"]) if dd.get("ia_sugestao") else None
                lan = mod_contabil.lancar(
                    db, ot, oid,
                    conta_debito_id=dd.get("conta_debito_id"),
                    conta_credito_id=dd.get("conta_credito_id"),
                    valor=dd.get("valor"),
                    data=_parse_data(dd.get("data")),
                    projeto_id=dd.get("projeto_id"),
                    historico=dd.get("historico", ""),
                    ia_sugestao=_ia)
                self.send_json({"ok": True, "lancamento": lan}, code=201)
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except (ValueError, TypeError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/reconciliar":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                rec = mod_contabil.reconciliar(db, ot, oid, ini=_parse_data(dd.get("ini")),
                                               fim=_parse_data(dd.get("fim")),
                                               metodologia=dd.get("metodologia", "proporcional_receita"))
                self.send_json({"ok": True, "reconciliacao": rec})
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/efetivar-provisao":
            # FASE D: registra o custo REAL de uma provisão (2.1.04.x × 2.1.01, competência).
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                conta = (dd.get("conta") or "").strip()
                proj = (dd.get("projeto") or "").strip() or None
                ref = (dd.get("ref") or "").strip() or ("ef:%s:%s:%s" % (proj or "-", conta, uuid.uuid4().hex[:8]))
                lan = mod_contabil.efetivar_provisao(db, ot, oid, proj, conta, dd.get("valor"), ref=ref)
                db.commit()
                self.send_json({"ok": True, "lancamento": lan})
            except ValueError as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        m = re.match(r'^/api/projetos/([^/]+)/ciclo/21/conciliar$', path)
        if m:
            # FASE D2 — Conciliação Final (etapa 21): resolve todo saldo remanescente das provisões do
            # projeto (sobra→4.4.02 / falta→5.6.10) e ENCERRA o projeto (status "Concluído"). Gate financeiro.
            from urllib.parse import unquote as _unquote
            nome_safe = _unquote(m.group(1))
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                if _projeto_da_loja(db, nome_safe, usuario.get("loja_id")) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                # Desmembramento operacional (Fatia 4): a Conciliação Final "resolve à força" TODO saldo
                # das provisões — incluindo o de ambientes RETIDOS pela obra, cujo custo ainda não foi
                # efetivado. Fechar aqui reconheceria a provisão retida como sobra (receita 4.4.02) antes
                # da execução, e deixaria o ativo diferido 1.1.06 órfão. Bloqueia até liberar (mesma
                # regra do gate de execução por parcela).
                import mod_retido
                retidos = mod_retido.ambientes_retidos(db, nome_safe)
                if retidos:
                    self.send_json({"ok": False, "erro": "Há ambientes retidos pela obra (%d): libere-os "
                                    "antes da Conciliação Final." % len(retidos)}, code=409); return
                resolvido = mod_contabil.conciliar_final(db, ot, oid, nome_safe, ref_base="cf:" + nome_safe)
                _set_etapa_status(db, nome_safe, "21", "concluido", usuario.get("id"))
                db.commit()
                upsert_projeto_status(nome_safe, "concluido")   # status novo, distinto de "fechado" (sessão própria)
                self.send_json({"ok": True, "resolvido": resolvido, "status": "concluido"})
            except ValueError as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/resolver-saldo-provisao":
            # FASE D: fecha o saldo da provisão ao resultado (sobra→4.4.02 / falta→5.6.10). Idempotente.
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                conta = (dd.get("conta") or "").strip()
                proj = (dd.get("projeto") or "").strip() or None
                ref = "resolve:%s:%s" % (proj or "-", conta)
                lan = mod_contabil.resolver_saldo_provisao(db, ot, oid, proj, conta, ref=ref)
                db.commit()
                self.send_json({"ok": True, "lancamento": lan})
            except ValueError as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/pagar-fornecedor":
            # FASE D: paga a obrigação com fornecedor (2.1.01 × 1.1.01).
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                proj = (dd.get("projeto") or "").strip() or None
                valor = round(float(dd.get("valor") or 0), 2)
                if valor <= 0:
                    self.send_json({"ok": False, "erro": "Valor inválido."}, code=400); return
                ref = (dd.get("ref") or "").strip() or ("pgf:%s:%s" % (proj or "-", uuid.uuid4().hex[:8]))
                lan = mod_contabil.registrar_evento(db, ot, oid, "pagamento_fornecedor", valor, projeto_id=proj, ref=ref)
                db.commit()
                self.send_json({"ok": True, "lancamento": lan})
            except (ValueError, TypeError) as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/periodos":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                r = mod_contabil.fechar_periodo(db, ot, oid, ini=_parse_data(dd.get("ini")),
                                                fim=_parse_data(dd.get("fim")),
                                                metodologia=dd.get("metodologia", "proporcional_receita"))
                self.send_json({"ok": True, "periodo": r}, code=201)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/rateio-pdv":
            # Rateio ao PDV (spec PDV 2026-07-22 §3): mãe pagou custo em nome do PDV.
            # Par intercompany ref rateio:<n> — mãe DR 1.1.09 × CR 1.1.01; PDV DR 5.x × CR 2.1.09.
            # O ator age a partir da PRÓPRIA loja (mãe); a unidade destino vem no corpo.
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                pdv_id = dd.get("pdv_id")
                ator = _ator_dict(db, usuario)
                pdv = db.get(Loja, int(pdv_id)) if pdv_id else None
                if (pdv is None or not pdv.loja_mae_id
                        or pdv.id not in _lojas_do_escopo(db, ator)):
                    self.send_json({"ok": False, "erro": "Ponto de Venda fora do escopo."},
                                   code=403); return
                owner_pdv = mod_contabil.resolver_owner(db, {"loja_id": pdv.id, "rede_id": None})
                r = mod_contabil.rateio_ao_pdv(
                    db, (ot, oid), owner_pdv, dd.get("valor"), dd.get("conta_despesa"),
                    historico=dd.get("historico", ""), projeto_id=dd.get("projeto_id"),
                    data=_parse_data(dd.get("data")))
                self.send_json({"ok": True, **r}, code=201)
            except (ValueError, TypeError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/rateio-pdv/estorno":
            # Reversão EM PAR do rateio (ref espelhada) — restrita ao perímetro do ator.
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            from database import Lancamento
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                ref = (dd.get("ref") or "").strip()
                ator = _ator_dict(db, usuario)
                owners = set()
                for u in _lojas_do_escopo(db, ator):
                    owners.add(mod_contabil.resolver_owner(db, {"loja_id": u, "rede_id": None}))
                legs = db.query(Lancamento).filter_by(ref=ref).all()
                if not legs or not all((l.owner_tipo, l.owner_id) in owners for l in legs):
                    self.send_json({"ok": False, "erro": "Rateio fora do escopo."}, code=403); return
                r = mod_contabil.estornar_rateio(db, ref)
                self.send_json({"ok": True, **r})
            except (ValueError, TypeError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/api/financeiro/eventos":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b'{}')
                lan = mod_contabil.registrar_evento(
                    db, ot, oid, dd.get("tipo"), dd.get("valor"),
                    projeto_id=dd.get("projeto_id"), data=_parse_data(dd.get("data")),
                    historico=dd.get("historico", ""), motivo=dd.get("motivo"))
                self.send_json({"ok": True, "lancamento": lan}, code=201)
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except (ValueError, TypeError) as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        m_conta_rm = re.match(r"^/api/financeiro/contas/(\d+)/remover$", path)
        if m_conta_rm:
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                r = mod_contabil.remover_conta(db, ot, oid, int(m_conta_rm.group(1)))
                self.send_json({"ok": True, **r})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return
        if path == "/perfis":
            dados = json.loads(body)
            perfis_salvar(dados)
            self.send_json({"ok": True})

        elif path == "/perfis/ativo":
            dados = json.loads(body)
            cfg   = perfis_carregar()
            cfg["perfil_ativo"] = dados.get("perfil", "consultor")
            perfis_salvar(cfg)
            self.send_json({"ok": True, "perfil_ativo": cfg["perfil_ativo"]})

        elif path == "/carregar":
            ct               = self.headers.get("Content-Type", "")
            arquivos, campos = _parse_multipart(body, ct)
            if not arquivos:
                self.send_json({"ok": False, "erro": "Nenhum arquivo XML recebido"})
                return
            try:
                dados        = carregar_xmls(arquivos)
                nome_cliente = dados.get("cliente", {}).get("nome", "").strip()
                cpf          = dados.get("cliente", {}).get("cpf", "").strip()
                if not nome_cliente:
                    nome_cliente = re.sub(r"\.xml$", "", arquivos[0][0], flags=re.IGNORECASE).strip() or "PROJETO"
                session_set("dados_carregados", dados)
                session_set("xmls_carregados", arquivos)
                session_set("nome_cliente", nome_cliente)
                session_set("excel_atual_caminho", None)
                session_set("idx_negociacao", None)
                dados["nome_cliente"] = nome_cliente
                self.send_json(dados)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})

        elif path == "/calcular_aymore":
            req = json.loads(body)
            from mod_fin import calcular_aymore as _calc_ay
            resultado = _calc_ay(
                valor_avista  = float(req.get("valor_avista",  req.get("valor_venda", 0))),
                entrada       = float(req.get("entrada", 0)),
                n_parcelas    = int(req.get("n_parcelas", 8)),
                carencia_dias = int(req.get("carencia_dias", 30)),
                data_contrato = req.get("data_contrato", ""),
            )
            self.send_json(resultado)

        elif path == "/calcular_cartao":
            req = json.loads(body)
            from mod_fin import calcular_cartao as _calc_cc
            resultado = _calc_cc(
                valor_avista  = float(req.get("valor_avista",  req.get("valor_venda", 0))),
                entrada       = float(req.get("entrada", 0)),
                n_parcelas    = int(req.get("n_parcelas", 1)),
                data_contrato = req.get("data_contrato", ""),
                codigo        = req.get("codigo", "cartao_credito"),
            )
            self.send_json(resultado)

        elif path == "/calcular_venda_programada":
            req = json.loads(body)
            from mod_fin import calcular_venda_programada as _calc_vp
            resultado = _calc_vp(
                valor_avista   = float(req.get("valor_avista", 0)),
                entrada        = float(req.get("entrada", 0)),
                n_parcelas     = int(req.get("n_parcelas", 1)),
                data_contrato  = req.get("data_contrato", ""),
                datas_parcelas = req.get("datas_parcelas", []),
            )
            self.send_json(resultado)

        elif path == "/api/gerente/verificar":
            req   = json.loads(body)
            senha = req.get("senha", "")
            # Sessão-primeiro (2026-07-24): logado com 'autorizar' não redigita senha.
            _auto_ok = False
            if not senha:
                _u_sess = get_usuario_sessao(self)
                _auto_ok = bool(_u_sess and perfis.pode(_u_sess.get("nivel"), "autorizar"))
            _perfis_cfg = perfis_carregar()
            senha_correta = _perfis_cfg.get("perfis", {}).get("gerente", {}).get("senha_gerente", "1234")
            if _auto_ok or (senha and senha == senha_correta):
                taxa_cfg = None
                try:
                    import mod_fin.total_flex as _tf_mod
                    c = _tf_mod._cfg()
                    taxa_cfg = round(c["taxa_juros_mensal"] * 100, 4)
                except Exception:
                    pass
                self.send_json({"ok": True, "taxa_juros_pct": taxa_cfg})
            else:
                self.send_json({"ok": False, "erro": "Senha incorreta"})

        elif path == "/api/fin/total_flex/inicializar":
            req = json.loads(body)
            from mod_fin import tf_inicializar as _tf_ini
            taxa_ov = req.get("taxa_override")
            resultado = _tf_ini(
                valor_financiado = float(req.get("valor_financiado", 0)),
                n_parcelas       = int(req.get("n_parcelas", 2)),
                prazo_meses      = int(req.get("prazo_meses", 6)),
                data_contrato    = req.get("data_contrato", ""),
                taxa_override    = float(taxa_ov) / 100 if taxa_ov is not None else None,
            )
            self.send_json(resultado)

        elif path == "/api/fin/total_flex/recalcular":
            req = json.loads(body)
            from mod_fin import tf_recalcular as _tf_rec
            taxa_ov = req.get("taxa_override")
            resultado = _tf_rec(
                valor_financiado   = float(req.get("valor_financiado", 0)),
                data_contrato      = req.get("data_contrato", ""),
                prazo_maximo_meses = int(req.get("prazo_maximo_meses", 12)),
                parcelas_input     = req.get("parcelas", []),
                taxa_override      = float(taxa_ov) / 100 if taxa_ov is not None else None,
            )
            self.send_json(resultado)

        elif path == "/calcular_total_flex":
            req = json.loads(body)
            from mod_fin import calcular_total_flex as _calc_tf
            resultado = _calc_tf(
                valor_avista     = float(req.get("valor_avista", 0)),
                entrada          = float(req.get("entrada", 0)),
                n_parcelas       = int(req.get("n_parcelas", 2)),
                taxa_mensal_pct  = 0,
                data_contrato    = req.get("data_contrato", ""),
                valores_parcelas = req.get("valores_parcelas", []),
                datas_parcelas   = req.get("datas_parcelas",   []),
            )
            self.send_json(resultado)

        elif path == "/projetos/novo":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req = json.loads(body)
            nome_proj   = req.get('nome_projeto', '').strip()
            cliente_id  = req.get('cliente_id')
            parceiro_id = req.get('parceiro_id')
            if not nome_proj:
                self.send_json({'ok': False, 'erro': 'nome_projeto é obrigatório'})
                return
            if not cliente_id:
                self.send_json({'ok': False, 'erro': 'cliente_id é obrigatório — selecione ou cadastre um cliente'})
                return
            # Carrega dados do cliente do banco para garantir consistência + escopo de loja
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, int(cliente_id), loja_id)
                if not c:
                    self.send_json({'ok': False, 'erro': 'Cliente não encontrado'}, code=404)
                    return
                cli_nome     = c.nome
                cli_cpf      = c.cpf      or ''
                cli_email    = c.email    or ''
                cli_telefone = c.telefone or ''
            except Exception as e:
                self.send_json({'ok': False, 'erro': str(e)})
                return
            finally:
                db.close()
            try:
                proj = _criar_projeto(nome_proj, cli_nome, cli_cpf, cli_email, cli_telefone,
                                      cliente_id=int(cliente_id),
                                      parceiro_id=int(parceiro_id) if parceiro_id else None)

                # Cria Orçamento 1 automaticamente
                _usuario = get_usuario_sessao(self)
                _db_orc = get_session()
                try:
                    _pid = proj['nome_safe']
                    print("[ORC] criando Orcamento 1 para projeto_id=%r" % _pid)
                    _orc = Orcamento(
                        projeto_id=_pid,
                        nome="Orçamento 1",
                        ordem=1,
                        loja_id=loja_id,
                        created_by=_usuario['id'] if _usuario else None,
                    )
                    _db_orc.add(_orc)
                    _db_orc.commit()
                    _db_orc.refresh(_orc)
                    proj['orcamento_ativo_id'] = _orc.id
                    print("[ORC] commit OK — id=%d projeto_id=%r" % (_orc.id, _orc.projeto_id))
                    _salvar_projeto(proj)
                except Exception as _e_orc:
                    print("[ORC] ERRO ao criar orcamento: %s" % _e_orc)
                    raise
                finally:
                    _db_orc.close()

                # Link cliente_id no projetos_meta e marcar etapas 1 e 2 (Briefing fica pendente)
                _db_ciclo = get_session()
                try:
                    p_meta = _db_ciclo.get(Projeto, proj['nome_safe'])
                    if not p_meta:
                        p_meta = Projeto(nome_safe=proj['nome_safe'])
                        _db_ciclo.add(p_meta)
                        # Consultor responsável (criado_por_id, gravado só na criação): por padrão o
                        # usuário logado; gerente+ pode indicar outro consultor da loja.
                        criador = usuario.get("id") if usuario else None
                        cons_id = req.get("consultor_id")
                        if cons_id and not _ve_apenas_proprios_projetos(usuario.get("nivel")):
                            alvo = _db_ciclo.query(Usuario).filter_by(id=int(cons_id)).first()
                            if _usuario_pertence_a_loja(_db_ciclo, alvo, loja_id):
                                criador = int(cons_id)
                        p_meta.criado_por_id = criador
                    p_meta.cliente_id = int(cliente_id)
                    p_meta.loja_id = loja_id
                    _db_ciclo.commit()

                    agora = datetime.utcnow()
                    uid_ciclo = _usuario['id'] if _usuario else None
                    # Marca apenas Captação(1) e Criação do projeto(2). Briefing(3) fica
                    # pendente — vira a "etapa corrente" e deve ser preenchido (sub-projeto D).
                    for cod in ["1", "2"]:
                        etapa = _db_ciclo.query(CicloEtapa).filter_by(
                            projeto_nome=proj['nome_safe'], etapa_codigo=cod
                        ).first()
                        if not etapa:
                            etapa = CicloEtapa(
                                projeto_nome=proj['nome_safe'],
                                etapa_codigo=cod,
                                status="concluido",
                                concluido_em=agora,
                                responsavel_id=uid_ciclo,
                            )
                            _db_ciclo.add(etapa)
                        elif etapa.status != "concluido":
                            etapa.status         = "concluido"
                            etapa.concluido_em   = agora
                            etapa.responsavel_id = uid_ciclo
                    _db_ciclo.commit()
                except Exception as _e_ciclo:
                    print("[CICLO] Erro ao marcar etapas iniciais: %s" % _e_ciclo)
                finally:
                    _db_ciclo.close()

                session_set('projeto_ativo', proj['nome_safe'])
                self.send_json({'ok': True, 'projeto': proj})
            except Exception as e:
                self.send_json({'ok': False, 'erro': str(e)})

        elif path == "/api/clientes":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req  = json.loads(body) if body else {}
            faltando = validar_cadastro_minimo(req)
            if faltando:
                self.send_json({"ok": False,
                                "erro": "Campos obrigatórios faltando: " + ", ".join(faltando)})
                return
            nome = (req.get("nome") or "").strip()
            import validacao_doc
            for _val, _rot, _tipo in ((req.get("cpf"), "CPF", "cpf"),
                                      (req.get("cnpj"), "CNPJ", "cnpj")):
                _e = validacao_doc.erro_doc(_val, _rot, _tipo)
                if _e:
                    self.send_json({"ok": False, "erro": _e}, code=400)
                    return
            cpf = (req.get("cpf") or "").strip() or None
            db  = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if cpf:
                    existente = db.query(Cliente).filter_by(cpf=cpf).first()
                    if existente:
                        if getattr(existente, "loja_id", None) == loja_id:
                            self.send_json({"ok": False, "erro": "CPF já cadastrado",
                                            "cliente": _cliente_dict(existente)}, code=409)
                        else:
                            self.send_json({"ok": False,
                                            "erro": "CPF já cadastrado em outra unidade."}, code=409)
                        return
                tipo_dest = (req.get("tipo_dest") or "").strip() or "nao_contribuinte"
                c = Cliente(
                    nome       =nome, cpf=cpf,
                    loja_id    =loja_id,
                    tipo_dest         =tipo_dest,
                    cnpj              =(req.get("cnpj")               or "").strip() or None,
                    inscricao_estadual=(req.get("inscricao_estadual") or "").strip() or None,
                    email      =(req.get("email")       or "").strip() or None,
                    telefone   =(req.get("telefone")    or "").strip() or None,
                    whatsapp   =(req.get("whatsapp")    or "").strip() or None,
                    cep        =(req.get("cep")         or "").strip() or None,
                    logradouro =(req.get("logradouro")  or "").strip() or None,
                    numero     =(req.get("numero")      or "").strip() or None,
                    complemento=(req.get("complemento") or "").strip() or None,
                    bairro     =(req.get("bairro")      or "").strip() or None,
                    cidade     =(req.get("cidade")      or "").strip() or None,
                    estado     =(req.get("estado")      or "").strip() or None,
                    municipio_ibge=(req.get("municipio_ibge") or "").strip() or None,
                    observacoes=(req.get("observacoes") or "").strip() or None,
                )
                db.add(c)
                db.commit()
                db.refresh(c)
                self.send_json({"ok": True, "cliente": _cliente_dict(c)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        m_bp = re.match(r"^/api/projetos/([^/]+)/briefing$", path)
        if m_bp:
            nome_safe = unquote(m_bp.group(1))
            usuario   = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req       = json.loads(body) if body else {}
            db        = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                cliente_id = p_meta.cliente_id if p_meta else None
                if not cliente_id:
                    self.send_json({"ok": False, "erro": "Projeto sem cliente vinculado"})
                    return
                b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    b = Briefing(
                        cliente_id=cliente_id,
                        projeto_nome=nome_safe,
                        data_atendimento=datetime.utcnow(),
                        tipo_imovel="",
                        budget_declarado=0.0,
                        categoria_proposta="",
                        data_entrega_desejada="",
                        flexibilidade_prazo="",
                    )
                    db.add(b)
                for campo in ["tipo_imovel", "categoria_proposta",
                               "data_entrega_desejada", "flexibilidade_prazo"]:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if "budget_declarado" in req:
                    b.budget_declarado = float(req["budget_declarado"] or 0)
                opcionais = [
                    "condicao_imovel", "metragem_m2", "num_ambientes",
                    "ambientes_prioritarios", "tem_arquiteto", "nome_arquiteto",
                    "tem_gerente_obra", "end_empreendimento", "estilo_decisao",
                    "estilo_vida", "relacao_projeto", "decisor", "referencias_visuais",
                    "obs_referencias", "experiencia_anterior", "obs_experiencia",
                    "tem_budget", "forma_pagamento_pref", "data_entrega_limite",
                    "motivo_prazo", "nao_abre_mao", "restricoes", "obs_livres",
                ]
                for campo in opcionais:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if usuario:
                    b.consultor_id = usuario["id"]
                b.atualizado_em = datetime.utcnow()
                db.commit()
                db.refresh(b)
                bd = _briefing_dict(b)
                if bd["completo"]:
                    etapa3 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="3"
                    ).first()
                    if not etapa3:
                        etapa3 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="3")
                        db.add(etapa3)
                    etapa3.status        = "concluido"
                    etapa3.concluido_em  = datetime.utcnow()
                    etapa3.responsavel_id = usuario["id"] if usuario else None
                    db.commit()
                self.send_json({"ok": True, "briefing": bd})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        m_bf = re.match(r"^/api/clientes/(\d+)/briefing$", path)
        if m_bf:
            cliente_id = int(m_bf.group(1))
            usuario    = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req        = json.loads(body) if body else {}
            db         = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, cliente_id, loja_id)
                if c is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                b = db.query(Briefing).filter_by(cliente_id=cliente_id)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    b = Briefing(
                        cliente_id=cliente_id,
                        data_atendimento=datetime.utcnow(),
                        tipo_imovel="",
                        budget_declarado=0.0,
                        categoria_proposta="",
                        data_entrega_desejada="",
                        flexibilidade_prazo="",
                    )
                    db.add(b)
                for campo in ["tipo_imovel", "categoria_proposta",
                               "data_entrega_desejada", "flexibilidade_prazo"]:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if "budget_declarado" in req:
                    b.budget_declarado = float(req["budget_declarado"] or 0)
                opcionais = [
                    "condicao_imovel", "metragem_m2", "num_ambientes",
                    "ambientes_prioritarios", "tem_arquiteto", "nome_arquiteto",
                    "tem_gerente_obra", "end_empreendimento", "estilo_decisao",
                    "estilo_vida", "relacao_projeto", "decisor", "referencias_visuais",
                    "obs_referencias", "experiencia_anterior", "obs_experiencia",
                    "tem_budget", "forma_pagamento_pref", "data_entrega_limite",
                    "motivo_prazo", "nao_abre_mao", "restricoes", "obs_livres",
                ]
                for campo in opcionais:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if usuario:
                    b.consultor_id = usuario["id"]
                b.atualizado_em = datetime.utcnow()
                db.commit()
                db.refresh(b)
                bd = _briefing_dict(b)
                self.send_json({"ok": True, "briefing": bd})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        elif re.match(r"^/api/clientes/(\d+)/editar$", path):
            m_cli = re.match(r"^/api/clientes/(\d+)/editar$", path)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req   = json.loads(body) if body else {}
            db    = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                c = _obj_da_loja(db, Cliente, int(m_cli.group(1)), loja_id)
                if not c:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                import validacao_doc
                for _val, _rot, _tipo in ((req.get("cpf"), "CPF", "cpf"),
                                          (req.get("cnpj"), "CNPJ", "cnpj")):
                    _e = validacao_doc.erro_doc(_val, _rot, _tipo)
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
                        return
                campos = ["nome","cpf","cnpj","inscricao_estadual",
                          "email","telefone","whatsapp",
                          "cep","logradouro","numero","complemento",
                          "bairro","cidade","estado","municipio_ibge","observacoes",
                          "inst_logradouro","inst_numero","inst_complemento",
                          "inst_bairro","inst_cidade","inst_cep","inst_uf"]
                for f in campos:
                    if f in req:
                        setattr(c, f, (req[f] or "").strip() or None)
                if "tipo_dest" in req:
                    c.tipo_dest = (req["tipo_dest"] or "").strip() or "nao_contribuinte"
                if "inst_mesmo_residencial" in req:
                    c.inst_mesmo_residencial = 1 if req["inst_mesmo_residencial"] else 0
                if "nome" in req and not c.nome:
                    self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                    return
                from datetime import datetime as _dt
                c.atualizado_em = _dt.utcnow()
                db.commit()
                db.refresh(c)
                self.send_json({"ok": True, "cliente": _cliente_dict(c)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        elif path == "/api/parceiros":
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req  = json.loads(body) if body else {}
            nome = (req.get("nome") or "").strip()
            if not nome:
                self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                return
            import validacao_doc
            _e = validacao_doc.erro_doc(req.get("cpf_cnpj"), "CPF/CNPJ")
            if _e:
                self.send_json({"ok": False, "erro": _e}, code=400)
                return
            db = get_session()
            try:
                p = Parceiro(
                    nome                =nome,
                    cpf_cnpj            =(req.get("cpf_cnpj")            or "").strip() or None,
                    tipo                =(req.get("tipo")                 or "").strip() or None,
                    email               =(req.get("email")                or "").strip() or None,
                    telefone            =(req.get("telefone")             or "").strip() or None,
                    whatsapp            =(req.get("whatsapp")             or "").strip() or None,
                    comissao_padrao_pct =float(req.get("comissao_padrao_pct") or 0),
                    observacoes         =(req.get("observacoes")          or "").strip() or None,
                    pix                 =(req.get("pix")                   or "").strip() or None,
                )
                db.add(p)
                db.flush()        # atribui p.id sem efetivar — transação única e atômica
                # Sempre aplica abrangência (default 'loja' → loja ativa do ator): garante
                # que o parceiro nunca nasça órfão/invisível para quem o cadastrou.
                ator = (_ator_dict(db, usuario) if usuario
                        else {"nivel": "", "loja_id": None, "rede_id": None, "active_loja_id": None})
                erros = _aplicar_abrangencia_parceiro(db, p, req, ator)
                if erros:
                    db.rollback()    # desfaz tudo, inclusive o INSERT do parceiro
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        elif re.match(r"^/api/parceiros/(\d+)/editar$", path):
            m_par = re.match(r"^/api/parceiros/(\d+)/editar$", path)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req   = json.loads(body) if body else {}
            db    = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                p = db.get(Parceiro, int(m_par.group(1)))
                if p is None or not _parceiro_visivel_loja(db, p, loja_id):
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if "cpf_cnpj" in req:
                    import validacao_doc
                    _e = validacao_doc.erro_doc(req.get("cpf_cnpj"), "CPF/CNPJ")
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
                        return
                for f in ["nome","cpf_cnpj","tipo","email","telefone","whatsapp","observacoes","pix"]:
                    if f in req:
                        setattr(p, f, (req[f] or "").strip() or None)
                if "comissao_padrao_pct" in req:
                    p.comissao_padrao_pct = float(req["comissao_padrao_pct"] or 0)
                if "nome" in req and not p.nome:
                    self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                    return
                if "abrangencia" in req:
                    erros = _aplicar_abrangencia_parceiro(db, p, req, ator)
                    if erros:
                        db.rollback()
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()

        elif re.match(r"^/api/projetos/([^/]+)/parametros$", path):
            m_par = re.match(r"^/api/projetos/([^/]+)/parametros$", path)
            nome_safe = unquote(m_par.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                from mod_orcamento_params import merge_parametros
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                p = _projeto_da_loja(db, nome_safe, loja_id)
                if p is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _projeto_esta_bloqueado(nome_safe):
                    self.send_json({"ok": False, "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."}, code=400)
                    return
                if _contrato_assinado(nome_safe, db):
                    self.send_json({"ok": False, "erro": "Contrato assinado — alterações não permitidas."}, code=403)
                    return
                atual = json.loads(p.parametros_json) if p.parametros_json else {}
                # Override de segmentação Mercadoria × Serviço: só o Diretor (aprovar_financeiro),
                # valida soma=100. merge_parametros ignora chaves fora do PARAMETROS_DEFAULT, então a
                # segmentação é tratada e persistida à parte (preservando override anterior).
                if "pct_mercadoria" in req or "pct_servico" in req:
                    if not perfis.pode(ator.get("nivel"), "aprovar_financeiro"):
                        self.send_json({"ok": False,
                                        "erro": "Apenas o Diretor pode alterar a segmentação Mercadoria × Serviço."},
                                       code=403)
                        return
                    from mod_orcamento_params import validar_segmentacao
                    pm = req.get("pct_mercadoria", atual.get("pct_mercadoria"))
                    ps = req.get("pct_servico", atual.get("pct_servico"))
                    try:
                        if pm is None or ps is None:
                            raise ValueError("Informe Mercadoria e Serviço juntos.")
                        validar_segmentacao(pm, ps)
                    except ValueError as _ve:
                        self.send_json({"ok": False, "erro": str(_ve)}, code=400)
                        return
                novos = merge_parametros(atual, req)
                for _k in ("pct_mercadoria", "pct_servico"):
                    if _k in req:      novos[_k] = float(req[_k])
                    elif _k in atual:  novos[_k] = atual[_k]
                p.parametros_json = json.dumps(novos, ensure_ascii=False)
                db.commit()
                proj_orcs = db.query(Orcamento).filter_by(projeto_id=nome_safe).all()
                for o in proj_orcs:
                    try: _recalcular_orcamento(o, db)
                    except Exception as _e: print("[FAXINA] recalc parametros:", _e)
                db.commit()
                brk = _negociacao_breakdown(proj_orcs[0], db) if proj_orcs else None
                self.send_json({"ok": True, "parametros": novos, "sombra": brk})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif re.match(r"^/api/orcamentos/(\d+)/margens$", path):
            # ── POST /api/orcamentos/<id>/margens — salva margens do orçamento ─────
            m_orc_mar = re.match(r"^/api/orcamentos/(\d+)/margens$", path)
            oid = int(m_orc_mar.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                _bc = _bloqueio_comercial(ator)      # visão do papel (§3): operacional não vê comercial
                if _bc:
                    self.send_json({"ok": False, "erro": _bc}, code=403); return
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                # Orçamento de AJUSTE (Fatia 3 PE) é isento das travas de aprovação/assinatura —
                # contratar o complemento pós-contrato é a razão de ele existir (11e Negociar Complemento).
                if not getattr(orc, "complemento_pe", 0):
                    if _projeto_esta_bloqueado(orc.projeto_id):
                        self.send_json({"ok": False,
                                        "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."},
                                       code=400)
                        return
                    if _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                if "desconto_pct" in req:
                    orc.desconto_pct = float(req["desconto_pct"])
                db.commit()
                try:
                    _recalcular_orcamento(orc, db)
                    db.commit()
                    self.send_json({"ok": True, "desconto_pct": orc.desconto_pct or 0.0,
                                    "sombra": _negociacao_breakdown(orc, db)})
                except Exception as _e:
                    db.rollback()
                    print("[CUTOVER] falha ao recalcular orçamento:", _e)
                    self.send_json({"ok": True, "desconto_pct": orc.desconto_pct or 0.0,
                                    "sombra": None, "erro_sombra": str(_e)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif re.match(r"^/api/orcamentos/(\d+)/negociacao-preview$", path):
            # ── POST /api/orcamentos/<id>/negociacao-preview — preview do motor (sem gravar) ──
            m_prev = re.match(r"^/api/orcamentos/(\d+)/negociacao-preview$", path)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                _bc = _bloqueio_comercial(ator)      # visão do papel (§3): operacional não vê comercial
                if _bc:
                    self.send_json({"ok": False, "erro": _bc}, code=403); return
                orc = _obj_da_loja(db, Orcamento, int(m_prev.group(1)), loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                d = _negociacao_breakdown(orc, db)
                self.send_json({"ok": True, "sombra": d, "ambientes": d.get("ambientes", [])})
            finally:
                db.close()
            return

        elif re.match(r"^/api/orcamentos/(\d+)/provisoes/(rev1|rev2)$", path):
            # ── POST /api/orcamentos/<id>/provisoes/<rev1|rev2> — Concorda/Revisa ──
            import mod_provisoes as _mprov
            m_prov = re.match(r"^/api/orcamentos/(\d+)/provisoes/(rev1|rev2)$", path)
            oid = int(m_prov.group(1)); versao = m_prov.group(2)
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"), sessao=usuario)
                if not aprovador:
                    self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                anterior_versao = "venda" if versao == "rev1" else "rev1"
                anterior = db.query(ProvisaoRegistro).filter_by(
                    orcamento_id=oid, versao=anterior_versao).first()
                if not anterior:
                    self.send_json({"ok": False,
                        "erro": "Registre a versão anterior primeiro (%s)." % anterior_versao},
                        code=409); return
                decisao = (req.get("decisao") or "").strip()
                if decisao == "concorda":
                    itens = json.loads(anterior.itens_json)
                    cfo, vl = anterior.cfo, anterior.val_liq
                elif decisao == "revisa":
                    try:
                        itens = {k: max(0.0, float(v or 0)) for k, v in (req.get("itens") or {}).items()}
                    except (TypeError, ValueError):
                        self.send_json({"ok": False, "erro": "Valores de itens inválidos"}, code=400); return
                    cfo, vl = anterior.cfo, anterior.val_liq   # base congelada (versão anterior: venda p/ rev1, rev1 p/ rev2)
                else:
                    self.send_json({"ok": False, "erro": "decisao deve ser concorda|revisa"}, code=400); return
                cust_var, marg = _mprov.cust_var_marg_cont(cfo, vl, itens)
                existente = db.query(ProvisaoRegistro).filter_by(orcamento_id=oid, versao=versao).first()
                pode_autorizar = perfis.pode(aprovador.nivel, "autorizar")   # capacidade de step-up (Diretor)
                # Fatia C: a revisão é REEDITÁVEL pelo aprovador financeiro ATÉ a ETAPA de AF ser aprovada
                # (rev1↔etapa 8, rev2↔etapa 11d). Depois de aprovada, reabrir exige Diretor (step-up).
                import mod_ciclo as _mcic
                _etapa_af = {"rev1": "8", "rev2": "11d"}.get(versao)
                _etc = (db.query(CicloEtapa).filter_by(projeto_nome=orc.projeto_id, etapa_codigo=_etapa_af).first()
                        if _etapa_af else None)
                if _etc is not None and _etc.status in _mcic.STATUS_CONCLUSIVOS and not pode_autorizar:
                    self.send_json({"ok": False,
                        "erro": "Etapa de AF já aprovada — reabrir a revisão exige Diretor."}, code=403); return
                # Fatia C (#10): aumento de custo acima do limite (config) exige step-up do Diretor
                import mod_parcelas as _mpar
                _loja = db.get(Loja, loja_id) if loja_id else None
                _cfg = {}
                if _loja and _loja.config_financeira_json:
                    try: _cfg = json.loads(_loja.config_financeira_json)
                    except Exception: _cfg = {}
                _af = (_cfg.get("aprovacao_financeira") or {})
                _lim_pct = float(_af.get("limite_af1_pct", 1.0) if versao == "rev1" else _af.get("limite_af2_pct", 2.0))
                if _mpar.exige_aprovacao_diretor(anterior.cust_var, cust_var, _lim_pct / 100.0) and not pode_autorizar:
                    self.send_json({"ok": False,
                        "erro": "Aumento de custo acima do limite (%.2f%%) — exige aprovação do Diretor." % _lim_pct}, code=403); return
                if existente:
                    db.delete(existente); db.flush()
                db.add(ProvisaoRegistro(orcamento_id=oid, versao=versao,
                    itens_json=json.dumps(itens, ensure_ascii=False),
                    cfo=cfo, val_liq=vl, cust_var=cust_var, marg_cont=marg,
                    decisao=decisao, por_id=aprovador.id, travada_em=datetime.utcnow()))
                db.flush()
                # Fatia C (#11): ajusta o razão (ativo × provisão, nunca DRE) p/ os valores aprovados
                import mod_contabil as _mc
                ot_af, own_af = _mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                _seq = int(getattr(orc, "ramo_financeiro_seq", 0) or 0) + 1
                _mc.disparar_deltas_af(db, ot_af, own_af, orc.projeto_id, itens,
                                       ref_base="af:%s:%s:%d" % (orc.projeto_id, versao, _seq))
                orc.ramo_financeiro_seq = _seq
                db.commit()
                self.send_json({"ok": True, "travada": True})
            finally:
                db.close()
            return

        elif re.match(r"^/api/orcamentos/(\d+)/ramo-financeiro$", path):
            # ── POST /api/orcamentos/<id>/ramo-financeiro — box loja×antecipação×financeira (Fatia B.2) ──
            import mod_contabil as _mc
            m_rf = re.match(r"^/api/orcamentos/(\d+)/ramo-financeiro$", path)
            oid = int(m_rf.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            ramo_novo = (req.get("ramo") or "").strip()
            if ramo_novo not in ("loja", "loja_antecipacao", "financeira"):
                self.send_json({"ok": False, "erro": "ramo inválido"}, code=400); return
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"), sessao=usuario)
                if not aprovador:
                    self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ramo_atual = _ramo_financeiro_efetivo(orc)
                cust_fin = _cust_fin_orc(orc)
                if ramo_novo != ramo_atual and cust_fin > 0:
                    ot, own_id = _mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                    seq = int(getattr(orc, "ramo_financeiro_seq", 0) or 0) + 1
                    _mc.trocar_ramo_custo_financeiro(db, ot, own_id, orc.projeto_id, ramo_atual, ramo_novo,
                                                     cust_fin, ref_base="ramofin:%s:%d" % (orc.projeto_id, seq))
                    orc.ramo_financeiro_seq = seq
                orc.ramo_financeiro = ramo_novo
                db.commit()
                self.send_json({"ok": True, "ramo": ramo_novo, "cust_fin": cust_fin})
            finally:
                db.close()
            return

        elif re.match(r"^/api/orcamentos/(\d+)/antecipacao$", path):
            # ── POST /api/orcamentos/<id>/antecipacao — reconhece o custo REAL da antecipação bancária (Fatia B) ──
            import mod_contabil as _mc
            m_an = re.match(r"^/api/orcamentos/(\d+)/antecipacao$", path)
            oid = int(m_an.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            try:
                valor = round(float(req.get("valor") or 0), 2)
            except (TypeError, ValueError):
                self.send_json({"ok": False, "erro": "Valor inválido"}, code=400); return
            if valor <= 0:
                self.send_json({"ok": False, "erro": "Informe o custo real (> 0)"}, code=400); return
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"), sessao=usuario)
                if not aprovador:
                    self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ramo = _ramo_financeiro_efetivo(orc)
                if ramo not in ("loja_antecipacao", "financeira"):
                    self.send_json({"ok": False, "erro": "Só no ramo antecipação/financeira (atual: %s)" % ramo}, code=400); return
                ot, own_id = _mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                seq = int(getattr(orc, "ramo_financeiro_seq", 0) or 0) + 1
                lan = _mc.reconhecer_custo_financeiro(db, ot, own_id, orc.projeto_id, ramo, valor,
                                                      ref="antecip:%s:%d" % (orc.projeto_id, seq))
                orc.ramo_financeiro_seq = seq
                db.commit()
                self.send_json({"ok": True, "reconhecido": bool(lan)})
            finally:
                db.close()
            return

        elif re.match(r"^/api/orcamentos/(\d+)/receita-financeira$", path):
            # ── POST /api/orcamentos/<id>/receita-financeira — ramo loja: apropria juros de parcela recebida ──
            import mod_contabil as _mc
            m_rl = re.match(r"^/api/orcamentos/(\d+)/receita-financeira$", path)
            oid = int(m_rl.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            try:
                valor = round(float(req.get("valor") or 0), 2)
            except (TypeError, ValueError):
                self.send_json({"ok": False, "erro": "Valor inválido"}, code=400); return
            if valor <= 0:
                self.send_json({"ok": False, "erro": "Informe o valor recebido (> 0)"}, code=400); return
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"), sessao=usuario)
                if not aprovador:
                    self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if _ramo_financeiro_efetivo(orc) != "loja":
                    self.send_json({"ok": False, "erro": "Só no ramo loja (financiamento direto)"}, code=400); return
                ot, own_id = _mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                seq = int(getattr(orc, "ramo_financeiro_seq", 0) or 0) + 1
                mv = _mc.apropriar_juros_loja(db, ot, own_id, orc.projeto_id, valor,
                                              ref_base="jloja:%s:%d" % (orc.projeto_id, seq))
                orc.ramo_financeiro_seq = seq
                db.commit()
                self.send_json({"ok": True, "apropriado": mv or 0.0})
            finally:
                db.close()
            return

        elif re.match(r"^/api/orcamentos/(\d+)/devolucao$", path):
            # ── POST /api/orcamentos/<id>/devolucao — devolução (parcial/total) da venda (Fatia D) ──
            import mod_contabil as _mc
            m_dv = re.match(r"^/api/orcamentos/(\d+)/devolucao$", path)
            oid = int(m_dv.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            try:
                fracao = round(float(req.get("fracao") or 0), 6)
            except (TypeError, ValueError):
                self.send_json({"ok": False, "erro": "Fração inválida"}, code=400); return
            if not (0 < fracao <= 1):
                self.send_json({"ok": False, "erro": "Fração deve estar entre 0 e 1 (ex.: 0.5 = 50%)"}, code=400); return
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"), sessao=usuario)
                if not aprovador:
                    self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ot, own_id = _mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                seq = int(getattr(orc, "ramo_financeiro_seq", 0) or 0) + 1
                _ref_dev = "dev:%s:%d" % (orc.projeto_id, seq)
                out = _mc.devolver_venda(db, ot, own_id, orc.projeto_id, fracao, ref_base=_ref_dev)
                # Ajustes Excepcionais (spec): devolve saldo aos acordos na fração devolvida
                out_ajx = _reverter_aplicacoes_fabrica(db, ot, own_id, orc.projeto_id, fracao, _ref_dev)
                orc.ramo_financeiro_seq = seq
                db.commit()
                self.send_json({"ok": True, "revertido": out, "ajustes_revertidos": out_ajx})
            finally:
                db.close()
            return

        elif re.match(r"^/api/orcamentos/(\d+)/cancelamento$", path):
            # ── POST /api/orcamentos/<id>/cancelamento — cancelamento de contrato (estorno TOTAL). ──
            # Gate DIRETOR (autorizar). Bloqueado após a NF-e (etapa 15). Reverte TODA a constituição do
            # contrato (cancelar_contrato) e trava o projeto como "cancelado" (opção B — revender = novo
            # projeto). Reembolso físico de valores recebidos → Tesouraria (módulo futuro).
            import mod_contabil as _mc
            import mod_ciclo as _mcic
            m_cc = re.match(r"^/api/orcamentos/(\d+)/cancelamento$", path)
            oid = int(m_cc.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"), sessao=usuario)
                if not aprovador or not perfis.pode(aprovador.nivel, "autorizar"):
                    self.send_json({"ok": False, "erro": "Cancelamento de contrato exige senha de Diretor"}, code=403); return
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                nome_safe = orc.projeto_id
                et15 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="15").first()
                if et15 and et15.status in _mcic.STATUS_CONCLUSIVOS:
                    self.send_json({"ok": False,
                        "erro": "NF-e já emitida — cancelamento de contrato indisponível (exige cancelamento fiscal)"}, code=409); return
                ot, own_id = _mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
                out = _mc.cancelar_contrato(db, ot, own_id, nome_safe, ref_base="cancel:%s" % nome_safe)
                db.commit()                                     # commit os estornos ANTES (libera o lock do SQLite)
                upsert_projeto_status(nome_safe, "cancelado")   # sessão própria (thread-safe), como no conciliar_final
                self.send_json({"ok": True, "revertido": out, "status": "cancelado"})
            finally:
                db.close()
            return

        elif re.match(r"^/api/projetos/([^/]+)/equipe$", path):
            # ── POST /api/projetos/<nome>/equipe — grava a seleção de um papel SELETOR da Equipe
            # (medidor/finalizador/montagem). Body: {papel, selecao}. Automáticos não são graváveis. ──
            from urllib.parse import unquote as _unq
            import mod_equipe as _meq, mod_tenancy as _mten
            m_eqp = re.match(r"^/api/projetos/([^/]+)/equipe$", path)
            nome_safe = _unq(m_eqp.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = _mten.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                ok, erro = _meq.salvar(db, nome_safe, (req.get("papel") or "").strip(),
                                       req.get("selecao"), loja_id=loja_id)
                if not ok:
                    self.send_json({"ok": False, "erro": erro}, code=400); return
                db.commit()
                self.send_json({"ok": True, "equipe": _meq.equipe(db, nome_safe, loja_id)})
            finally:
                db.close()
            return

        elif re.match(r"^/api/projetos/([^/]+)/data-entrega$", path):
            # ── POST /api/projetos/<nome>/data-entrega — persiste expectativa de entrega + previsão de
            # medição + venda programada e valida a FOLGA do trecho medição→entrega. folga<0 só grava com
            # reautenticação Gerente+ (auditada). Base do monitoramento e do gate da assinatura. ──
            from urllib.parse import unquote as _unq
            import mod_cronograma as _mcr, mod_tenancy as _mten
            m_de = re.match(r"^/api/projetos/([^/]+)/data-entrega$", path)
            nome_safe = _unq(m_de.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            data_entrega = _parse_data(req.get("data_entrega"))
            previsao_medicao = _parse_data(req.get("previsao_medicao"))
            if not data_entrega:
                self.send_json({"ok": False, "erro": "Informe a data de entrega esperada (AAAA-MM-DD)."}, code=400); return
            if not previsao_medicao:
                self.send_json({"ok": False, "erro": "Informe a previsão de medição (AAAA-MM-DD)."}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = _mten.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                cfg = _cfg_financeira_loja(db, loja_id)
                folga = _mcr.folga_medicao_entrega(cfg, previsao_medicao, data_entrega)
                cabe = folga >= 0
                override_ok = False
                if not cabe:
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    quer_override = bool(login or senha or req.get("override"))
                    if quer_override:   # sessão-primeiro; credenciais de terceiro seguem valendo
                        autorizador = _usuario_com_capacidade(db, login, senha, "autorizar", sessao=usuario)
                        if not autorizador:
                            self.send_json({"ok": False, "erro": "Credenciais inválidas ou perfil sem permissão (Gerente/Diretor)"}, code=403); return
                        override_ok = True
                        db.add(LogAcaoGerencial(
                            solicitante_id=usuario["id"], autorizador_id=autorizador.id,
                            acao="data_entrega_sem_folga", projeto_nome=nome_safe,
                            contexto=json.dumps({
                                "data_entrega": data_entrega.isoformat(),
                                "previsao_medicao": previsao_medicao.isoformat(),
                                "folga": folga})))
                    if not override_ok:
                        self.send_json({"ok": True, "cabe": False, "folga_min": folga, "requer_autorizacao": True}); return
                proj = db.get(Projeto, nome_safe)
                proj.data_entrega = data_entrega
                proj.previsao_medicao = previsao_medicao
                proj.folga_autorizada = 0 if cabe else 1   # 1 = gravada sob autorização gerencial (folga negativa)
                if "venda_programada" in req:
                    proj.venda_programada = 1 if req.get("venda_programada") else 0
                if not proj.data_inicio:
                    proj.data_inicio = datetime.utcnow()   # âncora do progressivo
                db.commit()
                self.send_json({"ok": True, "cabe": cabe, "folga_min": folga})
            except Exception as _e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(_e)}, code=500)
            finally:
                db.close()
            return

        else:
            import re as _re

            # ── POST /projetos/<nome_safe>/orcamentos — criar novo orçamento ─────────
            m_novo_orc = _re.match(r"^/projetos/([^/]+)/orcamentos$", path)
            if m_novo_orc:
                nome_safe = m_novo_orc.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    db.close()
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    db.close()
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _contrato_assinado(nome_safe, db):
                    db.close()
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                if not _briefing_projeto_completo(unquote(nome_safe), db):
                    db.close()
                    self.send_json({"ok": False,
                                    "erro": "Preencha o briefing do projeto antes de iniciar a negociação."},
                                   code=400)
                    return
                _orc_dict = None
                try:
                    req      = json.loads(body.decode("utf-8", "replace")) if body else {}
                    nome_orc = (req.get("nome") or "").strip()
                    if not nome_orc:
                        self.send_json({"ok": False, "erro": "nome é obrigatório"})
                        return
                    ultimo = (db.query(Orcamento)
                                .filter_by(projeto_id=nome_safe)
                                .order_by(Orcamento.ordem.desc())
                                .first())
                    proxima_ordem = (ultimo.ordem + 1) if ultimo else 1
                    _origem_id = req.get("origem_id")
                    _desconto_novo = 0.0
                    if _origem_id:
                        _origem = _obj_da_loja(db, Orcamento, int(_origem_id), loja_id)
                        if _origem:
                            _desconto_novo = _origem.desconto_pct or 0.0
                    orc = Orcamento(
                        projeto_id=nome_safe,
                        nome=      nome_orc,
                        ordem=     proxima_ordem,
                        desconto_pct= _desconto_novo,
                        loja_id=   loja_id,
                        created_by=usuario['id'] if usuario else None,
                    )
                    db.add(orc)
                    db.commit()
                    db.refresh(orc)
                    _orc_dict = _orcamento_dict(orc)
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                    return
                finally:
                    db.close()
                # print fora do try para não capturar erros de encoding do terminal
                print("[ORC] novo orcamento: id=%d ordem=%d projeto=%r"
                      % (_orc_dict["id"], _orc_dict["ordem"], nome_safe))
                self.send_json({"ok": True, "orcamento": _orc_dict})
                return

            # ── POST /projetos/<nome_safe>/pool — carregar XML com detecção de duplicata ──
            m_pool = _re.match(r"^/projetos/([^/]+)/pool$", path)
            if m_pool:
                nome_safe = m_pool.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                _db_bf = get_session()
                try:
                    ator = _ator_dict(_db_bf, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(_db_bf, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    _bf_ok = _briefing_projeto_completo(unquote(nome_safe), _db_bf)
                finally:
                    _db_bf.close()
                if not _bf_ok:
                    self.send_json({"ok": False,
                                    "erro": "Preencha o briefing do projeto antes de subir XML."},
                                   code=400)
                    return
                ct = self.headers.get("Content-Type", "")
                arquivos, _ = _parse_multipart(body, ct)
                if not arquivos:
                    self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                    return
                arq_nome, arq_conteudo = arquivos[0]
                nome_base = re.sub(r"\.xml$", "", arq_nome, flags=re.IGNORECASE).strip()

                from integracoes.promob_grupos import ler_xml_str
                try:
                    amb = ler_xml_str(arq_nome, arq_conteudo)
                except Exception as e:
                    self.send_json({"ok": False, "erro": "XML inválido: %s" % e})
                    return

                budget_total = amb.get("total", 0.0)
                order_total  = sum(
                    item.get("order_total", 0.0)
                    for grupo in amb.get("grupos", [])
                    for item in grupo.get("itens", [])
                )
                _qa = avaliar_qualidade_xml(
                    [it for g in amb.get("grupos", []) for it in g.get("itens", [])])

                # Hash do conteúdo (ignora campos derivados do nome do arquivo)
                def _content_hash(a):
                    c = {"total": a.get("total"), "grupos": a.get("grupos", [])}
                    return hashlib.sha256(
                        json.dumps(c, sort_keys=True, ensure_ascii=False).encode("utf-8")
                    ).hexdigest()
                hash_novo = _content_hash(amb)

                db = get_session()
                if _contrato_assinado(nome_safe, db):
                    db.close()
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                try:
                    # Busca por nome
                    por_nome = db.query(PoolAmbiente).filter_by(
                        projeto_id=nome_safe, nome=nome_base
                    ).first()

                    # Busca por conteúdo (compara hash contra todos do projeto)
                    por_hash = None
                    for pa_c in db.query(PoolAmbiente).filter_by(projeto_id=nome_safe).all():
                        try:
                            h = _content_hash(json.loads(pa_c.ambientes_json))
                            if h == hash_novo:
                                por_hash = pa_c
                                break
                        except Exception:
                            continue

                    temp_base = {
                        "nome_safe":    nome_safe,
                        "nome_base":    nome_base,
                        "arq_nome":     arq_nome,
                        "arq_conteudo": arq_conteudo,
                        "amb":          amb,
                        "budget_total": budget_total,
                        "order_total":  order_total,
                        "qa":           _qa,
                    }

                    if por_nome and por_hash and por_nome.id == por_hash.id:
                        # Caso A: nome igual + conteúdo igual → já está no projeto
                        print("[POOL] ja_existe: id=%d nome=%r projeto=%r"
                              % (por_nome.id, por_nome.nome_exibicao, nome_safe))
                        self.send_json({
                            "ok":  True,
                            "acao": "ja_existe",
                            "ambiente_existente": {
                                "id":           por_nome.id,
                                "nome_exibicao": por_nome.nome_exibicao,
                            },
                        })

                    elif por_nome and (not por_hash or por_hash.id != por_nome.id):
                        # Caso B: nome igual + conteúdo diferente → perguntar sobrescrever
                        n_afetados = db.query(OrcamentoAmbiente).filter_by(
                            pool_ambiente_id=por_nome.id
                        ).count()
                        session_set("pool_xml_temp", temp_base)
                        print("[POOL] perguntar_sobrescrever: nome=%r orcamentos=%d"
                              % (nome_base, n_afetados))
                        self.send_json({
                            "ok":  True,
                            "acao": "perguntar_sobrescrever",
                            "ambiente_existente": {
                                "id":                  por_nome.id,
                                "nome_exibicao":       por_nome.nome_exibicao,
                                "orcamentos_afetados": n_afetados,
                            },
                        })

                    elif not por_nome and por_hash:
                        # Caso C: nome diferente + conteúdo igual → perguntar renomear
                        session_set("pool_xml_temp", temp_base)
                        print("[POOL] perguntar_renomear: nome_existente=%r nome_novo=%r"
                              % (por_hash.nome_exibicao, nome_base))
                        self.send_json({
                            "ok":  True,
                            "acao": "perguntar_renomear",
                            "ambiente_existente": {
                                "id":           por_hash.id,
                                "nome_exibicao": por_hash.nome_exibicao,
                            },
                            "nome_novo": nome_base,
                        })

                    else:
                        # Novo ambiente
                        pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                        os.makedirs(pasta_xmls, exist_ok=True)
                        _usuario = get_usuario_sessao(self)
                        pa = PoolAmbiente(
                            projeto_id=    nome_safe,
                            nome=          nome_base,
                            versao=        1,
                            nome_exibicao= nome_base,
                            xml_path=      os.path.join("xmls", arq_nome),
                            ambientes_json=json.dumps(amb),
                            budget_total=              budget_total,
                            order_total=               order_total,
                            qa_selo=                   _qa["qa_selo"],
                            qa_pct_sem_acrescimo=      _qa["qa_pct_sem_acrescimo"],
                            qa_markup_xml=             _qa["qa_markup_xml"],
                            qa_custo_sem_venda=        _qa["qa_custo_sem_venda"],
                            created_by=    _usuario['id'] if _usuario else None,
                        )
                        db.add(pa)
                        db.commit()
                        db.refresh(pa)
                        storage_salvar_texto(os.path.join(pasta_xmls, arq_nome), arq_conteudo)
                        print("[POOL] criado: id=%d nome_exibicao=%r projeto=%r budget=%.2f"
                              % (pa.id, pa.nome_exibicao, pa.projeto_id, pa.budget_total))
                        self.send_json({"ok": True, "acao": "criado",
                                        "ambiente": _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/<pid>/sobrescrever ────────────────────
            m_sobr = _re.match(r"^/projetos/([^/]+)/pool/(\d+)/sobrescrever$", path)
            if m_sobr:
                nome_safe = m_sobr.group(1)
                pid       = int(m_sobr.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente para sobrescrita"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if not pa or pa.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    # Atualiza o registro no pool
                    pa.xml_path               = os.path.join("xmls", temp["arq_nome"])
                    pa.ambientes_json          = json.dumps(temp["amb"])
                    pa.budget_total            = temp["budget_total"]
                    pa.order_total             = temp["order_total"]
                    _qa_s = temp.get("qa") or avaliar_qualidade_xml(
                        [it for g in temp["amb"].get("grupos", []) for it in g.get("itens", [])])
                    pa.qa_selo                 = _qa_s["qa_selo"]
                    pa.qa_pct_sem_acrescimo    = _qa_s["qa_pct_sem_acrescimo"]
                    pa.qa_markup_xml           = _qa_s["qa_markup_xml"]
                    pa.qa_custo_sem_venda      = _qa_s["qa_custo_sem_venda"]
                    # Passo 12: recalcula todos os orçamentos que referenciam este ambiente
                    links_afetados = db.query(OrcamentoAmbiente).filter_by(pool_ambiente_id=pid).all()
                    recalculados = []
                    for lk in links_afetados:
                        orc = db.get(Orcamento, lk.orcamento_id)
                        if orc:
                            todos = db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all()
                            orc.valor_total = round(
                                sum(db.get(PoolAmbiente, t.pool_ambiente_id).budget_total
                                    for t in todos), 2
                            )
                            orc.updated_at = datetime.now()
                            recalculados.append(orc.id)
                    db.commit()
                    # Salva o arquivo no disco somente após commit bem-sucedido
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    os.makedirs(pasta_xmls, exist_ok=True)
                    storage_salvar_texto(os.path.join(pasta_xmls, temp["arq_nome"]), temp["arq_conteudo"])
                    session_set("pool_xml_temp", None)
                    print("[POOL] sobrescrito: id=%d nome=%r budget=%.2f orcamentos_recalc=%s"
                          % (pa.id, pa.nome_exibicao, pa.budget_total, recalculados))
                    self.send_json({
                        "ok": True, "acao": "sobrescrito",
                        "ambiente": _pool_ambiente_dict(pa),
                        "orcamentos_recalculados": recalculados,
                        "orcamentos_afetados": len(recalculados),
                    })
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/<pid>/nova-versao ─────────────────────
            m_nova = _re.match(r"^/projetos/([^/]+)/pool/(\d+)/nova-versao$", path)
            if m_nova:
                nome_safe = m_nova.group(1)
                pid       = int(m_nova.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente para nova versão"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa_orig = db.get(PoolAmbiente, pid)
                    if not pa_orig or pa_orig.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    nova_versao      = pa_orig.versao + 1
                    # versao=2 → "_v1", versao=3 → "_v2" ...
                    nome_exib_novo   = "%s_v%d" % (pa_orig.nome, nova_versao - 1)
                    arq_nome_novo    = "%s.xml" % nome_exib_novo
                    _usuario = usuario
                    _qa_nv = temp.get("qa") or avaliar_qualidade_xml(
                        [it for g in temp["amb"].get("grupos", []) for it in g.get("itens", [])])
                    pa_novo = PoolAmbiente(
                        projeto_id=    nome_safe,
                        nome=          pa_orig.nome,
                        versao=        nova_versao,
                        nome_exibicao= nome_exib_novo,
                        xml_path=      os.path.join("xmls", arq_nome_novo),
                        ambientes_json=json.dumps(temp["amb"]),
                        budget_total=              temp["budget_total"],
                        order_total=               temp["order_total"],
                        qa_selo=                   _qa_nv["qa_selo"],
                        qa_pct_sem_acrescimo=      _qa_nv["qa_pct_sem_acrescimo"],
                        qa_markup_xml=             _qa_nv["qa_markup_xml"],
                        qa_custo_sem_venda=        _qa_nv["qa_custo_sem_venda"],
                        created_by=    _usuario['id'] if _usuario else None,
                    )
                    db.add(pa_novo)
                    db.commit()
                    db.refresh(pa_novo)
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    os.makedirs(pasta_xmls, exist_ok=True)
                    storage_salvar_texto(os.path.join(pasta_xmls, arq_nome_novo), temp["arq_conteudo"])
                    session_set("pool_xml_temp", None)
                    print("[POOL] nova versao: id=%d nome_exibicao=%r versao=%d budget=%.2f"
                          % (pa_novo.id, pa_novo.nome_exibicao, pa_novo.versao, pa_novo.budget_total))
                    self.send_json({"ok": True, "acao": "nova_versao",
                                    "ambiente": _pool_ambiente_dict(pa_novo)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/<pid>/renomear ────────────────────────
            m_ren = _re.match(r"^/projetos/([^/]+)/pool/(\d+)/renomear$", path)
            if m_ren:
                nome_safe = m_ren.group(1)
                pid       = int(m_ren.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                try:
                    req = json.loads(body)
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"})
                    return
                novo_nome = (req.get("novo_nome") or "").strip()
                if not novo_nome:
                    self.send_json({"ok": False, "erro": "Nome não pode ser vazio"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if not pa or pa.projeto_id != nome_safe:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"})
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa.nome          = novo_nome
                    pa.nome_exibicao = novo_nome
                    db.commit()
                    db.refresh(pa)
                    session_set("pool_xml_temp", None)
                    print("[POOL] renomeado: id=%d novo_nome=%r" % (pa.id, novo_nome))
                    self.send_json({"ok": True, "acao": "renomeado",
                                    "ambiente": _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /projetos/<nome_safe>/pool/criar_forcado — mesmo conteúdo, nome novo ─
            m_forc = _re.match(r"^/projetos/([^/]+)/pool/criar_forcado$", path)
            if m_forc:
                nome_safe = m_forc.group(1)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                temp      = session_get("pool_xml_temp")
                if not temp or temp.get("nome_safe") != nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum XML pendente"})
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    _qa_cf = temp.get("qa") or avaliar_qualidade_xml(
                        [it for g in temp["amb"].get("grupos", []) for it in g.get("itens", [])])
                    pa = PoolAmbiente(
                        projeto_id=    nome_safe,
                        nome=          temp["nome_base"],
                        versao=        1,
                        nome_exibicao= temp["nome_base"],
                        xml_path=      os.path.join("xmls", temp["arq_nome"]),
                        ambientes_json=json.dumps(temp["amb"]),
                        budget_total=              temp["budget_total"],
                        order_total=               temp["order_total"],
                        qa_selo=                   _qa_cf["qa_selo"],
                        qa_pct_sem_acrescimo=      _qa_cf["qa_pct_sem_acrescimo"],
                        qa_markup_xml=             _qa_cf["qa_markup_xml"],
                        qa_custo_sem_venda=        _qa_cf["qa_custo_sem_venda"],
                        created_by=    usuario['id'] if usuario else None,
                    )
                    db.add(pa)
                    db.commit()
                    db.refresh(pa)
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    os.makedirs(pasta_xmls, exist_ok=True)
                    storage_salvar_texto(os.path.join(pasta_xmls, temp["arq_nome"]), temp["arq_conteudo"])
                    session_set("pool_xml_temp", None)
                    print("[POOL] criado_forcado: id=%d nome=%r" % (pa.id, pa.nome_exibicao))
                    self.send_json({"ok": True, "acao": "criado",
                                    "ambiente": _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /orcamentos/<oid>/ambientes/<pid>/remover — remover ambiente ─────
            m_rem = _re.match(r"^/orcamentos/(\d+)/ambientes/(\d+)/remover$", path)
            if m_rem:
                oid = int(m_rem.group(1))
                pid = int(m_rem.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db  = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if pa is None or pa.projeto_id != orc.projeto_id:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    link = db.query(OrcamentoAmbiente).filter_by(
                        orcamento_id=oid, pool_ambiente_id=pid
                    ).first()
                    if not link:
                        self.send_json({"ok": False, "erro": "Ambiente não está neste orçamento"})
                        return
                    db.delete(link)
                    db.flush()
                    # Recálculo simples — Passo 8 implementa versão completa com margens
                    links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()
                    orc.valor_total = round(
                        sum(db.get(PoolAmbiente, lk.pool_ambiente_id).budget_total for lk in links), 2
                    )
                    orc.updated_at = datetime.now()
                    db.commit()
                    print("[ORC-AMB] removido: orcamento_id=%d pool_ambiente_id=%d valor_total=%.2f"
                          % (oid, pid, orc.valor_total))
                    self.send_json({"ok": True,
                                    "orcamento":        _orcamento_dict(orc),
                                    "ambiente_removido": _pool_ambiente_dict(pa) if pa else {"id": pid}})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            # ── POST /api/pool/<pid>/qa-override — liberar ambiente bloqueado ──────
            m_qaov = _re.match(r"^/api/pool/(\d+)/qa-override$", path)
            if m_qaov:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "aprovar_financeiro"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                motivo = (req.get("motivo") or "").strip()
                if not motivo:
                    self.send_json({"ok": False, "erro": "Justificativa é obrigatória."})
                    return
                db = get_session()
                try:
                    pa = db.get(PoolAmbiente, int(m_qaov.group(1)))
                    if not pa:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"}, code=404)
                        return
                    pa.qa_override_por_id = usuario["id"]
                    pa.qa_override_motivo = motivo
                    db.add(LogAcaoGerencial(
                        autorizador_id=usuario["id"], acao="qa_override",
                        projeto_nome=pa.projeto_id,
                        contexto=json.dumps({"pool_ambiente_id": pa.id, "motivo": motivo})))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            # ── POST /orcamentos/<oid>/ambientes/<pid> — adicionar ambiente ──────────
            m_add = _re.match(r"^/orcamentos/(\d+)/ambientes/(\d+)$", path)
            if m_add:
                oid = int(m_add.group(1))
                pid = int(m_add.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db  = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    pa = db.get(PoolAmbiente, pid)
                    if pa is None or pa.projeto_id != orc.projeto_id:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if pa.qa_selo == "bloqueado" and pa.qa_override_por_id is None:
                        self.send_json({"ok": False, "erro":
                            "Ambiente bloqueado por qualidade do XML (acréscimo zerado). "
                            "Re-exporte o XML ou solicite liberação ao Diretor/Gerente."}, code=409)
                        return
                    ja_existe = db.query(OrcamentoAmbiente).filter_by(
                        orcamento_id=oid, pool_ambiente_id=pid
                    ).first()
                    if ja_existe:
                        self.send_json({"ok": False, "erro": "Ambiente já está neste orçamento"})
                        return
                    ordem = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).count() + 1
                    db.add(OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=ordem))
                    db.flush()
                    # Recálculo simples — Passo 8 implementa versão completa com margens
                    links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()
                    orc.valor_total = round(
                        sum(db.get(PoolAmbiente, lk.pool_ambiente_id).budget_total for lk in links), 2
                    )
                    orc.updated_at = datetime.now()
                    db.commit()
                    print("[ORC-AMB] adicionado: orcamento_id=%d pool_ambiente_id=%d valor_total=%.2f"
                          % (oid, pid, orc.valor_total))
                    self.send_json({"ok": True,
                                    "orcamento": _orcamento_dict(orc),
                                    "ambiente":  _pool_ambiente_dict(pa)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)})
                finally:
                    db.close()
                return

            if path == "/api/admin/usuarios":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db  = get_session()
                try:
                    logins = [u.login for u in db.query(Usuario.login).all()]
                    erros  = mod_usuarios.validar_novo_usuario(req, logins)
                    ator   = _ator_dict(db, usuario)
                    # compat: se só loja_ids vier (sem loja_id), usa o primeiro como primário
                    req_tenant = dict(req)
                    if "loja_ids" in req_tenant and not req_tenant.get("loja_id"):
                        ids_raw = req_tenant["loja_ids"]
                        if ids_raw:
                            req_tenant["loja_id"] = int(ids_raw[0])
                    loja_id, rede_id, erros_tenant = mod_tenancy.atribuir_tenant_usuario(ator, req_tenant)
                    loja_ids, erros_lojas = mod_tenancy.lojas_do_novo_usuario(ator, req)
                    erros = erros + erros_tenant + erros_lojas
                    # valida cada loja no escopo do ator (admin_rede/diretor)
                    if not erros and loja_ids and not mod_tenancy._eh_super_admin(ator):
                        for lid in loja_ids:
                            loja = db.get(Loja, lid)
                            if not loja or not mod_tenancy.pode_ver_loja(
                                    ator, {"id": loja.id, "rede_id": loja.rede_id}):
                                erros = erros + ["Loja fora do seu escopo."]; break
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                    import validacao_doc
                    _e = validacao_doc.erro_doc(req.get("cpf"), "CPF", "cpf")
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
                        return
                    primary_loja_id = loja_ids[0] if loja_ids else None
                    u = Usuario(nome=req["nome"].strip(), login=req["login"].strip(),
                                nivel=req["nivel"].strip(),
                                telefone=(req.get("telefone") or "").strip(),
                                whatsapp=(req.get("whatsapp") or "").strip(),
                                email=(req.get("email") or "").strip(),
                                cpf=(req.get("cpf") or "").strip(),
                                loja_id=primary_loja_id, rede_id=rede_id)
                    u.set_senha(req["senha"])
                    db.add(u); db.flush()
                    for lid in loja_ids:
                        db.add(UsuarioLoja(usuario_id=u.id, loja_id=lid))
                    db.commit()
                    self.send_json({"ok": True, "id": u.id})
                finally:
                    db.close()
                return

            if path == "/api/admin/perfis":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_perfis"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    from auth import perfil_store
                    lid = _loja_admin_alvo(usuario)
                    if lid is None:
                        self.send_json({"ok": False, "erro": "Selecione uma loja para criar o perfil."}); return
                    p, err = perfil_store.criar_perfil(db, lid,
                                req.get("nome", ""), req.get("base", ""), req.get("modulos", []),
                                capacidades=req.get("capacidades"))
                    if not p:
                        self.send_json({"ok": False, "erro": err}); return
                    perfis.recarregar()
                    self.send_json({"ok": True, "perfil": {"slug": p.slug, "nome": p.nome}}, code=201)
                finally:
                    db.close()
                return

            if path == "/api/admin/redes":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                erros = mod_tenancy.validar_rede(req)
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                import validacao_doc
                _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                if _e:
                    self.send_json({"ok": False, "erro": _e}, code=400)
                    return
                db = get_session()
                try:
                    r = Rede(nome=req["nome"].strip(),
                             cnpj=(req.get("cnpj") or "").strip() or None)
                    db.add(r); db.commit()
                    self.send_json({"ok": True, "rede": _rede_dict(r)})
                finally:
                    db.close()
                return

            if path == "/api/admin/lojas":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_lojas"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    codigos = [c for (c,) in db.query(Loja.codigo).all() if c]
                    erros = mod_tenancy.validar_loja(req, codigos)
                    rede_id = req.get("rede_id")
                    if not mod_tenancy._eh_super_admin(ator):
                        rede_id = ator.get("rede_id")
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                    import validacao_doc
                    _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                    if _e:
                        self.send_json({"ok": False, "erro": _e}, code=400)
                        return
                    l = Loja(
                        nome=req["nome"].strip(),
                        codigo=req["codigo"].strip().upper(),
                        rede_id=rede_id,
                        cnpj=(req.get("cnpj") or "").strip() or None,
                        telefone=(req.get("telefone") or "").strip() or None,
                        email=(req.get("email") or "").strip() or None,
                        responsavel=(req.get("responsavel") or "").strip() or None,
                        cep=(req.get("cep") or "").strip() or None,
                        logradouro=(req.get("logradouro") or "").strip() or None,
                        numero=(req.get("numero") or "").strip() or None,
                        complemento=(req.get("complemento") or "").strip() or None,
                        bairro=(req.get("bairro") or "").strip() or None,
                        cidade=(req.get("cidade") or "").strip() or None,
                        estado=((req.get("estado") or req.get("uf") or "").strip() or None),
                    )
                    if isinstance(req.get("modulos"), list):
                        l.modulos_ativos = json.dumps([str(m) for m in req["modulos"]])
                    db.add(l); db.flush()   # precisa do l.id p/ o diretor
                    dir_req = req.get("diretor") or {}
                    dir_login = (dir_req.get("login") or "").strip()
                    if dir_login:
                        if db.query(Usuario).filter(Usuario.login == dir_login).first() is not None:
                            self.send_json({"ok": False, "erro": "Já existe uma conta com este e-mail (diretor)."}); return
                        senha_ini = validacao_doc._digitos(l.cnpj or "") or "orizon123"
                        u = Usuario(nome=(dir_req.get("nome") or dir_login).strip(), login=dir_login,
                                    email=dir_login, nivel="master", loja_id=l.id, ativo=1, senha_provisoria=1)
                        u.set_senha(senha_ini); db.add(u); db.flush()
                        db.add(UsuarioLoja(usuario_id=u.id, loja_id=l.id))
                    db.commit()
                    self.send_json({"ok": True, "loja": _loja_dict(l)})
                finally:
                    db.close()
                return

            m_pdv = _re.match(r"^/api/admin/lojas/(\d+)/pdvs$", path)
            if m_pdv:
                # Criar Ponto de Venda da loja (spec 2026-07-22, Desvio 4): SÓ super_admin.
                # O PDV nasce SEM emitente (fiscal pela mãe), com rede herdada e config
                # financeira copiada da mãe (metas/faixas ajustáveis depois).
                usuario = get_usuario_sessao(self)
                if not usuario or usuario.get("nivel") != "super_admin":
                    self.send_json({"ok": False, "erro": "Criar Ponto de Venda é exclusivo "
                                    "do administrador da plataforma."}, code=403)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    mae = db.get(Loja, int(m_pdv.group(1)))
                    if mae is None:
                        self.send_json({"ok": False, "erro": "Loja não encontrada"}, code=404)
                        return
                    if mae.loja_mae_id:
                        self.send_json({"ok": False, "erro": "Um Ponto de Venda não pode ter "
                                        "Pontos de Venda próprios."}, code=400)
                        return
                    codigos = [c for (c,) in db.query(Loja.codigo).all() if c]
                    erros = mod_tenancy.validar_loja(req, codigos)
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                    pdv = Loja(
                        nome=req["nome"].strip(),
                        codigo=req["codigo"].strip().upper(),
                        tipo="ponto_venda",
                        loja_mae_id=mae.id,
                        rede_id=mae.rede_id,                    # herdado, não editável
                        config_financeira_json=mae.config_financeira_json,   # seed = cópia da mãe
                        pct_mercadoria=mae.pct_mercadoria,
                        pct_servico=mae.pct_servico,
                        telefone=(req.get("telefone") or "").strip() or None,
                        email=(req.get("email") or "").strip() or None,
                        responsavel=(req.get("responsavel") or "").strip() or None,
                        cep=(req.get("cep") or "").strip() or None,
                        logradouro=(req.get("logradouro") or "").strip() or None,
                        numero=(req.get("numero") or "").strip() or None,
                        complemento=(req.get("complemento") or "").strip() or None,
                        bairro=(req.get("bairro") or "").strip() or None,
                        cidade=(req.get("cidade") or "").strip() or None,
                        estado=((req.get("estado") or req.get("uf") or "").strip() or None),
                        testemunha1_nome=(req.get("testemunha1_nome") or "").strip() or None,
                        testemunha1_cpf=(req.get("testemunha1_cpf") or "").strip() or None,
                        testemunha2_nome=(req.get("testemunha2_nome") or "").strip() or None,
                        testemunha2_cpf=(req.get("testemunha2_cpf") or "").strip() or None,
                    )
                    db.add(pdv); db.flush()
                    # Perfis padrão do PDV (master/gerencial/operador) — fiel ao que a
                    # migração semeia para lojas plenas; sem isto o cadastro de usuários
                    # do PDV cai no fallback hardcoded.
                    from auth import perfil_store
                    perfil_store.seed_perfis_loja(db, pdv.id)
                    db.commit()
                    perfis.recarregar()
                    self.send_json({"ok": True, "pdv": _loja_dict(pdv)})
                finally:
                    db.close()
                return

            m = _re.match(r"^/projetos/([^/]+)/ambientes/(adicionar|remover|atualizar|selecao)$", path)
            if m:
                nome_safe = m.group(1)
                acao = m.group(2)

                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                _db_scope = get_session()
                try:
                    ator = _ator_dict(_db_scope, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(_db_scope, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                finally:
                    _db_scope.close()

                # Rotas de escrita bloqueadas após aprovação
                if acao in ("adicionar", "remover", "atualizar"):
                    _proj_chk = _carregar_projeto(nome_safe)
                    if _proj_chk and _proj_chk.get("bloqueado"):
                        self.send_json({"ok": False, "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."})
                        return

                if acao == "adicionar":
                    ct = self.headers.get("Content-Type", "")
                    arquivos, _ = _parse_multipart(body, ct)
                    if not arquivos:
                        self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                        return
                    try:
                        proj = _adicionar_ambientes(nome_safe, arquivos)
                        session_set("projeto_ativo", nome_safe)
                        self.send_json({"ok": True, "projeto": proj})
                    except Exception as e:
                        self.send_json({"ok": False, "erro": str(e)})

                elif acao == "remover":
                    req = json.loads(body)
                    arquivo = req.get("arquivo", "").strip()
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"})
                        return
                    proj["ambientes"] = [a for a in proj["ambientes"] if a["arquivo"] != arquivo]
                    xml_path = os.path.join(_projeto_path(nome_safe), "xmls", arquivo)
                    storage_deletar(xml_path)
                    _salvar_projeto(proj)
                    self.send_json({"ok": True, "projeto": proj})

                elif acao == "atualizar":
                    ct = self.headers.get("Content-Type", "")
                    arquivos, campos = _parse_multipart(body, ct)
                    arquivo_sub = campos.get("arquivo_substituir", "").strip()
                    if not arquivos:
                        self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                        return
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"})
                        return
                    pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
                    sel_anterior = True
                    for a in proj["ambientes"]:
                        if a["arquivo"] == arquivo_sub:
                            sel_anterior = a.get("selecionado", True)
                    proj["ambientes"] = [a for a in proj["ambientes"] if a["arquivo"] != arquivo_sub]
                    old_xml = os.path.join(pasta_xmls, arquivo_sub)
                    if arquivo_sub:
                        storage_deletar(old_xml)
                    for nome_arq, conteudo in arquivos:
                        storage_salvar_texto(os.path.join(pasta_xmls, nome_arq), conteudo)
                    dados = carregar_xmls(arquivos)
                    for amb in dados.get("ambientes", []):
                        amb["selecionado"] = sel_anterior
                        amb["arquivo_path"] = os.path.join(pasta_xmls, amb["arquivo"])
                        proj["ambientes"].append(amb)
                    _salvar_projeto(proj)
                    self.send_json({"ok": True, "projeto": proj})

                elif acao == "selecao":
                    req = json.loads(body)
                    selecoes = req.get("selecoes", {})
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto nao encontrado"})
                        return
                    for amb in proj["ambientes"]:
                        if amb["arquivo"] in selecoes:
                            amb["selecionado"] = selecoes[amb["arquivo"]]
                    _salvar_projeto(proj)
                    self.send_json({"ok": True})

            # POST /api/projetos/<nome>/ciclo/desfazer_aprovacao — volta ao orçamento (requer gerente)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/desfazer_aprovacao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    req   = json.loads(body or b'{}')
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    # Sessão-primeiro (2026-07-24): logado com 'autorizar' não redigita senha.
                    autorizador = _usuario_com_capacidade(db, login, senha, "autorizar", sessao=usuario)
                    if not autorizador:
                        self.send_json({"ok": False, "erro": "Credenciais inválidas ou perfil sem permissão (Gerente/Diretor)"})
                        return
                    # Verifica se contrato está assinado — nesse caso não pode voltar
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if contrato and contrato.status in ("assinado", "vigente"):
                        self.send_json({"ok": False,
                                        "erro": "Contrato já assinado — não é possível voltar ao orçamento"})
                        return
                    # Resetar etapa 7 (a geração do contrato iniciou a 7); a etapa 4
                    # (Orçamento) permanece concluída — voltar ao orçamento reabre o contrato.
                    e7 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="7").first()
                    if e7: db.delete(e7)
                    # Resetar contrato para rascunho
                    if contrato:
                        contrato.status = "rascunho"
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/reabrir — reabre em cascata (requer gerente)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/reabrir$', path)
            if m:
                nome_safe   = unquote(m.group(1))
                etapa_cod   = unquote(m.group(2))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    req   = json.loads(body or b'{}')
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    # Sessão-primeiro (2026-07-24): logado com 'autorizar' não redigita senha.
                    autorizador = _usuario_com_capacidade(db, login, senha, "autorizar", sessao=solicitante)
                    if not autorizador:
                        self.send_json({"ok": False, "erro": "Credenciais inválidas ou perfil sem permissão (Gerente/Diretor)"}, code=403)
                        return
                    todas    = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    codigos  = [e.etapa_codigo for e in todas]
                    resetar  = mod_ciclo.codigos_a_resetar(etapa_cod, codigos)
                    # Trava: não reabrir se desfaz contrato assinado/vigente
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    cstatus  = contrato.status if contrato else ""
                    if mod_ciclo.reabertura_bloqueada_por_contrato(resetar, cstatus):
                        self.send_json({"ok": False,
                                        "erro": "Contrato já assinado — não é possível reabrir esta etapa"},
                                       code=400)
                        return
                    resetar_set = set(resetar)
                    status_anterior = {e.etapa_codigo: e.status for e in todas
                                       if e.etapa_codigo in resetar_set}
                    for e in todas:
                        if e.etapa_codigo in resetar_set:
                            e.status         = "pendente"
                            e.iniciado_em    = None
                            e.concluido_em   = None
                            e.responsavel_id = None
                            try:               # Fase 4: cancela comissão do papel reaberto (se não paga)
                                import mod_comissao
                                if e.responsavel_funcionario_id:
                                    mod_comissao.cancelar_comissao_etapa(db, e.projeto_nome, e.etapa_codigo,
                                                                         e.responsavel_funcionario_id)
                            except Exception as _e:
                                print("[COMISSAO] cancelar falhou:", _e)
                    log = LogAcaoGerencial(
                        solicitante_id=solicitante["id"],
                        autorizador_id=autorizador.id,
                        acao="reabrir_cascata",
                        projeto_nome=nome_safe,
                        etapa_alvo=etapa_cod,
                        contexto=json.dumps({"resetadas": sorted(resetar_set),
                                             "status_anterior": status_anterior}),
                    )
                    db.add(log)
                    db.commit()
                    self.send_json({"ok": True, "resetadas": sorted(resetar_set)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/data-prevista — edita a data prevista de
            # conclusão de uma etapa (Cronograma do Ciclo, Modulos_Orizon_v11). Protegida por
            # reautenticação Gerente+ (mesmo princípio dos gates financeiros) e auditada (quem/quando/
            # valor antigo → novo) em LogAcaoGerencial.
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/data-prevista$', path)
            if m:
                nome_safe   = unquote(m.group(1))
                etapa_cod   = unquote(m.group(2))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    req   = json.loads(body or b'{}')
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    nova_str = (req.get("data_prevista") or "").strip()   # "AAAA-MM-DD"
                    # Sessão-primeiro (2026-07-24): logado com 'autorizar' não redigita senha.
                    autorizador = _usuario_com_capacidade(db, login, senha, "autorizar", sessao=solicitante)
                    if not autorizador:
                        self.send_json({"ok": False, "erro": "Credenciais inválidas ou perfil sem permissão (Gerente/Diretor)"}, code=403)
                        return
                    try:
                        nova_dt = datetime.strptime(nova_str, "%Y-%m-%d") if nova_str else None
                    except ValueError:
                        self.send_json({"ok": False, "erro": "Data inválida (use AAAA-MM-DD)"}, code=400)
                        return
                    if nova_dt is None:
                        self.send_json({"ok": False, "erro": "Informe a nova data prevista"}, code=400)
                        return
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod).first()
                    if etapa is None:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    antigo = etapa.data_prevista_conclusao
                    etapa.data_prevista_conclusao = nova_dt
                    db.add(LogAcaoGerencial(
                        solicitante_id=solicitante["id"],
                        autorizador_id=autorizador.id,
                        acao="editar_data_prevista",
                        projeto_nome=nome_safe,
                        etapa_alvo=etapa_cod,
                        contexto=json.dumps({
                            "valor_antigo": antigo.isoformat() if antigo else None,
                            "valor_novo":   nova_dt.isoformat(),
                        }),
                    ))
                    db.commit()
                    self.send_json({"ok": True, "data_prevista_conclusao": nova_dt.isoformat()})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/responsavel — escolhe o FUNCIONÁRIO responsável
            # pela etapa (Cronograma do Projeto, Modulos_Orizon_v12). O funcionário precisa ter a FUNÇÃO
            # exigida pela fase (funcao_responsavel_id, herdada do padrão no D0). funcionario_id vazio limpa.
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/responsavel$', path)
            if m:
                nome_safe = unquote(m.group(1))
                etapa_cod = unquote(m.group(2))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    req = json.loads(body or b'{}')
                    fio_id = req.get("funcionario_id")
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod).first()
                    if etapa is None:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    if fio_id in (None, "", 0, "0"):
                        etapa.responsavel_funcionario_id = None
                    else:
                        func = db.get(Funcionario, int(fio_id))
                        if func is None or func.loja_id != loja_id:
                            self.send_json({"ok": False, "erro": "Funcionário não encontrado"}, code=404); return
                        # Restrição por função: se a fase exige uma função, o funcionário tem de tê-la.
                        if etapa.funcao_responsavel_id and func.funcao_id != etapa.funcao_responsavel_id:
                            self.send_json({"ok": False,
                                            "erro": "Funcionário não tem a função exigida por esta fase"}, code=400)
                            return
                        etapa.responsavel_funcionario_id = func.id
                    db.commit()
                    self.send_json({"ok": True, "responsavel_funcionario_id": etapa.responsavel_funcionario_id})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/atribuicoes — upsert de atribuição(ões) do Mapa (Regras
            # §4/§5). Body: {papel, pool_ambiente_id|null, funcionario_id|null, terceiro_id|null}
            # (1 alvo, comportamento de sempre) OU {papel, pool_ambiente_id|null,
            # alvos:[{tipo,id},...]} (2026-08-06: papel="montagem" aceita VÁRIOS executores por
            # ambiente — substitui TODO o conjunto, mesmo padrão de mod_equipe._salvar_montagem
            # já usado pra Equipe de Montagem no projeto inteiro). PE/Medição/Assistência
            # continuam 1:1 (trava real no banco — ver database.py). Auditado em
            # LogAcaoGerencial. Só Gerência+/Supervisor.
            m = _re.match(r'^/api/projetos/([^/]+)/atribuicoes$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not _pode_editar_mapa(ator.get("nivel")):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    req = json.loads(body or b'{}')
                    papel = (req.get("papel") or "").strip()
                    if papel not in mod_escopo.PAPEIS:
                        self.send_json({"ok": False, "erro": "Papel inválido"}, code=400); return
                    # LOTE (rev 2026-08-03, box "Todos os ambientes" do Mapa): pool_ambiente_ids
                    # aplica o MESMO alvo a vários ambientes num só POST — uma auditoria e UMA
                    # notificação (evita N mensagens ao mesmo profissional).
                    if req.get("pool_ambiente_ids"):
                        try:
                            alvo_amb_ids = [int(x) for x in req["pool_ambiente_ids"]]
                        except (TypeError, ValueError):
                            self.send_json({"ok": False, "erro": "Ambientes inválidos"}, code=400); return
                    else:
                        _raw = req.get("pool_ambiente_id")
                        alvo_amb_ids = [int(_raw) if _raw not in (None, "", 0, "0") else None]
                    for aid in alvo_amb_ids:
                        if aid is not None:
                            pa = db.get(PoolAmbiente, aid)
                            if pa is None or pa.projeto_id != nome_safe:
                                self.send_json({"ok": False, "erro": "Ambiente não encontrado"}, code=404); return

                    # múltiplos executores (2026-08-06, só "montagem"): {alvos:[{tipo,id},...]}
                    _alvos_req = req.get("alvos")
                    if _alvos_req is not None and papel != "montagem":
                        self.send_json({"ok": False,
                                        "erro": "Só o papel 'montagem' aceita mais de um executor."}, code=400)
                        return

                    def _resolve_alvo(tipo, id_):
                        """(obj, erro, http_code) — separa "não achei" (404) de "achei mas não
                        serve" (400), achado 2026-08-06: a versão anterior devolvia `obj=None`
                        nos dois casos e tentava adivinhar o código pelo TEXTO da mensagem."""
                        Model = Funcionario if tipo == "funcionario" else Terceiro
                        obj = db.get(Model, int(id_)) if id_ else None
                        if obj is None or obj.loja_id != loja_id:
                            return None, "Profissional não encontrado", 404
                        fnome = ""
                        if getattr(obj, "funcao_id", None):
                            _fn = db.get(Funcao, obj.funcao_id); fnome = _fn.nome if _fn else ""
                        if not mod_escopo.funcao_compativel(papel, fnome):
                            return None, "Profissional não tem função compatível com este papel", 400
                        return obj, None, None

                    alvos = []   # [(tipo, id, obj)] — lista normalizada, 0..N
                    if _alvos_req is not None:
                        for a in _alvos_req:
                            tipo = "funcionario" if (a or {}).get("tipo") in ("f", "funcionario") else "terceiro"
                            obj, erro, cod = _resolve_alvo(tipo, (a or {}).get("id"))
                            if erro:
                                self.send_json({"ok": False, "erro": erro}, code=cod); return
                            alvos.append((tipo, obj.id, obj))
                    else:
                        fio_id = req.get("funcionario_id") or None
                        ter_id = req.get("terceiro_id") or None
                        if fio_id or ter_id:
                            tipo = "funcionario" if fio_id else "terceiro"
                            obj, erro, cod = _resolve_alvo(tipo, fio_id or ter_id)
                            if erro:
                                self.send_json({"ok": False, "erro": erro}, code=cod); return
                            alvos.append((tipo, obj.id, obj))

                    # Bloqueio de conflito de agenda (2026-08-06, decisão do usuário: "bloqueia
                    # sempre" — sem override, nem pra gerência). Roda ANTES de tocar o banco:
                    # antes disso o conflito era só um AVISO calculado DEPOIS do commit (a troca
                    # já tinha sido salva) — o usuário não conseguia recusar. Simula "e se esse
                    # alvo entrasse aqui?" comparando a janela deste projeto (calculada com o
                    # estado ATUAL, pré-troca) contra as janelas de QUALQUER outro projeto onde o
                    # alvo já responde por montagem/PE.
                    if alvos and papel in ("montagem", "projeto_executivo"):
                        import mod_agenda as _mag
                        _cfg_ag_pre = (_cfg_financeira_loja(db, loja_id) or {}).get("agenda") or {}
                        _itens_pre = _montagem_itens_enriquecidos(db, ator, loja_id, _cfg_ag_pre,
                                                                  papel=papel)
                        janelas_alvo = [(it["inicio"], it["fim"]) for it in _itens_pre
                                        if it["projeto"] == nome_safe and not it.get("realizado")
                                        and (alvo_amb_ids == [None] or
                                             any(a2["id"] in alvo_amb_ids
                                                 for a2 in (it.get("ambientes") or [])))]
                        if janelas_alvo:
                            outros_por_chave = {}
                            for it in _itens_pre:
                                if it.get("realizado") or it["projeto"] == nome_safe:
                                    continue
                                for m in (it.get("montadores") or []):
                                    if not m.get("chave"):
                                        continue
                                    outros_por_chave.setdefault(m["chave"], []).append(
                                        (it["projeto"], it["inicio"], it["fim"]))
                            bloqueios = []
                            for tipo, oid, obj in alvos:
                                chave = ("f:%d" % oid) if tipo == "funcionario" else ("t:%d" % oid)
                                for (o_proj, o_ini, o_fim) in outros_por_chave.get(chave, []):
                                    if any(ini <= o_fim and o_ini <= fim for ini, fim in janelas_alvo):
                                        bloqueios.append(
                                            "%s já está em %s (%s–%s)"
                                            % (obj.nome, o_proj, o_ini.strftime("%d/%m/%Y"),
                                               o_fim.strftime("%d/%m/%Y")))
                                        break
                            if bloqueios:
                                self.send_json({"ok": False, "erro": "Conflito de agenda — "
                                               + "; ".join(sorted(set(bloqueios)))}, code=409)
                                return

                    trocas = []
                    novos_alvos_uids = set()   # só notifica quem é NOVO no conjunto (evita spam)
                    for amb_id in alvo_amb_ids:
                        q_reg = (db.query(AtribuicaoAmbiente)
                                   .filter_by(projeto_nome=nome_safe, papel=papel)
                                   .filter(AtribuicaoAmbiente.pool_ambiente_id.is_(None) if amb_id is None
                                           else AtribuicaoAmbiente.pool_ambiente_id == amb_id))
                        regs_antigos = q_reg.all()
                        antes_chaves = {(r.funcionario_id, r.terceiro_id) for r in regs_antigos}
                        antigo_rot = [(r.funcionario_id or ("t%d" % r.terceiro_id)) for r in regs_antigos]
                        for r in regs_antigos:
                            db.delete(r)
                        novo_rot = []
                        for tipo, oid, obj in alvos:
                            reg = AtribuicaoAmbiente(loja_id=loja_id, projeto_nome=nome_safe,
                                                     pool_ambiente_id=amb_id, papel=papel,
                                                     atribuido_por_id=usuario["id"])
                            if tipo == "funcionario":
                                reg.funcionario_id = oid
                            else:
                                reg.terceiro_id = oid
                            db.add(reg)
                            novo_rot.append(oid if tipo == "funcionario" else ("t%d" % oid))
                            chave = (oid, None) if tipo == "funcionario" else (None, oid)
                            if chave not in antes_chaves:
                                uid = getattr(obj, "usuario_id", None)
                                if uid and uid != usuario["id"]:
                                    novos_alvos_uids.add(uid)
                        trocas.append({"pool_ambiente_id": amb_id,
                                       "alvo_antigo": (antigo_rot[0] if len(antigo_rot) == 1 else (antigo_rot or None)),
                                       "alvo_novo": (novo_rot[0] if len(novo_rot) == 1 else (novo_rot or None))})
                    db.add(LogAcaoGerencial(
                        solicitante_id=usuario["id"], autorizador_id=usuario["id"],
                        acao="atribuir_mapa", projeto_nome=nome_safe, etapa_alvo=papel,
                        contexto=json.dumps({"papel": papel, "trocas": trocas})))
                    db.commit()
                    # ── pós-commit, best-effort: notificação via Orizon Chat ──
                    # (aviso de conflito saiu daqui — 2026-08-06, virou bloqueio PRÉ-commit acima)
                    _PAPEL_ROTULO = {"projeto_executivo": "Projeto Executivo", "medicao": "Medição",
                                     "montagem": "Montagem", "assistencia": "Assistência"}
                    notificado = False
                    if novos_alvos_uids:
                        try:
                            import mod_chat as _mchat
                            nomes_amb = [pa.nome_exibicao or pa.nome for pa in
                                         db.query(PoolAmbiente).filter(
                                             PoolAmbiente.id.in_([a for a in alvo_amb_ids if a])).all()]
                            onde = ("no projeto inteiro" if alvo_amb_ids == [None]
                                    else ("no ambiente %s" % nomes_amb[0] if len(nomes_amb) == 1
                                          else "em %d ambientes (%s)" % (len(nomes_amb), ", ".join(nomes_amb))))
                            corpo = ("📌 Você foi atribuído como responsável de %s %s no projeto %s."
                                     % (_PAPEL_ROTULO.get(papel, papel), onde, nome_safe))
                            for alvo_uid in novos_alvos_uids:
                                conv = _mchat.get_or_create_direct(db, loja_id, usuario["id"], alvo_uid,
                                                                  assunto_tipo="livre")
                                msg = _mchat.enviar_mensagem(db, conv, usuario["id"], corpo)
                                db.commit()
                                try:
                                    import mod_chat_externo as _mwa
                                    _mwa.notificar_conversa(db, conv, msg, usuario["id"])
                                    db.commit()
                                except Exception:
                                    db.rollback()
                            notificado = True
                        except Exception:
                            db.rollback()   # notificação nunca derruba a atribuição (já commitada)
                    self.send_json({"ok": True, "atribuicoes": _serializar_atribuicoes(db, nome_safe),
                                    "notificado": notificado})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/parceiro — associa/remove o parceiro (arquiteto) do
            # projeto (etapa "Criação do Projeto"). Editável só ATÉ a assinatura do contrato.
            m = _re.match(r'^/api/projetos/([^/]+)/parceiro$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    _meta = _projeto_da_loja(db, nome_safe, loja_id)
                    if _meta is None or not _projeto_visivel_ao_ator(_meta, usuario, db):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if _contrato_totalmente_assinado(nome_safe, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado por ambas as partes — o parceiro não pode mais ser alterado"},
                                       code=400)
                        return
                    req = json.loads(body or b'{}')
                    pid = req.get("parceiro_id")
                    parceiro_dict = None
                    if pid:
                        parc = db.get(Parceiro, int(pid))
                        if parc is None or not _parceiro_visivel_loja(db, parc, loja_id):
                            self.send_json({"ok": False, "erro": "Parceiro fora do seu escopo"}, code=400)
                            return
                        parceiro_dict = _parceiro_dict(parc, db)
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto não encontrado"}, code=404)
                        return
                    proj["parceiro_id"] = int(pid) if pid else None
                    _salvar_projeto(proj)
                    self.send_json({"ok": True, "parceiro": parceiro_dict})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/editar — altera os campos de criação (nome, cliente,
            # parceiro, consultor). Cliente/parceiro travam após contrato assinado; nome e
            # consultor seguem editáveis. Reatribuir consultor exige gerente+ (escopo não-próprio).
            m = _re.match(r'^/api/projetos/([^/]+)/editar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    _meta = _projeto_da_loja(db, nome_safe, loja_id)
                    if _meta is None or not _projeto_visivel_ao_ator(_meta, usuario, db):
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    proj = _carregar_projeto(nome_safe)
                    if not proj:
                        self.send_json({"ok": False, "erro": "Projeto não encontrado"}, code=404)
                        return
                    req = json.loads(body or b'{}')
                    assinado = _contrato_totalmente_assinado(nome_safe, db)
                    pode_atribuir = not _ve_apenas_proprios_projetos(usuario.get("nivel"))

                    # Nome exibido (a chave nome_safe é preservada) — sempre editável
                    if "nome_projeto" in req:
                        nv = (req.get("nome_projeto") or "").strip()
                        if nv:
                            proj["nome_projeto"] = nv

                    # Consultor responsável — só gerente+; editável mesmo após o contrato
                    if "consultor_id" in req:
                        if not pode_atribuir:
                            self.send_json({"ok": False, "erro": "Sem permissão para reatribuir o consultor"}, code=403)
                            return
                        cid = req.get("consultor_id")
                        if cid:
                            alvo = db.query(Usuario).filter_by(id=int(cid)).first()
                            if not _usuario_pertence_a_loja(db, alvo, loja_id):
                                self.send_json({"ok": False, "erro": "Consultor fora da loja"}, code=400)
                                return
                            _meta.criado_por_id = int(cid)

                    # Cliente — travado após contrato assinado
                    if "cliente_id" in req:
                        if assinado:
                            self.send_json({"ok": False, "erro": "Contrato assinado — cliente não pode ser alterado"}, code=400)
                            return
                        cid = req.get("cliente_id")
                        if cid:
                            c = _obj_da_loja(db, Cliente, int(cid), loja_id)
                            if not c:
                                self.send_json({"ok": False, "erro": "Cliente fora da loja"}, code=400)
                                return
                            proj["cliente_id"] = int(cid)
                            proj["cliente"] = {"nome": c.nome, "cpf": c.cpf or "",
                                               "email": c.email or "", "telefone": c.telefone or ""}
                            _meta.cliente_id = int(cid)

                    # Parceiro — travado após contrato assinado ("" / null remove)
                    if "parceiro_id" in req:
                        if assinado:
                            self.send_json({"ok": False, "erro": "Contrato assinado — parceiro não pode ser alterado"}, code=400)
                            return
                        pid = req.get("parceiro_id")
                        if pid:
                            parc = db.get(Parceiro, int(pid))
                            if parc is None or not _parceiro_visivel_loja(db, parc, loja_id):
                                self.send_json({"ok": False, "erro": "Parceiro fora do seu escopo"}, code=400)
                                return
                        proj["parceiro_id"] = int(pid) if pid else None

                    _salvar_projeto(proj)
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/contrato/assinar — registra assinatura
            m = _re.match(r'^/api/projetos/([^/]+)/contrato/assinar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req   = json.loads(body)
                parte = (req.get("parte") or "").strip()
                nome  = (req.get("nome")  or "").strip()
                cpf   = (req.get("cpf")   or "").strip()
                if parte not in ("loja", "cliente"):
                    self.send_json({"ok": False, "erro": "parte deve ser 'loja' ou 'cliente'"}, code=400)
                    return
                if not nome or not cpf:
                    self.send_json({"ok": False, "erro": "nome e cpf são obrigatórios"}, code=400)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        self.send_json({"ok": False, "erro": "Contrato não encontrado"}, code=404)
                        return
                    if contrato.status in ("vigente", "assinado"):
                        self.send_json({"ok": False, "erro": "Contrato já está vigente"}, code=400)
                        return
                    ja_assinou = any(a.parte == parte for a in contrato.assinaturas)
                    if ja_assinou:
                        self.send_json({"ok": False, "erro": f"Parte '{parte}' já assinou"}, code=400)
                        return
                    # Gate (Fatia 2): QUALQUER assinatura — já a 1ª — exige as datas do acordo definidas e a
                    # data de entrega cabendo na folga (ou autorizada sob gerência). Antes só travava a
                    # assinatura que COMPLETAVA o contrato (loja+cliente); agora bloqueia desde a primeira.
                    _pm = db.get(Projeto, nome_safe)
                    if _pm is None or _pm.data_entrega is None or _pm.previsao_medicao is None:
                        self.send_json({"ok": False,
                            "erro": "Defina a data de entrega esperada E a previsão de medição antes de assinar."}, code=400)
                        return
                    import mod_cronograma as _mcr_sig
                    _folga_sig = _mcr_sig.folga_medicao_entrega(
                        _cfg_financeira_loja(db, loja_id), _pm.previsao_medicao, _pm.data_entrega)
                    if _folga_sig < 0 and not _pm.folga_autorizada:
                        self.send_json({"ok": False,
                            "erro": "A data de entrega não cabe no cronograma (folga negativa) e não foi autorizada. "
                                    "Ajuste a data ou registre com autorização gerencial antes de assinar."}, code=400)
                        return
                    timestamp = datetime.utcnow().isoformat()
                    ip        = self.client_address[0] if self.client_address else ""
                    hash_sig  = calcular_hash_assinatura(nome, cpf, contrato.id, timestamp)
                    assinatura = ContratoAssinatura(
                        contrato_id=contrato.id,
                        parte=parte,
                        nome=nome,
                        cpf=cpf,
                        assinado_em=datetime.utcnow(),
                        ip_origem=ip,
                        hash_sha256=hash_sig,
                    )
                    db.add(assinatura)
                    partes_assinadas = {a.parte for a in contrato.assinaturas} | {parte}
                    if "loja" in partes_assinadas and "cliente" in partes_assinadas:
                        contrato.status = "assinado_loja"
                    elif parte == "loja":
                        contrato.status = "assinado_loja"
                    else:
                        contrato.status = "assinado_cliente"
                    db.commit()
                    # Verificar se ambas as partes assinaram → fechar etapa 7
                    assinaturas = db.query(ContratoAssinatura)\
                                    .filter_by(contrato_id=contrato.id).all()
                    partes_assinadas = {a.parte for a in assinaturas}
                    if {"loja", "cliente"}.issubset(partes_assinadas):
                        contrato.status = "assinado"
                        etapa7 = db.query(CicloEtapa).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="7"
                        ).first()
                        if not etapa7:
                            etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                            db.add(etapa7)
                        etapa7.status        = "concluido"
                        etapa7.concluido_em  = datetime.utcnow()
                        etapa7.responsavel_id = usuario["id"]
                        db.commit()
                        # Cronograma do Ciclo (Modulos_Orizon_v11): D0 = assinatura total do contrato
                        # (mesmo gatilho das Provisões). Constitui data_prevista_conclusao por etapa a
                        # partir do Cronograma de Projeto Padrão (Config). Fail-soft: não bloqueia a
                        # assinatura se algo falhar.
                        try:
                            import mod_cronograma
                            _cfg_crono = _cfg_financeira_loja(db, loja_id)
                            _d0 = datetime.utcnow()
                            mod_cronograma.gerar_cronograma_projeto(db, nome_safe, _cfg_crono, _d0)
                            # Data-limite do Contrato (Fatia 3): D0 + prazo contratual em DIAS ÚTEIS. Só existe
                            # após a assinatura (na geração do contrato ainda não há D0) — registrada aqui para
                            # a Agenda monitorar o esgotamento do prazo conforme as etapas avançam/atrasam.
                            _prazo_du = int(_cfg_crono.get("prazo_contratual_dias_uteis") or 50)
                            _pm_lim = db.get(Projeto, nome_safe)
                            if _pm_lim is not None:
                                _pm_lim.data_limite_contratual = mod_cronograma.somar_dias_uteis(_d0, _prazo_du)
                            db.commit()
                        except Exception as _ec:
                            db.rollback()
                            print("[CRONOGRAMA] gerar_cronograma_projeto falhou:", _ec)
                        # FASE B2 (A6): congela a segmentação Mercadoria × Serviço efetiva no projeto.
                        # A partir da assinatura, NF-e e NFS-e leem os MESMOS percentuais (imune a mudança
                        # do default da loja entre os dois documentos). Sem migração; grava no JSON existente.
                        try:
                            if _congelar_segmentacao_no_projeto(db, loja_id, nome_safe) is not None:
                                db.commit()
                        except Exception as _eseg:
                            db.rollback()
                            print("[SEGMENTACAO] congelar na assinatura falhou:", _eseg)
                        try:
                            upsert_projeto_status(nome_safe, "fechado")
                        except Exception as _e:
                            print("[FECHADO] upsert_projeto_status falhou:", _e)
                        # Montagem da equipe no fechamento (decisão 2026-07-27): persiste os
                        # responsáveis automáticos, apura as lacunas e posta o resumo na conversa
                        # do projeto (gerência vê por oversight). Best-effort — nunca quebra a assinatura.
                        try:
                            import mod_equipe as _meq, mod_chat as _mchat_f
                            _res = _meq.montar_equipe_no_fechamento(db, nome_safe, loja_id)
                            _pm = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                            _conv = _mchat_f.get_or_create_conversa_projeto(
                                db, loja_id, nome_safe, cliente_id=(_pm.cliente_id if _pm else None))
                            # membership: sincroniza os participantes com a equipe derivada (os
                            # auto-designados passam a ver a conversa/o resumo na inbox).
                            _eq = _meq.equipe_do_projeto(db, nome_safe, loja_id)
                            _mchat_f.sincronizar_participantes_projeto(db, _conv, _eq["membros_usuarios"])
                            _falta = ", ".join(l["funcao_nome"] or "?" for l in _res["lacunas"]) or "nenhuma"
                            _summary = _mchat_f.enviar_mensagem(
                                db, _conv, None,
                                "📋 Contrato fechado — equipe montada. Responsáveis automáticos "
                                "definidos: %d. Funções a definir (ação gerencial): %s."
                                % (len(_res["definidos"]), _falta), permitir_vazio=True)
                            # E-mail aos gerentes/diretores QUANDO há lacunas (config-gated: sem SMTP
                            # nasce 'pendente_config', nada é enviado). Os auto-designados já veem o
                            # resumo na inbox (são membros da conversa do projeto).
                            if _res["lacunas"]:
                                try:
                                    import mod_chat_externo as _mce_f
                                    _gers = [{"id": u.id, "email": u.email} for u in db.query(Usuario)
                                             .filter(Usuario.loja_id == loja_id, Usuario.ativo == 1).all()
                                             if (u.email or "").strip()
                                             and perfis.pode(u.nivel, "ver_todas_conversas")]
                                    _corpo_mail = ("Novo projeto contratado: %s.\nFunções a definir "
                                                   "(mais de um candidato): %s.\nAbra o Orizon Chat "
                                                   "para indicar os responsáveis." % (nome_safe, _falta))
                                    _mce_f.notificar_gerentes_email(db, _summary, _gers, _corpo_mail)
                                except Exception as _email:
                                    print("[EQUIPE] e-mail de lacunas falhou:", _email)
                            db.commit()
                        except Exception as _eq:
                            db.rollback(); print("[EQUIPE] montar_equipe_no_fechamento falhou:", _eq)
                    self.send_json({"ok": True, "status": contrato.status, "parte": parte})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/contrato — gera PDF do contrato
            m = _re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                # A validação completa do cadastro do cliente (identificação +
                # endereço) ocorre mais abaixo, após montar cliente_dict, via
                # validar_cliente_para_contrato() — valida o dado realmente renderizado.
                req                  = json.loads(body)
                orcamento_id         = req.get("orcamento_id")
                endereco_instalacao  = (req.get("endereco_instalacao") or "").strip()
                entrada_valor        = float(req.get("entrada_valor") or 0)
                parcelas_descricao   = req.get("parcelas_descricao") or ""
                adendo               = req.get("adendo") or ""
                forma_entrada        = req.get("forma_entrada", "pix")
                forma_parcelas       = req.get("forma_parcelas", "boleto")
                pagamento_json_str   = req.get("pagamento_json", "")
                if not orcamento_id:
                    self.send_json({"ok": False, "erro": "orcamento_id obrigatório"}, code=400)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    # Gate BLOQUEANTE-SUAVE (decisão 13 da spec de chat, mini-frente
                    # 2026-07-25): o ato do contrato exige que o operador tenha VISTO os
                    # contatos de comunicação e escolhido — 'confirmado' ou 'sem_whatsapp'
                    # ("seguir sem WhatsApp"). O codigo específico faz o frontend abrir o
                    # modal de confirmação e tentar de novo; nunca passa sem ver.
                    import mod_chat as _mchat
                    if _mchat.confirmacao_vigente(db, loja_id, nome_safe) is None:
                        self.send_json({"ok": False,
                                        "codigo": "contatos_nao_confirmados",
                                        "erro": "Confirme os contatos de comunicação do "
                                                "projeto antes de gerar o contrato."},
                                       code=400)
                        return
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, orcamento_id, db)
                    # Gate: orçamento precisa ter ao menos um ambiente (1º orçamento concluído).
                    if not orcamento_dict.get("ambientes"):
                        self.send_json({
                            "ok": False,
                            "erro": "O orçamento não tem ambientes. Conclua o primeiro orçamento "
                                    "(com ambientes) antes de aprovar.",
                        }, code=400)
                        return
                    # Signatário alternativo: substitui o cadastro só para este contrato.
                    _override = req.get("signatario_override")
                    if isinstance(_override, dict) and _override.get("nome"):
                        cliente_dict = {**cliente_dict, **{k: v for k, v in _override.items() if v not in (None, "")}}
                    from mod_contrato import construir_contexto
                    from mod_contrato import _formatar_valor
                    from mod_contrato import validar_cliente_para_contrato
                    # Valida os dados que serão de fato renderizados no documento.
                    # Impede gerar contrato com endereço/contato em branco.
                    faltando = validar_cliente_para_contrato(cliente_dict)
                    if faltando:
                        self.send_json({
                            "ok": False,
                            "erro": "Cadastro do cliente incompleto — preencha antes de gerar o contrato. "
                                    "Campos faltando: " + ", ".join(faltando),
                            "campos_faltando": faltando,
                        }, code=400)
                        return
                    from mod_contrato import validar_loja_para_contrato
                    loja_dict = _loja_dict_para_contrato(db, loja_id)
                    faltando_loja = validar_loja_para_contrato(loja_dict)
                    if faltando_loja and not req.get("confirmar_loja_incompleta"):
                        self.send_json({
                            "ok": False,
                            "precisa_confirmar_loja": True,
                            "campos_loja_faltando": faltando_loja,
                            "erro": "Dados da loja incompletos.",
                        }, code=400)
                        return
                    usuario_ctx = {
                        "nome":     usuario.get("nome", ""),
                        "telefone": _get_usuario_telefone(usuario["id"], db),
                        "email":    usuario.get("email", "") or "",
                    }
                    # pagamento_json_str = JSON completo enviado pela aprovação (prioridade)
                    # fallback: forma_pagamento do orçamento (texto curto ou JSON salvo)
                    pag_json = pagamento_json_str or orcamento_dict.get("forma_pagamento", "") or ""
                    variaveis = construir_contexto(
                        cliente_dict,
                        usuario_ctx,
                        pag_json,
                        loja_dict,
                    )
                    variaveis.update({
                        "projeto_nome":    projeto_dict.get("nome_projeto", ""),
                        "orcamento_nome":  orcamento_dict.get("nome", ""),
                        "valor_total":     _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_negociado": _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_liquido":   _formatar_valor(orcamento_dict.get("valor_liquido", 0)),
                        "ambientes_lista": "\n".join(orcamento_dict.get("ambientes", [])),
                        "tem_adendo":      bool(req.get("adendo")),
                        "adendo":          req.get("adendo") or "",
                        "consultor_nome":  usuario.get("nome", ""),
                        "_ambientes":      _ambientes_valor_para_contrato(orcamento_id, db),
                    })
                    variaveis.update(_extras_marcadores_contrato(db, nome_safe, loja_id))
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        contrato = Contrato(projeto_nome=nome_safe, orcamento_id=orcamento_id)
                        db.add(contrato)
                        db.flush()
                    contrato.endereco_instalacao = endereco_instalacao
                    contrato.pagamento_json      = pagamento_json_str
                    contrato.adendo              = adendo
                    contrato.gerado_por_id       = usuario["id"]
                    contrato.status              = "rascunho"
                    if not contrato.loja_id:
                        contrato.loja_id = loja_id
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
                    # Número do contrato (gerado uma vez; mantido em regerações).
                    if not contrato.num_contrato:
                        from mod_contrato import gerar_num_contrato
                        _existing = [c.num_contrato for c in db.query(Contrato)
                                     .filter(Contrato.num_contrato.isnot(None)).all()]
                        contrato.num_contrato = gerar_num_contrato(_existing, loja_dict.get("codigo", ""))
                    variaveis["num_contrato"] = contrato.num_contrato
                    # Fixa a versão do modelo que gerou este contrato: regerar
                    # depois reproduz estas cláusulas mesmo que a loja troque o
                    # modelo. Contrato legado (já gerado, sem versão) fica no
                    # template global. (spec D6)
                    # PRECISA rodar ANTES de marcar gerado_em = utcnow() abaixo:
                    # versao_para_contrato usa contrato.gerado_em (ainda None
                    # aqui p/ contrato novo; já preenchido de uma geração
                    # anterior p/ regeração) para distinguir "nunca gerado"
                    # (adota e fixa o modelo ativo) de "legado" (fica no global).
                    import mod_documentos as _mdoc
                    variaveis["_db"] = db
                    variaveis["_modelo_versao_id"] = _mdoc.versao_para_contrato(
                        db, contrato, contrato.loja_id or loja_id)
                    contrato.gerado_em = datetime.utcnow()
                    db.commit()
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    contrato.status = "para_assinatura"
                    # A geração do contrato conclui a etapa Orçamento (4) — aprovar o
                    # orçamento e gerar o contrato são a mesma transição (Orçamento → Contrato).
                    _set_etapa_status(db, nome_safe, "4", "concluido", usuario["id"])
                    db.commit()
                    # Marcar etapa 7 como "em_andamento" (contrato gerado, aguardando assinatura)
                    etapa7 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="7"
                    ).first()
                    if not etapa7:
                        etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                        db.add(etapa7)
                    etapa7.status = "em_andamento"
                    db.commit()
                    _orc_venda = db.get(Orcamento, contrato.orcamento_id)
                    _registrar_provisao_venda(db, _orc_venda,
                                              por_id=(usuario.get("id") if usuario else None))
                    db.commit()
                    # v6 §6.4: auto-constitui as 3 provisões contábeis (% × valor da venda), fail-soft
                    _fin_provisoes_venda_seguro(_orc_venda, nome_safe, "prov:" + str(contrato.id))
                    resp = {"ok": True, "contrato_id": contrato.id, "status": "para_assinatura"}
                    self.send_json(resp)
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/solicitacao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "registrar_medicao", sessao=usuario)
                    if not u:
                        self.send_json({"ok": False, "erro": "Confirmação exige login+senha do Medidor (ou Diretor)."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo de solicitação de medição."}); return
                    fname, data = arquivos["arquivo"]
                    destino = os.path.join(_projeto_path(nome_safe), "medicao", "solicitacao_" + os.path.basename(fname))
                    storage_salvar_binario(destino, data)
                    md = _get_or_create_medicao(db, nome_safe)
                    md.solicitacao_arquivo = os.path.basename(destino)
                    md.solicitacao_por = u.id
                    md.solicitacao_em = datetime.utcnow()
                    _set_etapa_status(db, nome_safe, "9", "concluido", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="medicao_solicitacao", projeto_nome=nome_safe, etapa_alvo="9"))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/parecer$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                parecer = (campos.get("parecer","") or "").strip().lower()
                ambientes = campos.get("ambientes_aprovados","")
                erros = mod_medicao.validar_parecer(parecer, ambientes)
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)}); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    _blk = _bloqueio_execucao_etapa(db, nome_safe, loja_id, "10")   # gate: medição precisa de nome
                    if _blk:
                        self.send_json({"ok": False, "erro": _blk}, code=409); return
                    u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "registrar_medicao", sessao=usuario)
                    if not u:
                        self.send_json({"ok": False, "erro": "Registro exige login+senha do Medidor (ou Diretor)."}, code=403); return
                    if "planta" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo promob da Planta de Pontos Medidos."}); return
                    fname, data = arquivos["planta"]
                    destino = os.path.join(_projeto_path(nome_safe), "medicao", "planta_" + os.path.basename(fname))
                    storage_salvar_binario(destino, data)
                    md = _get_or_create_medicao(db, nome_safe)
                    md.planta_arquivo = os.path.basename(destino)
                    md.parecer = parecer
                    md.ambientes_aprovados = ambientes.strip() if parecer == "parcial" else None
                    md.medidor_id = u.id
                    md.medicao_em = datetime.utcnow()
                    if parecer in ("aprovado", "parcial"):
                        _set_etapa_status(db, nome_safe, "10", "concluido", u.id)
                    else:
                        _set_etapa_status(db, nome_safe, "10", "em_andamento", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="medicao_parecer_" + parecer, projeto_nome=nome_safe, etapa_alvo="10"))
                    db.commit()
                    self.send_json({"ok": True, "parecer": parecer})
                finally:
                    db.close()
                return

            m = _re.match(r'^/api/projetos/([^/]+)/medicao/decisao-reprovado$', path)
            if m:
                nome_safe = unquote(m.group(1))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    if not md or md.parecer != "reprovado":
                        self.send_json({"ok": False, "erro": "Só aplicável a uma medição com parecer Reprovado."}); return
                    u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "aprovar_medicao_reprovada", sessao=solicitante)
                    if not u:
                        self.send_json({"ok": False, "erro": "Liberação exige login+senha de Gerente de Vendas, Gerente Adm/Financeiro ou Diretor."}, code=403); return
                    if "doc_cliente" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o documento de aprovação do cliente."}); return
                    fname, data = arquivos["doc_cliente"]
                    destino = os.path.join(_projeto_path(nome_safe), "medicao", "doc_cliente_" + os.path.basename(fname))
                    storage_salvar_binario(destino, data)
                    md.doc_cliente_arquivo = os.path.basename(destino)
                    md.excecao_por = u.id
                    md.excecao_em = datetime.utcnow()
                    _set_etapa_status(db, nome_safe, "10", "concluido", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=solicitante["id"], autorizador_id=u.id,
                            acao="medicao_excecao_reprovado", projeto_nome=nome_safe, etapa_alvo="10"))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/documento — upload append-only (PE)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/documento$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    _blk = _bloqueio_execucao_etapa(db, nome_safe, loja_id, "11")   # gate: PE precisa do responsável
                    if _blk:
                        self.send_json({"ok": False, "erro": _blk}, code=409); return
                    tipo_esperado = mod_ciclo.tipo_doc_de(codigo)
                    if not tipo_esperado:
                        self.send_json({"ok": False, "erro": "Subfase de PE inválida."}, code=400); return
                    u = _usuario_com_capacidade(db, campos.get("login", ""), campos.get("senha", ""), "executar_pe", sessao=usuario)
                    if not u:
                        self.send_json({"ok": False, "erro": "Ação exige login+senha de Projetista Executivo, Conferente, Gerente ou Diretor."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo_esperado,
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=u.id)
                    db.add(doc)
                    _chat_registrar_documento(db, nome_safe, loja_id, doc, u.id)
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, codigo, "em_andamento", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="pe_documento_" + tipo_esperado, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    # rollback é no-op se o commit já ocorreu (linha do doc persiste; o
                    # download degrada com 404 se o arquivo não foi para o disco).
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/pedido-xml — upload XML da etapa
            # operacional (12), append-only, CYCLE-GATED (sem capability de PE).
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/pedido-xml$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    _blk = _bloqueio_execucao_etapa(db, nome_safe, loja_id, codigo)   # gate de execução
                    if _blk:
                        self.send_json({"ok": False, "erro": _blk}, code=409); return
                    tipo_esperado = mod_ciclo.tipo_doc_operacional(codigo)
                    if not tipo_esperado:
                        self.send_json({"ok": False, "erro": "Esta etapa não aceita upload de pedidos."}, code=400); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo XML."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo_esperado,
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=usuario["id"])
                    db.add(doc)
                    _chat_registrar_documento(db, nome_safe, loja_id, doc, usuario["id"])
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, codigo, "em_andamento", usuario["id"])
                    db.add(LogAcaoGerencial(solicitante_id=usuario["id"], autorizador_id=usuario["id"],
                            acao="ciclo_" + tipo_esperado, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe-fabrica — upload da NF-e da fábrica
            # (etapa 15), append-only, gated por capacidade fiscal (editar_dados_loja).
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe-fabrica$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o XML da NF-e da fábrica."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", "15", unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo="15", tipo="nfe_fabrica_xml",
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=usuario["id"])
                    db.add(doc)
                    _chat_registrar_documento(db, nome_safe, loja_id, doc, usuario["id"])
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="15").first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, "15", "em_andamento", usuario["id"])
                    db.add(LogAcaoGerencial(solicitante_id=usuario["id"], autorizador_id=usuario["id"],
                            acao="ciclo_nfe_fabrica_xml", projeto_nome=nome_safe, etapa_alvo="15"))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/revisao — revisão + reabertura em cascata
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/revisao$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    sf = mod_ciclo.SUBFASES_PE.get(codigo)
                    if not sf or not sf["revisavel"]:
                        self.send_json({"ok": False, "erro": "Esta subfase não permite revisão."}, code=400); return
                    u = _usuario_com_capacidade(db, campos.get("login", ""), campos.get("senha", ""), "revisar_pe", sessao=solicitante)
                    if not u:
                        self.send_json({"ok": False, "erro": "Revisão exige login+senha de Gerente de Vendas, Gerente Adm/Financeiro ou Diretor."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o relatório complementar (obrigatório)."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo="pe_relatorio_complementar",
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=u.id)
                    db.add(doc); db.flush()   # doc.id para a revisão
                    _chat_registrar_documento(db, nome_safe, loja_id, doc, u.id)
                    todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    codigos = [e.etapa_codigo for e in todas]
                    resetar = mod_ciclo.codigos_a_resetar(codigo, codigos)
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe).order_by(Contrato.id.desc()).first()
                    cstatus = contrato.status if contrato else ""
                    if mod_ciclo.reabertura_bloqueada_por_contrato(resetar, cstatus):
                        self.send_json({"ok": False, "erro": "Contrato já assinado — não é possível revisar esta etapa"}, code=400); return
                    resetar_set = set(resetar)
                    status_anterior = {e.etapa_codigo: e.status for e in todas
                                       if e.etapa_codigo in resetar_set}
                    for e in todas:
                        if e.etapa_codigo in resetar_set:
                            e.status = "pendente"; e.iniciado_em = None; e.concluido_em = None; e.responsavel_id = None
                    # a etapa-mãe 11 volta a "em andamento" (PE deixou de estar concluído).
                    # _set_etapa_status cria/atualiza a linha, mas não zera concluido_em/responsavel_id
                    # ao sair de "concluido" — limpamos aqui para não deixar carimbo obsoleto.
                    e11 = _set_etapa_status(db, nome_safe, "11", "em_andamento", u.id)
                    e11.concluido_em = None; e11.responsavel_id = None
                    rev = CicloRevisao(projeto_nome=nome_safe, etapa_codigo=codigo, aberta_por_id=u.id,
                                       relatorio_doc_id=doc.id, motivo=(campos.get("motivo") or None))
                    db.add(rev)
                    db.add(LogAcaoGerencial(solicitante_id=solicitante["id"], autorizador_id=u.id,
                            acao="pe_revisao", projeto_nome=nome_safe, etapa_alvo=codigo,
                            contexto=json.dumps({"resetadas": sorted(resetar_set),
                                                 "status_anterior": status_anterior})))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "resetadas": sorted(resetar_set)})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/<codigo>/concluir — fecha a subfase de PE
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/concluir$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    _blk = _bloqueio_execucao_etapa(db, nome_safe, loja_id, "11")   # gate: PE precisa do responsável
                    if _blk:
                        self.send_json({"ok": False, "erro": _blk}, code=409); return
                    if codigo not in mod_ciclo.SUBFASES_PE:
                        self.send_json({"ok": False, "erro": "Subfase de PE inválida."}, code=400); return
                    req = json.loads(body or b'{}')
                    u = _usuario_com_capacidade(db, req.get("login", ""), req.get("senha", ""), "executar_pe", sessao=usuario)
                    if not u:
                        self.send_json({"ok": False, "erro": "Ação exige login+senha de Projetista Executivo, Conferente, Gerente ou Diretor."}, code=403); return
                    docs = db.query(CicloDocumento).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).all()
                    tipos_presentes = {d.tipo for d in docs}
                    todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    status_por = {e.etapa_codigo: e.status for e in todas}
                    pe_amb = None
                    if codigo == "11c":   # PE por ambiente (tabela de comparação) substitui o doc único
                        # Universo = ambientes do ORÇAMENTO DO CONTRATO (o que foi vendido e o que a
                        # 11c exibe). Ambiente de pool fora do orçamento (removido antes da assinatura)
                        # não trava a conclusão — não aparece na tabela nem tem upload (QA Vera).
                        ct = (db.query(Contrato).filter_by(projeto_nome=nome_safe)
                                .order_by(Contrato.id.desc()).first())
                        ids_orc = ({oa.pool_ambiente_id for oa in
                                    db.query(OrcamentoAmbiente).filter_by(orcamento_id=ct.orcamento_id).all()}
                                   if ct is not None else set())
                        if ids_orc:
                            com_pe = (db.query(ArquivoPE.pool_ambiente_id)
                                        .filter_by(projeto_nome=nome_safe)
                                        .filter(ArquivoPE.pool_ambiente_id.in_(ids_orc))
                                        .distinct().count())
                            pe_amb = (len(ids_orc), com_pe)
                        else:   # sem contrato/orçamento (legado) → pool inteiro, como antes
                            total = db.query(PoolAmbiente).filter_by(projeto_id=nome_safe).count()
                            com_pe = (db.query(ArquivoPE.pool_ambiente_id)
                                        .filter_by(projeto_nome=nome_safe).distinct().count())
                            pe_amb = (total, com_pe)
                    aprov_ok = None
                    if codigo == mod_ciclo.PE_SUBFASE_FINAL:
                        # correção Fatia 3: a 11e conclui com a Aprovação do PE ASSINADA
                        # (doc legado pe_pe_assinado segue valendo — retrocompat no guard)
                        _ap = (db.query(AprovacaoPE).filter_by(projeto_nome=nome_safe)
                                 .order_by(AprovacaoPE.id.desc()).first())
                        aprov_ok = bool(_ap is not None and _ap.status == "assinado")
                    ok, erro = mod_ciclo.guarda_conclusao(codigo, tipos_presentes, status_por,
                                                          pe_ambientes=pe_amb,
                                                          aprovacao_pe=aprov_ok)
                    if not ok:
                        self.send_json({"ok": False, "erro": erro}, code=400); return
                    _set_etapa_status(db, nome_safe, codigo, "concluido", u.id)
                    if codigo == mod_ciclo.PE_SUBFASE_FINAL:
                        _set_etapa_status(db, nome_safe, "11", "concluido", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="pe_concluir_" + codigo, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/admin/lojas/<id>/nfe/emitir-teste — emissão de teste (homologação)
            m = _re.match(r'^/api/admin/lojas/(\d+)/nfe/emitir-teste$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                from fiscal import mod_nfe, mapa_fiscal, nfe_emissao, mod_fiscal
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    try:
                        emitente = mod_fiscal.resolver_emitente(db, loja, "produto")
                    except ValueError as e:
                        self.send_json({"ok": False, "erro": str(e)}, code=400); return
                    _pront = mod_fiscal.prontidao_emitente(emitente, "produto")
                    if _pront:
                        self.send_json({"ok": False, "erro": _pront}, code=400); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o XML da fábrica."}, code=400); return
                    projeto_nome = campos.get("projeto_nome")
                    projeto = db.get(Projeto, projeto_nome) if projeto_nome else None
                    if not projeto:
                        self.send_json({"ok": False, "erro": "Informe um projeto válido da loja."}, code=400); return
                    if projeto.loja_id != loja.id:
                        self.send_json({"ok": False, "erro": "O projeto não pertence a esta loja."}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    try:
                        markup = float(campos.get("markup_pct") or 0)
                    except ValueError:
                        markup = 0.0
                    _fname, data = arquivos["arquivo"]
                    preview = mod_nfe.preview(data, markup)
                    ref = "TESTE-" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    nota = mapa_fiscal.montar_nota(emitente, cliente, preview["itens"], ref, data_emissao)
                    res = nfe_emissao.emitir(db, loja.id, projeto_nome, nota, tipo_documento="produto",
                                             emitente_id=emitente.id)
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value if hasattr(res.status, "value") else res.status,
                                    "chave": res.chave, "numero": res.numero, "serie": res.serie,
                                    "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": reg.xml_doc_id if reg else None,
                                    "danfe_doc_id": reg.danfe_doc_id if reg else None})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/admin/lojas/<id>/modulos — grava topologia (domínios ativos).
            # ativos=None religa tudo; senão valida cada item ∈ modulos.DOMINIOS. Gated como o GET.
            m = _re.match(r'^/api/admin/lojas/(\d+)/modulos$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                import modulos as _mod
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    ativos = req.get("ativos")
                    if ativos is None:
                        loja.modulos_ativos = None
                    else:
                        if not isinstance(ativos, list):
                            self.send_json({"ok": False, "erro": "ativos deve ser lista ou null"}, code=400); return
                        invalidos = [x for x in ativos if x not in _mod.DOMINIOS]
                        if invalidos:
                            self.send_json({"ok": False, "erro": "Módulo(s) inválido(s): %s" % ", ".join(map(str, invalidos))}, code=400); return
                        _ok, _msg = _mod.topologia_valida(ativos)
                        if not _ok:
                            self.send_json({"ok": False, "erro": _msg}, code=400); return
                        loja.modulos_ativos = json.dumps(list(ativos))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/emitir-nfe — emite a NF-e da loja
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/emitir-nfe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                from fiscal import mod_nfe, mapa_fiscal, nfe_emissao, mod_fiscal
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    projeto = _projeto_da_loja(db, nome_safe, loja_id)
                    if projeto is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    loja = db.get(Loja, loja_id)
                    try:
                        emitente = mod_fiscal.resolver_emitente(db, loja, "produto")
                    except ValueError as e:
                        self.send_json({"ok": False, "erro": str(e)}, code=400); return
                    _pront = mod_fiscal.prontidao_emitente(emitente, "produto")
                    if _pront:
                        self.send_json({"ok": False, "erro": _pront}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    # Contribuinte exige Inscrição Estadual na NF-e. Se ainda não estiver cadastrada,
                    # coleta a IE do body no ato da emissão e persiste no Cliente.
                    if (cliente.tipo_dest == "contribuinte") and not (cliente.inscricao_estadual or "").strip():
                        ie = (req.get("ie") or "").strip()
                        if not ie:
                            self.send_json({"ok": False, "erro": "Informe a Inscrição Estadual do cliente para emitir a NF-e (contribuinte)."}, code=400); return
                        cliente.inscricao_estadual = ie
                        db.add(cliente); db.commit()
                    doc_id = req.get("fabrica_doc_id")
                    doc = db.query(CicloDocumento).filter_by(id=doc_id, projeto_nome=nome_safe,
                                                             etapa_codigo="15", tipo="nfe_fabrica_xml").first() if doc_id else None
                    if not doc:
                        self.send_json({"ok": False, "erro": "XML da fábrica inválido."}, code=400); return
                    try:
                        markup = float(req.get("markup_pct") or 0)
                    except (TypeError, ValueError):
                        markup = 0.0   # markup inválido → custo (aceitável: emissão só em homologação por padrão)
                    xml_bytes = storage_ler_binario(os.path.join(_projeto_path(nome_safe), doc.arquivo_path))
                    preview = mod_nfe.preview(xml_bytes, markup)
                    # FASE B2.3 (T4): alinhar a FACE da NF-e à parcela Mercadoria (pct_merc × Val_Cont) —
                    # reescala os itens reais da fábrica p/ Σ = parcela Mercadoria (o total é governado pelo
                    # Val_Cont, já líquido do desconto; markup vira output do rateio). Sem contrato/Val_Cont
                    # (venda avulsa/teste) → mantém o markup (fallback). ICMS/alíquotas definitivos ficam p/
                    # a frente Fiscal (contador) — o reescalonamento muda a base por item, é consequência.
                    _vseg = _valores_segmentados_do_projeto(db, loja_id, nome_safe)
                    if _vseg is not None:
                        preview["itens"] = mod_nfe.rescalar_itens_para_total(preview["itens"], _vseg["mercadoria"])
                    ref = "NFE-" + nome_safe + "-" + str(doc.id)
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    nota = mapa_fiscal.montar_nota(emitente, cliente, preview["itens"], ref, data_emissao)
                    res = nfe_emissao.emitir(db, loja_id, nome_safe, nota, tipo_documento="produto",
                                             emitente_id=emitente.id, fabrica_doc_id=doc.id)
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                        # wiring: NF-e produto autorizada = faturamento da MERCADORIA (4.1.01) + CMV=CFO
                        # (FASE B2, receita segmentada — valor contábil = parcela Mercadoria do Val_Cont).
                        _fin_faturamento_segmentado_seguro(loja_id, nome_safe, "mercadoria", ref)
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value, "chave": res.chave, "numero": res.numero,
                                    "serie": res.serie, "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": reg.xml_doc_id if reg else None,
                                    "danfe_doc_id": reg.danfe_doc_id if reg else None})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/emitir-nfse — emite a NFS-e (serviço, valor manual)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/emitir-nfse$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                from fiscal import mapa_fiscal, nfe_emissao, mod_fiscal
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    projeto = _projeto_da_loja(db, nome_safe, loja_id)
                    if projeto is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    loja = db.get(Loja, loja_id)
                    try:
                        emitente = mod_fiscal.resolver_emitente(db, loja, "servico")
                    except ValueError as e:
                        self.send_json({"ok": False, "erro": str(e)}, code=400); return
                    _pront = mod_fiscal.prontidao_emitente(emitente, "servico")
                    if _pront:
                        self.send_json({"ok": False, "erro": _pront}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    # IBGE do tomador é obrigatório para a NFS-e (L999 "Tomador Não Identificado").
                    # Clientes novos já capturam via ViaCEP no cadastro; para os antigos, backfill best-effort.
                    # Consistência (auditoria A11): alinha cidade/UF à MESMA fonte (ViaCEP) que define o IBGE,
                    # senão o tomador iria com município textual divergente do código IBGE.
                    if not (cliente.municipio_ibge or "").strip() and (cliente.cep or "").strip():
                        end = _endereco_por_cep(cliente.cep)
                        if end:
                            cliente.municipio_ibge = end["ibge"]
                            if end.get("cidade"): cliente.cidade = end["cidade"]
                            if end.get("uf"):     cliente.estado = end["uf"]
                            db.commit()
                    try:
                        valor = float(req.get("valor_servico") or 0)
                    except (TypeError, ValueError):
                        valor = 0.0
                    if valor <= 0:
                        self.send_json({"ok": False, "erro": "Informe o valor do serviço."}, code=400); return
                    # NFS-e por TENTATIVA: um RPS rejeitado é "morto" (a Focus deduplica por ref), então
                    # re-emitir usa um ref novo (NFSE-<projeto>-<n>). Se a última tentativa já está
                    # autorizada, é idempotente (não emite de novo). Corrige o beco-sem-saída da auditoria (A4).
                    nfse_regs = (db.query(DocumentoFiscal)
                                   .filter_by(projeto_nome=nome_safe, tipo_documento="servico")
                                   .order_by(DocumentoFiscal.id.asc()).all())
                    # Idempotente enquanto a última está autorizada OU ainda processando (evita 2ª nota
                    # antes de a 1ª resolver). Só rejeitada/cancelada libera uma nova tentativa.
                    if nfse_regs and nfse_regs[-1].status in ("autorizado", "processando"):
                        reg = nfse_regs[-1]
                        if reg.status == "autorizado":   # NFS-e autorizada conclui a etapa 15 (A14)
                            _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                        self.send_json({"ok": True, "ref": reg.ref, "status": reg.status,
                                        "chave": reg.chave_nfe, "numero": reg.numero, "serie": reg.serie,
                                        "mensagem_sefaz": reg.mensagem_sefaz,
                                        "erros": json.loads(reg.erros_json) if reg.erros_json else [],
                                        "xml_doc_id": reg.xml_doc_id, "danfe_doc_id": reg.danfe_doc_id}); return
                    ref = "NFSE-%s-%d" % (nome_safe, len(nfse_regs) + 1)
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    discriminacao = req.get("discriminacao") or "Serviço de montagem/instalação de móveis planejados"
                    # FASE B2.3 (T4): valor da NFS-e = parcela Serviço (pct_serv × Val_Cont), complemento da
                    # NF-e produto (juntos fecham o Val_Cont). Sem contrato/Val_Cont → mantém o valor informado.
                    _vseg = _valores_segmentados_do_projeto(db, loja_id, nome_safe)
                    _valor_nfse = _vseg["servico"] if _vseg is not None else round(valor, 2)
                    nota = mapa_fiscal.montar_nota_nfse(emitente, cliente, _valor_nfse, ref, data_emissao, discriminacao)
                    res = nfe_emissao.emitir(db, loja_id, nome_safe, nota, tipo_documento="servico",
                                             emitente_id=emitente.id)
                    # NFS-e autorizada conclui a etapa 15, como a NF-e de produto (auditoria A14).
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                        # wiring: NFS-e (serviço) autorizada = faturamento do SERVIÇO (4.2.01)
                        # (FASE B2 — valor contábil = parcela Serviço do Val_Cont, não o valor de face).
                        _fin_faturamento_segmentado_seguro(loja_id, nome_safe, "servico", ref)
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value, "chave": res.chave, "numero": res.numero,
                                    "serie": res.serie, "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": reg.xml_doc_id if reg else None,
                                    "danfe_doc_id": reg.danfe_doc_id if reg else None})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe/consultar
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe/consultar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                from fiscal import nfe_emissao
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    ref = req.get("ref")
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    if not reg or reg.projeto_nome != nome_safe:   # a NF-e tem de pertencer a este projeto (evita cross-tenant via ref do body)
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    res = nfe_emissao.consultar(db, ref)
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                    self.send_json({"ok": True, "status": res.status.value, "chave": res.chave,
                                    "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe/cancelar
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe/cancelar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                from fiscal import nfe_emissao
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    ref = req.get("ref")
                    reg = db.query(DocumentoFiscal).filter_by(ref=ref).first()
                    if not reg or reg.projeto_nome != nome_safe:   # a NF-e tem de pertencer a este projeto (evita cross-tenant via ref do body)
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    res = nfe_emissao.cancelar(db, ref, req.get("justificativa") or "")
                    if res.status.value == "cancelado":
                        # nota cancelada → etapa 15 volta a não-conclusiva (não deixar "emitida" com NF-e cancelada)
                        _set_etapa_status(db, nome_safe, "15", "em_andamento", usuario["id"]); db.commit()
                    self.send_json({"ok": True, "status": res.status.value, "mensagem_sefaz": res.mensagem_sefaz})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            else:
                self.send_response(404)
                self.end_headers()

    def do_PUT(self):
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
        path   = urlparse(self.path).path
        body   = self._ler_body()
        if body is None: return   # 413 já respondido pelo _ler_body

        # ── PUT /api/financeiro/contas/<id> (renomear/reordenar) ──────────────
        m_conta = re.match(r"^/api/financeiro/contas/(\d+)$", path)
        if m_conta:
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body) if body else {}
                r = mod_contabil.editar_conta(db, ot, oid, int(m_conta.group(1)),
                                              nome=dd.get("nome"), ordem=dd.get("ordem"))
                self.send_json({"ok": True, "conta": r})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except ValueError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=400)
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/config-financeira ───────────────────────
        m_cfg = re.match(r"^/api/admin/lojas/(\d+)/config-financeira$", path)
        if m_cfg:
            import mod_provisoes
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            erros = mod_provisoes.validar_config_financeira(req)
            if erros:
                self.send_json({"ok": False, "erro": " ".join(erros)}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_cfg.group(1)))
                if not loja or not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Loja fora do escopo"}, code=403); return
                loja.config_financeira_json = json.dumps(req, ensure_ascii=False)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal — config não-secreta ──────
        m_pf = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal$", path)
        if m_pf:
            from fiscal import mod_fiscal
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            ok, erro = mod_fiscal.validar_config(req)
            if not ok:
                self.send_json({"ok": False, "erro": erro}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_pf.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "loja", loja)
                if not em:
                    em = _fiscal_criar_emitente(db, loja, attr, loja.rede_id)
                _fiscal_put_config(em, req)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-fiscal — config do Emitente central ──
        m_rpf = re.match(r"^/api/admin/redes/(\d+)/perfil-fiscal$", path)
        if m_rpf:
            from fiscal import mod_fiscal
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            ok, erro = mod_fiscal.validar_config(req)
            if not ok:
                self.send_json({"ok": False, "erro": erro}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_rpf.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "rede", rede)
                if not em:
                    em = _fiscal_criar_emitente(db, rede, attr, rede.id)
                _fiscal_put_config(em, req)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal/segredos — write-only, cifrado ──
        m_seg = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal/segredos$", path)
        if m_seg:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_seg.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "loja", loja)
                if not em:
                    em = _fiscal_criar_emitente(db, loja, attr, loja.rede_id)
                _fiscal_put_segredos(em, req)
                db.commit()
                self.send_json({"ok": True})
            except Exception:
                db.rollback()
                self.send_json({"ok": False, "erro": "Falha ao salvar segredos"}, code=500)
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-fiscal/segredos — write-only, cifrado ──
        m_rseg = re.match(r"^/api/admin/redes/(\d+)/perfil-fiscal/segredos$", path)
        if m_rseg:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_rseg.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "rede", rede)
                if not em:
                    em = _fiscal_criar_emitente(db, rede, attr, rede.id)
                _fiscal_put_segredos(em, req)
                db.commit()
                self.send_json({"ok": True})
            except Exception:
                db.rollback()
                self.send_json({"ok": False, "erro": "Falha ao salvar segredos"}, code=500)
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal/ambiente — troca explícita ──
        m_amb = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal/ambiente$", path)
        if m_amb:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            amb = req.get("ambiente")
            if amb not in ("homologacao", "producao"):
                self.send_json({"ok": False, "erro": "ambiente inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_amb.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "loja", loja)
                if not em:
                    em = _fiscal_criar_emitente(db, loja, attr, loja.rede_id)
                ok, erro = _fiscal_put_ambiente(em, amb)
                if not ok:
                    self.send_json({"ok": False, "erro": erro}, code=400); return
                db.commit()
                self.send_json({"ok": True, "ambiente_ativo": amb})
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-fiscal/ambiente — troca explícita ──
        m_ramb = re.match(r"^/api/admin/redes/(\d+)/perfil-fiscal/ambiente$", path)
        if m_ramb:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            amb = req.get("ambiente")
            if amb not in ("homologacao", "producao"):
                self.send_json({"ok": False, "erro": "ambiente inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_ramb.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                em, attr = _emitente_do_dono(db, "rede", rede)
                if not em:
                    em = _fiscal_criar_emitente(db, rede, attr, rede.id)
                ok, erro = _fiscal_put_ambiente(em, amb)
                if not ok:
                    self.send_json({"ok": False, "erro": erro}, code=400); return
                db.commit()
                self.send_json({"ok": True, "ambiente_ativo": amb})
            finally:
                db.close()
            return

        # ── PUT /api/admin/redes/<id>/perfil-emissao — default de emissão da rede ──
        m_pemr = re.match(r"^/api/admin/redes/(\d+)/perfil-emissao$", path)
        if m_pemr:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                rid = int(m_pemr.group(1))
                rede = db.get(Rede, rid)
                if not rede:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_rede(ator, rid):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                payload, code = _perfil_emissao_put(db, "rede", rid, rede, req)
                self.send_json(payload, code=code)
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-emissao — override de emissão da loja ──
        m_peml = re.match(r"^/api/admin/lojas/(\d+)/perfil-emissao$", path)
        if m_peml:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_peml.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                payload, code = _perfil_emissao_put(db, "loja", loja.id, loja, req)
                self.send_json(payload, code=code)
            finally:
                db.close()
            return

        # ── PUT /projetos/<nome_safe>/orcamentos/<oid> — renomear orçamento ───
        m = re.match(r"^/projetos/([^/]+)/orcamentos/(\d+)$", path)
        if m:
            nome_safe = m.group(1)
            oid       = int(m.group(2))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            try:
                req = json.loads(body)
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"})
                return
            novo_nome = (req.get("nome") or "").strip()
            if not novo_nome:
                self.send_json({"ok": False, "erro": "Nome não pode ser vazio"})
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None or orc.projeto_id != nome_safe:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                if _contrato_assinado(nome_safe, db):
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                orc.nome       = novo_nome
                orc.updated_at = datetime.now()
                db.commit()
                db.refresh(orc)
                self.send_json({"ok": True, "orcamento": _orcamento_dict(orc)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return

        # ── PUT /api/orcamentos/<id>/descontos — descontos individuais em lote ──
        m_desc = re.match(r"^/api/orcamentos/(\d+)/descontos$", path)
        if m_desc:
            oid = int(m_desc.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                from mod_orcamento_params import sanear_descontos
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                pares = req.get("descontos", req)   # aceita {"descontos":{...}} ou {...}
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                # Orçamento de AJUSTE (Fatia 3 PE) é isento das travas de aprovação/assinatura —
                # contratar o complemento pós-contrato é a razão de ele existir (11e Negociar Complemento).
                if not getattr(orc, "complemento_pe", 0):
                    if _projeto_esta_bloqueado(orc.projeto_id):
                        self.send_json({"ok": False,
                                        "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."},
                                       code=400)
                        return
                    if _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()
                ids_validos = {lk.pool_ambiente_id for lk in links}
                limpos = sanear_descontos(pares, ids_validos)
                by_id = {lk.pool_ambiente_id: lk for lk in links}
                for pid, pct in limpos.items():
                    by_id[pid].desconto_individual_pct = pct
                db.commit()
                try:
                    _recalcular_orcamento(orc, db); db.commit()
                    self.send_json({"ok": True, "sombra": _negociacao_breakdown(orc, db)})
                except Exception as _e:
                    db.rollback()
                    self.send_json({"ok": True, "sombra": None, "erro_sombra": str(_e)})
                return
            except ValueError as ve:
                db.rollback()
                self.send_json({"ok": False, "erro": str(ve)}, code=400)
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        # ── PUT /api/orcamentos/<id>/out-forn — editar outros fornecedores ──
        m_out = re.match(r"^/api/orcamentos/(\d+)/out-forn$", path)
        if m_out:
            oid = int(m_out.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                    return
                try:
                    orc.out_forn = max(0.0, float(req.get("out_forn") or 0))
                except (TypeError, ValueError):
                    self.send_json({"ok": False, "erro": "Valor inválido"}, code=400)
                    return
                db.commit()
                self.send_json({"ok": True, "sombra": _negociacao_breakdown(orc, db)})
                return
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return

        self.send_response(404)
        self.end_headers()

    def do_PATCH(self):
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
        try:
            path = urlparse(self.path).path
            body = self._ler_body()
            if body is None: return   # 413 já respondido pelo _ler_body

            # ── Adiantamentos: editar (abater/quitado/valor/competência) ou remover (Fase 5) ──
            m = re.match(r'^/api/adiantamentos/(\d+)$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    a = db.query(AdiantamentoFuncionario).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                    if a is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    r = json.loads(body or b'{}')
                    if r.get("remover"):
                        db.delete(a); db.commit()
                        self.send_json({"ok": True, "removido": True}); return
                    if "abater" in r:            a.abater = 1 if r["abater"] else 0
                    if "quitado" in r:           a.quitado = 1 if r["quitado"] else 0
                    if "valor" in r:             a.valor = float(r["valor"] or 0.0)
                    if "competencia_abate" in r: a.competencia_abate = r["competencia_abate"] or None
                    db.commit()
                    self.send_json({"ok": True, "id": a.id, "abater": bool(a.abater),
                                    "quitado": bool(a.quitado), "valor": a.valor})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # ── Comissão: editar base ajustada de um item e recalcular valor (Fase 4) ──
            m = re.match(r'^/api/comissao/(\d+)$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_comissao
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    it = db.query(ComissaoFolha).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                    if it is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    base = float((json.loads(body or b'{}')).get("base_ajustada") or 0.0)
                    ok, err = mod_comissao.editar_item(db, it, base)
                    if not ok:
                        self.send_json({"ok": False, "erro": err}, code=409); return
                    db.commit()
                    self.send_json({"ok": True, "id": it.id, "base_ajustada": it.base_ajustada, "valor": it.valor})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            # ── Folha de Pagamento: editar base da comissão e recalcular (Fase 3) ──
            m = re.match(r'^/api/folha/(\d+)$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    reg = db.query(FolhaPagamento).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                    if reg is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    base = float((json.loads(body or b'{}')).get("base_comissao") or 0.0)
                    cfg = _cfg_financeira_loja(db, loja_id)
                    ok, err = mod_folha.editar_base(db, loja_id, reg, base, cfg)
                    if not ok:
                        self.send_json({"ok": False, "erro": err}, code=409); return
                    db.commit()
                    self.send_json(mod_folha.serialize(db, reg))
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = re.match(r'^/orcamentos/(\d+)/valor$', path)
            if m:
                oid = int(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req = json.loads(body)
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    if orc and not getattr(orc, "complemento_pe", 0) and _contrato_assinado(orc.projeto_id, db):
                        # ajuste (Fatia 3 PE) segue editável pós-assinatura
                        self.send_json({"ok": False,
                                        "erro": "Contrato assinado — alterações não permitidas."},
                                       code=403)
                        return
                    # backend autoritativo: NÃO aceita valor_total/valor_liquido do frontend
                    if "forma_pagamento" in req:
                        _fp_novo = req["forma_pagamento"] or None
                        # cinto de segurança: plano com parcela/entrada negativa nunca persiste
                        # (ex.: Total Flex digitado p/ um total que mudou — ambiente removido)
                        if _fp_novo:
                            try:
                                _fp_d = json.loads(_fp_novo)
                            except Exception:
                                _fp_d = None   # legado texto curto — aceito
                            from mod_fin import validar_plano_pagamento as _vpp
                            _err_fp = _vpp(_fp_d)
                            if _err_fp:
                                self.send_json({"ok": False, "erro": _err_fp}, code=400)
                                return
                        orc.forma_pagamento = _fp_novo
                    if "negociacao_json" in req:
                        orc.negociacao_json = req["negociacao_json"] or None
                    orc.updated_at = datetime.utcnow()
                    db.flush()                      # forma_pagamento disponível para o recálculo
                    try:
                        _recalcular_orcamento(orc, db)
                    except Exception as _e:
                        print("[CUTOVER] recalculo no PATCH falhou:", _e)
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = re.match(r'^/api/projetos/([^/]+)/status$', path)
            if m:
                nome_safe = unquote(m.group(1))
                req = json.loads(body)
                novo_status = (req.get('status') or '').strip().lower()
                VALIDOS = {'quente', 'morno', 'frio', 'perdido'}
                if novo_status not in VALIDOS:
                    self.send_json({"ok": False, "erro": f"Status inválido. Use: {', '.join(sorted(VALIDOS))}"})
                    return
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                _db_scope = get_session()
                try:
                    ator = _ator_dict(_db_scope, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(_db_scope, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    _assinado = _contrato_assinado(nome_safe, _db_scope)
                finally:
                    _db_scope.close()
                if _assinado:
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
                upsert_projeto_status(nome_safe, novo_status)
                self.send_json({"ok": True, "status": novo_status})
                return

            m = re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)$', path)
            if m:
                nome_safe   = unquote(m.group(1))
                etapa_cod   = unquote(m.group(2))
                usuario     = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req = json.loads(body)
                novo_status = req.get("status", "").strip()
                obs         = req.get("observacoes")
                if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and etapa_cod in ("9", "10"):
                    self.send_json({"ok": False, "erro": "Use o fluxo de Medição para concluir esta etapa."}, code=400)
                    return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    etapa = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo=etapa_cod
                    ).first()
                    if not etapa:
                        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=etapa_cod)
                        db.add(etapa)
                    # Gating sequencial + BLOQUEADOR do chat (Fatia 3, spec seção 3): uma
                    # transferência bloqueadora não resolvida trava a etapa (ou o ciclo
                    # inteiro, quando veio sem etapa) mesmo com a anterior concluída.
                    if novo_status and novo_status != "pendente":
                        import mod_chat
                        todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                        status_por_codigo = {e.etapa_codigo: e.status for e in todas}
                        _bloq = mod_chat.bloqueadores_ativos(db, nome_safe)
                        if not mod_ciclo.pode_avancar(etapa_cod, status_por_codigo,
                                                      bloqueadores_ativos=_bloq):
                            # distingue a CAUSA: sem o bloqueador teria passado? → é ele.
                            if mod_ciclo.pode_avancar(etapa_cod, status_por_codigo):
                                self.send_json({
                                    "ok": False,
                                    "codigo": "bloqueador_ativo",
                                    "erro": "Bloqueador ativo — resolva a transferência na "
                                            "Conversa antes de avançar.",
                                }, code=400)
                                return
                            ant = mod_ciclo.etapa_anterior(etapa_cod)
                            nome_ant = mod_ciclo.ETAPA_NOME.get(ant, ant)
                            self.send_json({
                                "ok": False,
                                "erro": f"Conclua a etapa anterior ({nome_ant}) antes de iniciar esta.",
                            }, code=400)
                            return
                    # Guarda das etapas operacionais (12/13/14): exige XML / números /
                    # relatório antes de concluir. Usa o obs recebido no request (se veio
                    # junto do status) ou o persistido na etapa.
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and etapa_cod in mod_ciclo.ETAPAS_OPERACIONAIS:
                        tem_xml = db.query(CicloDocumento).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="12",
                            tipo=mod_ciclo.tipo_doc_operacional("12")).first() is not None
                        obs_efetivo   = obs if obs is not None else etapa.observacoes
                        numeros_txt   = obs_efetivo if etapa_cod == "13" else None
                        relatorio_txt = obs_efetivo if etapa_cod == "14" else None
                        ok_op, erro_op = mod_ciclo.guarda_conclusao_operacional(
                            etapa_cod, tem_xml, numeros_txt, relatorio_txt)
                        if not ok_op:
                            self.send_json({"ok": False, "erro": erro_op}, code=400)
                            return
                    # Gate de execução de MONTAGEM/ASSISTÊNCIA (17/18): responsável por AMBIENTE no Mapa.
                    # Só trava na LACUNA (>1 candidato e ambiente sem responsável) — mesma regra do
                    # bloqueador invertido, mas por ambiente (fecha o gate de PE/montagem do chat).
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and etapa_cod in ("17", "18"):
                        # Desmembramento operacional (achado da Vera): a etapa 17/18 é de PROJETO INTEIRO —
                        # concluí-la com um ambiente ainda RETIDO pela obra registraria "montado" algo que
                        # fisicamente não pôde ser montado. Barra até liberar (mesmo padrão do pe/upload e
                        # da Conciliação Final).
                        import mod_retido as _mret
                        if _mret.ambientes_retidos(db, nome_safe):
                            self.send_json({"ok": False, "erro": "Há ambientes retidos pela obra: "
                                "libere-os (Retenção por Obra) antes de concluir a montagem/assistência."},
                                code=409)
                            return
                        import mod_equipe as _meq
                        faltam = _meq.montagem_lacunas(
                            db, loja_id, _ETAPA_PAPEL.get(etapa_cod),
                            _atribuicoes_dicts(db, nome_safe),
                            [a["id"] for a in _ambientes_do_projeto(db, nome_safe)])
                        if faltam:
                            self.send_json({"ok": False, "erro": "Defina o responsável de montagem no "
                                "Mapa de Atribuições para %d ambiente(s) antes de concluir: a função tem "
                                "mais de um candidato." % len(faltam)}, code=409)
                            return
                    # Aprovação financeira (8/11d): exige login+senha de quem pode aprovar.
                    aprovador = None
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and mod_ciclo.exige_aprovacao_financeira(etapa_cod):
                        aprovador = _aprovador_financeiro(db, req.get("login", ""), req.get("senha", ""), sessao=usuario)
                        if not aprovador:
                            self.send_json({
                                "ok": False,
                                "erro": "Apenas Gerente Administrativo/Financeiro ou Diretor podem "
                                        "aprovar a etapa financeira (login/senha inválidos ou sem permissão).",
                            }, code=403)
                            return
                        # Gate independente da SEQUÊNCIA: a AF só FECHA com a data de entrega DEFINIDA
                        # E o contrato totalmente assinado (as duas partes). Vale mesmo p/ projeto que
                        # foi assinado ANTES do gate da assinatura existir — antes essa trava vivia só
                        # na assinatura e a AF (etapa posterior) fechava sem re-checar.
                        _pm = db.get(Projeto, nome_safe)
                        if _pm is None or _pm.data_entrega is None:
                            self.send_json({"ok": False,
                                "erro": "Defina a data de entrega esperada do cliente antes de aprovar a AF."},
                                code=400)
                            return
                        if not _contrato_totalmente_assinado(nome_safe, db):
                            self.send_json({"ok": False,
                                "erro": "Contrato ainda não assinado pelas duas partes — não é possível "
                                        "aprovar a AF."}, code=400)
                            return
                    if novo_status:
                        if etapa.status == "pendente" and novo_status != "pendente":
                            etapa.iniciado_em = datetime.utcnow()
                        etapa.status = novo_status
                        if novo_status in mod_ciclo.STATUS_CONCLUSIVOS:
                            etapa.concluido_em  = datetime.utcnow()
                            etapa.responsavel_id = aprovador.id if aprovador else usuario["id"]
                    if obs is not None:
                        etapa.observacoes = obs
                    if aprovador is not None:
                        db.add(LogAcaoGerencial(
                            solicitante_id=usuario["id"],
                            autorizador_id=aprovador.id,
                            acao="aprovar_financeiro",
                            projeto_nome=nome_safe,
                            etapa_alvo=etapa_cod,
                        ))
                    # Passagem oficial AUTOMÁTICA (decisão 17): concluiu a fase → posta na
                    # Conversa uma transferência para o responsável da PRÓXIMA etapa principal.
                    # Só documenta (não grava CicloEtapa); pula quando não há próxima ou a
                    # próxima não tem responsável resolvível. Best-effort: falha aqui não pode
                    # derrubar a conclusão da etapa (que é o efeito principal do endpoint).
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS:
                        try:
                            prox = mod_ciclo.etapa_seguinte(etapa_cod)
                            prox_fid = (_responsavel_funcionario_etapa(db, nome_safe, loja_id, prox)
                                        if prox else None)
                            import mod_chat as _mchat
                            _pm = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                            conv = _mchat.get_or_create_conversa_projeto(
                                db, loja_id, nome_safe,
                                cliente_id=(_pm.cliente_id if _pm else None))
                            if prox and prox_fid:
                                _mchat.mensagem_passagem_fase(
                                    db, conv, usuario.get("id"),
                                    mod_ciclo.ETAPA_NOME.get(etapa_cod, etapa_cod),
                                    prox, mod_ciclo.ETAPA_NOME.get(prox, prox), prox_fid)
                            # Grupo de acompanhamento EVOLUTIVO (spec 2026-07-31, decisão 1):
                            # a transição re-deriva equipe∪gerência e cada entrada/saída vira
                            # evento inline na timeline da conversa do projeto.
                            import mod_equipe as _meq_f
                            _eqf = _meq_f.equipe_do_projeto(db, nome_safe, loja_id)
                            _mchat.sincronizar_grupo_da_fase(
                                db, conv, _eqf["membros_usuarios"],
                                fase_nome=(mod_ciclo.ETAPA_NOME.get(prox, prox) if prox else None),
                                autor_usuario_id=usuario.get("id"))
                        except Exception as _e:
                            logging.getLogger(__name__).warning(
                                "passagem automática de fase falhou (%s/%s): %s",
                                nome_safe, etapa_cod, _e)
                    db.commit()
                    self.send_json({"ok": True, "etapa_codigo": etapa_cod, "status": etapa.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m = re.match(r'^/api/projetos/([^/]+)/contrato$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario   = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req    = json.loads(body)
                adendo = req.get("adendo") or ""
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    if not contrato:
                        self.send_json({"ok": False, "erro": "Contrato não encontrado"}, code=404)
                        return
                    if contrato.status in ("vigente", "assinado"):
                        self.send_json({"ok": False,
                                        "erro": "Contrato vigente não pode ser editado"}, code=400)
                        return
                    contrato.adendo = adendo
                    db.commit()
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, contrato.orcamento_id, db)
                    from mod_contrato import construir_contexto
                    from mod_contrato import _formatar_valor
                    from mod_contrato import validar_loja_para_contrato
                    loja_dict = _loja_dict_para_contrato(db, contrato.loja_id or loja_id)
                    faltando_loja = validar_loja_para_contrato(loja_dict)
                    if faltando_loja and not req.get("confirmar_loja_incompleta"):
                        self.send_json({
                            "ok": False,
                            "precisa_confirmar_loja": True,
                            "campos_loja_faltando": faltando_loja,
                            "erro": "Dados da loja incompletos.",
                        }, code=400)
                        return
                    usuario_ctx = {
                        "nome":     usuario.get("nome", ""),
                        "telefone": _get_usuario_telefone(usuario["id"], db),
                        "email":    usuario.get("email", "") or "",
                    }
                    pag_json = contrato.pagamento_json or orcamento_dict.get("forma_pagamento", "") or ""
                    variaveis = construir_contexto(
                        cliente_dict,
                        usuario_ctx,
                        pag_json,
                        loja_dict,
                    )
                    variaveis.update({
                        "projeto_nome":    projeto_dict.get("nome_projeto", ""),
                        "orcamento_nome":  orcamento_dict.get("nome", ""),
                        "valor_total":     _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_negociado": _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_liquido":   _formatar_valor(orcamento_dict.get("valor_liquido", 0)),
                        "ambientes_lista": "\n".join(orcamento_dict.get("ambientes", [])),
                        "tem_adendo":      bool(adendo),
                        "adendo":          adendo or "",
                        "consultor_nome":  usuario.get("nome", ""),
                        "_ambientes":      _ambientes_valor_para_contrato(contrato.orcamento_id, db),
                    })
                    variaveis.update(_extras_marcadores_contrato(db, nome_safe, contrato.loja_id or loja_id))
                    # Fixa a versão do modelo que gerou este contrato: regerar
                    # depois reproduz estas cláusulas mesmo que a loja troque o
                    # modelo. Contrato legado (já gerado, sem versão) fica no
                    # template global. (spec D6)
                    import mod_documentos as _mdoc
                    variaveis["_db"] = db
                    variaveis["_modelo_versao_id"] = _mdoc.versao_para_contrato(
                        db, contrato, contrato.loja_id or loja_id)
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
                    if not contrato.loja_id:
                        contrato.loja_id = loja_id
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
                    db.commit()
                    self.send_json({"ok": True, "status": contrato.status})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return

            m_perfil = re.match(r"^/api/admin/perfis/([a-z0-9_]+)$", path)
            if m_perfil:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_perfis"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    from auth import perfil_store
                    p, err = perfil_store.editar_perfil(db, _loja_admin_alvo(usuario), m_perfil.group(1),
                                nome=req.get("nome"), modulos=req.get("modulos"),
                                capacidades=req.get("capacidades"))
                    if not p:
                        self.send_json({"ok": False, "erro": err}, code=403); return
                    perfis.recarregar()
                    self.send_json({"ok": True, "perfil": {"slug": p.slug, "nome": p.nome}})
                finally:
                    db.close()
                return

            m_user = re.match(r"^/api/admin/usuarios/(\d+)$", path)
            if m_user:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                erros = mod_usuarios.validar_edicao_usuario(req)
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                db = get_session()
                try:
                    u = db.query(Usuario).filter_by(id=int(m_user.group(1))).first()
                    if not u:
                        self.send_json({"ok": False, "erro": "Usuário não encontrado"})
                        return
                    ator = _ator_dict(db, usuario)
                    # escopo: o ator precisa enxergar o usuário-alvo (mesma regra da listagem)
                    if mod_tenancy._eh_super_admin(ator):
                        visivel = True
                    elif mod_tenancy._eh_admin_rede(ator):
                        rede_alvo = u.rede_id
                        if rede_alvo is None and u.loja_id is not None:
                            la = db.get(Loja, u.loja_id)
                            rede_alvo = la.rede_id if la else None
                        visivel = (rede_alvo == ator.get("rede_id"))
                    else:
                        visivel = (u.loja_id is not None and u.loja_id == ator.get("loja_id"))
                    if not visivel:
                        self.send_json({"ok": False, "erro": "Usuário fora do seu escopo."}, code=403)
                        return
                    # anti-lockout: o ator não altera o próprio perfil nem se inativa
                    eh_proprio = (u.id == usuario.get("id"))
                    if eh_proprio and "nivel" in req and req["nivel"].strip() != u.nivel:
                        self.send_json({"ok": False,
                            "erro": "Não é possível alterar o próprio perfil."}, code=403)
                        return
                    if eh_proprio and "ativo" in req and not req["ativo"]:
                        self.send_json({"ok": False,
                            "erro": "Não é possível inativar a si mesmo."}, code=403)
                        return
                    # anti-escalonamento: super_admin só por super_admin;
                    # admin_rede por super_admin ou admin_rede
                    novo_nivel = req["nivel"].strip() if "nivel" in req else None
                    if novo_nivel == "super_admin" and not mod_tenancy._eh_super_admin(ator):
                        self.send_json({"ok": False,
                            "erro": "Sem permissão para atribuir esse perfil."}, code=403)
                        return
                    if novo_nivel == "admin_rede" and not (
                            mod_tenancy._eh_super_admin(ator) or mod_tenancy._eh_admin_rede(ator)):
                        self.send_json({"ok": False,
                            "erro": "Sem permissão para atribuir esse perfil."}, code=403)
                        return
                    if "cpf" in req:
                        import validacao_doc
                        _e = validacao_doc.erro_doc(req.get("cpf"), "CPF", "cpf")
                        if _e:
                            self.send_json({"ok": False, "erro": _e}, code=400)
                            return
                    if "nome" in req:     u.nome     = req["nome"].strip()
                    if "nivel" in req:    u.nivel    = req["nivel"].strip()
                    if "telefone" in req: u.telefone = (req.get("telefone") or "").strip()
                    if "whatsapp" in req: u.whatsapp = (req.get("whatsapp") or "").strip()
                    if "email" in req:    u.email    = (req.get("email") or "").strip()
                    if "cpf" in req:      u.cpf      = (req.get("cpf") or "").strip()
                    if "ativo" in req:    u.ativo    = 1 if req["ativo"] else 0
                    if req.get("senha"):  u.set_senha(req["senha"])
                    # Apenas super_admin e admin_rede gerenciam memberships de lojas.
                    # Atores de loja (diretor/gerente_adm_fin) não reescrevem usuario_lojas —
                    # o modal deles só exibe a própria loja e re-escreveria a lista incorretamente,
                    # revogando memberships atribuídas por um admin_rede silenciosamente.
                    if "loja_ids" in req and (
                            mod_tenancy._eh_super_admin(ator)
                            or mod_tenancy._eh_admin_rede(ator)):
                        novas, erros_l = mod_tenancy.lojas_do_novo_usuario(ator, req)
                        if erros_l:
                            self.send_json({"ok": False, "erro": " ".join(erros_l)}); return
                        if not mod_tenancy._eh_super_admin(ator):
                            for lid in novas:
                                loja = db.get(Loja, lid)
                                if not loja or not mod_tenancy.pode_ver_loja(
                                        ator, {"id": loja.id, "rede_id": loja.rede_id}):
                                    self.send_json({"ok": False, "erro": "Loja fora do seu escopo."}); return
                        db.query(UsuarioLoja).filter(UsuarioLoja.usuario_id == u.id).delete()
                        for lid in novas:
                            db.add(UsuarioLoja(usuario_id=u.id, loja_id=lid))
                        u.loja_id = novas[0] if novas else u.loja_id
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return

            m_rede = re.match(r"^/api/admin/redes/(\d+)$", path)
            if m_rede:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    r = db.get(Rede, int(m_rede.group(1)))
                    if not r:
                        self.send_json({"ok": False, "erro": "Rede não encontrada"}, code=404)
                        return
                    if "nome" in req:
                        nome = (req["nome"] or "").strip()
                        if not nome:
                            self.send_json({"ok": False, "erro": "Nome da rede é obrigatório."})
                            return
                        r.nome = nome
                    if "cnpj" in req:
                        import validacao_doc
                        _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                        if _e:
                            self.send_json({"ok": False, "erro": _e}, code=400)
                            return
                        r.cnpj = (req["cnpj"] or "").strip() or None
                    if "ativo" in req: r.ativo = 1 if req["ativo"] else 0
                    db.commit()
                    self.send_json({"ok": True, "rede": _rede_dict(r)})
                finally:
                    db.close()
                return

            m_loja = re.match(r"^/api/admin/lojas/(\d+)$", path)
            if m_loja:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    l = db.get(Loja, int(m_loja.group(1)))
                    if not l:
                        self.send_json({"ok": False, "erro": "Loja não encontrada"}, code=404)
                        return
                    ator = _ator_dict(db, usuario)
                    loja_d = {"id": l.id, "rede_id": l.rede_id}
                    if not mod_tenancy.pode_editar_dados_loja(ator, loja_d):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                        return
                    # PDV (loja com mãe): cadastro é exclusivo do super_admin — o lojista
                    # visualiza, não edita (spec 2026-07-22, Desvio 4).
                    if l.loja_mae_id and not mod_tenancy._eh_super_admin(ator):
                        self.send_json({"ok": False, "erro": "Ponto de Venda só é editável "
                                        "pelo administrador da plataforma."}, code=403)
                        return
                    if "codigo" in req:
                        outros = [c for (c,) in db.query(Loja.codigo)
                                                .filter(Loja.id != l.id).all() if c]
                        erros = mod_tenancy.validar_loja(
                            {"nome": req.get("nome", l.nome), "codigo": req["codigo"]}, outros)
                        if erros:
                            self.send_json({"ok": False, "erro": " ".join(erros)})
                            return
                        l.codigo = req["codigo"].strip().upper()
                    if "cnpj" in req:
                        import validacao_doc
                        _e = validacao_doc.erro_doc(req.get("cnpj"), "CNPJ", "cnpj")
                        if _e:
                            self.send_json({"ok": False, "erro": _e}, code=400)
                            return
                    for campo in ("nome", "cnpj", "telefone", "email", "responsavel", "cep", "logradouro",
                                  "numero", "complemento", "bairro", "cidade", "estado",
                                  "testemunha1_nome", "testemunha1_cpf",
                                  "testemunha2_nome", "testemunha2_cpf"):
                        if campo in req:
                            val = (req[campo] or "").strip() or None
                            if campo == "nome" and not val:
                                self.send_json({"ok": False, "erro": "Nome da loja é obrigatório."})
                                return
                            setattr(l, campo, val)
                    # Segmentação de receita Mercadoria × Serviço (default da loja; valida soma=100).
                    if "pct_mercadoria" in req or "pct_servico" in req:
                        from mod_orcamento_params import validar_segmentacao
                        pm = req.get("pct_mercadoria", l.pct_mercadoria)
                        ps = req.get("pct_servico", l.pct_servico)
                        try:
                            validar_segmentacao(pm, ps)
                        except ValueError as _ve:
                            self.send_json({"ok": False, "erro": str(_ve)}, code=400)
                            return
                        l.pct_mercadoria = float(pm); l.pct_servico = float(ps)
                    if perfis.pode(ator.get("nivel"), "gerir_lojas"):
                        if "ativo" in req:   l.ativo = 1 if req["ativo"] else 0
                        # PDV: rede_id é HERDADO da mãe, não editável (spec 2026-07-22).
                        if ("rede_id" in req and mod_tenancy._eh_super_admin(ator)
                                and not l.loja_mae_id):
                            l.rede_id = req["rede_id"]
                        if isinstance(req.get("modulos"), list):
                            l.modulos_ativos = json.dumps([str(mo) for mo in req["modulos"]])
                    db.commit()
                    self.send_json({"ok": True, "loja": _loja_dict(l)})
                finally:
                    db.close()
                return

            self.send_json({"ok": False, "erro": "Rota não encontrada"})
        except Exception as e:
            self.send_json({"ok": False, "erro": str(e)})


# ── Helper ────────────────────────────────────────────────────────────────────
def validar_cadastro_minimo(req: dict) -> list:
    """Campos mínimos obrigatórios para criar um cliente: nome, e-mail, telefone.
    Retorna a lista de rótulos faltando (vazia se ok). CPF/endereço são opcionais
    na criação — a completude para o contrato é cobrada na aprovação."""
    faltando = []
    for campo, rotulo in [("nome", "Nome"), ("email", "E-mail"), ("telefone", "Telefone")]:
        if not (req.get(campo) or "").strip():
            faltando.append(rotulo)
    return faltando


def _endereco_por_cep(cep):
    """Consulta o ViaCEP e devolve {'ibge', 'cidade', 'uf'} (best-effort, offline-safe) ou None.
    Nunca lança — qualquer falha (rede, CEP inválido, JSON, sem IBGE) degrada para None."""
    try:
        dig = re.sub(r"\D", "", cep or "")   # `re` (global do módulo); `_re` só existe local nos handlers
        if len(dig) != 8:
            return None
        import requests
        r = requests.get("https://viacep.com.br/ws/%s/json/" % dig, timeout=5)
        d = (r.json() or {}) if r.status_code == 200 else {}
        ibge = d.get("ibge")
        if not ibge:
            return None
        return {"ibge": ibge, "cidade": d.get("localidade") or None, "uf": d.get("uf") or None}
    except Exception:
        return None


def _ibge_por_cep(cep):
    """Compat: só o código IBGE do município (via `_endereco_por_cep`). Usado no backfill de
    clientes antigos sem `municipio_ibge`."""
    end = _endereco_por_cep(cep)
    return end["ibge"] if end else None


def _bloqueio_modulo(path, loja):
    """(True, msg) se o path pertence a um módulo de domínio DESLIGADO para a loja; senão (False, None).
    Default tudo-ligado → nunca bloqueia sem config explícita. Topologia (ARQUITETURA-MODULOS.md)."""
    import modulos as _mod
    mod = _mod.modulo_do_path(path)
    if mod is None or loja is None:
        return (False, None)
    if mod_tenancy.modulo_ativo(loja, mod):
        return (False, None)
    return (True, "Módulo '%s' não está habilitado para esta loja." % mod)


def _cliente_dict(c) -> dict:
    return {
        "id":          c.id,
        "nome":        c.nome,
        "cpf":         c.cpf         or "",
        "tipo_dest":         c.tipo_dest         or "nao_contribuinte",
        "cnpj":              c.cnpj              or "",
        "inscricao_estadual":c.inscricao_estadual or "",
        "email":       c.email       or "",
        "telefone":    c.telefone    or "",
        "whatsapp":    c.whatsapp    or "",
        "cep":         c.cep         or "",
        "logradouro":  c.logradouro  or "",
        "numero":      c.numero      or "",
        "complemento": c.complemento or "",
        "bairro":      c.bairro      or "",
        "cidade":      c.cidade      or "",
        "estado":      c.estado      or "",
        "municipio_ibge": c.municipio_ibge or "",
        "observacoes": c.observacoes or "",
        "inst_mesmo_residencial": bool(c.inst_mesmo_residencial if c.inst_mesmo_residencial is not None else 1),
        "inst_logradouro":  c.inst_logradouro  or "",
        "inst_numero":      c.inst_numero      or "",
        "inst_complemento": c.inst_complemento or "",
        "inst_bairro":      c.inst_bairro      or "",
        "inst_cidade":      c.inst_cidade      or "",
        "inst_cep":         c.inst_cep         or "",
        "inst_uf":          c.inst_uf          or "",
        "criado_em":   c.criado_em.strftime("%Y-%m-%d") if c.criado_em else "",
    }


_BRIEFING_OBRIGATORIOS = [
    "tipo_imovel", "budget_declarado", "categoria_proposta",
    "data_entrega_desejada", "flexibilidade_prazo",
]

def _briefing_dict(b) -> dict:
    d = {
        "id":                    b.id,
        "cliente_id":            b.cliente_id,
        "projeto_nome":          b.projeto_nome or "",
        "data_atendimento":      b.data_atendimento.isoformat() if b.data_atendimento else "",
        "consultor_id":          b.consultor_id,
        "tipo_imovel":           b.tipo_imovel           or "",
        "budget_declarado":      b.budget_declarado       or 0.0,
        "categoria_proposta":    b.categoria_proposta     or "",
        "data_entrega_desejada": b.data_entrega_desejada  or "",
        "flexibilidade_prazo":   b.flexibilidade_prazo    or "",
        "condicao_imovel":       b.condicao_imovel        or "",
        "metragem_m2":           b.metragem_m2,
        "num_ambientes":         b.num_ambientes,
        "ambientes_prioritarios":b.ambientes_prioritarios or "",
        "tem_arquiteto":         b.tem_arquiteto          or "",
        "nome_arquiteto":        b.nome_arquiteto         or "",
        "tem_gerente_obra":      bool(b.tem_gerente_obra),
        "end_empreendimento":    b.end_empreendimento     or "",
        "estilo_decisao":        b.estilo_decisao         or "[]",
        "estilo_vida":           b.estilo_vida            or "[]",
        "relacao_projeto":       b.relacao_projeto        or "[]",
        "decisor":               b.decisor                or "",
        "referencias_visuais":   b.referencias_visuais    or "[]",
        "obs_referencias":       b.obs_referencias        or "",
        "experiencia_anterior":  b.experiencia_anterior   or "",
        "obs_experiencia":       b.obs_experiencia        or "",
        "tem_budget":            b.tem_budget             or "",
        "forma_pagamento_pref":  b.forma_pagamento_pref   or "",
        "data_entrega_limite":   b.data_entrega_limite    or "",
        "motivo_prazo":          b.motivo_prazo           or "[]",
        "nao_abre_mao":          b.nao_abre_mao           or "",
        "restricoes":            b.restricoes             or "",
        "obs_livres":            b.obs_livres             or "",
    }
    d["completo"] = all(d.get(f) for f in _BRIEFING_OBRIGATORIOS)
    # locked é calculado dinamicamente pelo endpoint GET (não aqui)
    d["locked"] = False
    return d


def _briefing_projeto_completo(nome_safe, db) -> bool:
    """True se o projeto tem um briefing POR-PROJETO com todos os obrigatórios
    preenchidos. Briefings legados (projeto_nome NULL) não são considerados."""
    b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
          .order_by(Briefing.id.desc()).first()
    if not b:
        return False
    return _briefing_dict(b)["completo"]


def _briefing_locked(cliente_id: int, briefing_completo: bool, db) -> bool:
    """
    Retorna True se o briefing deve ser somente-leitura.
    Regra: briefing COMPLETO + pelo menos um projeto novo do cliente com etapa 4 concluída.
    Projetos legados (sem cliente_id em projetos_meta) não bloqueiam o briefing.
    """
    if not briefing_completo:
        return False   # briefing incompleto → sempre editável (precisa ser preenchido)
    projetos = db.query(Projeto).filter_by(cliente_id=cliente_id).all()
    if not projetos:
        return False   # nenhum projeto novo → não bloqueia
    for p in projetos:
        etapa4 = db.query(CicloEtapa).filter_by(
            projeto_nome=p.nome_safe, etapa_codigo="4", status="concluido"
        ).first()
        if etapa4:
            return True
    return False


def _marcar_etapa_cliente(cliente_id: int, etapa_codigo: str, db, usuario):
    """Marca uma etapa do ciclo como concluída em todos os projetos vinculados ao cliente."""
    from datetime import datetime as _dt
    projetos = db.query(Projeto).filter_by(cliente_id=cliente_id).all()
    agora = _dt.utcnow()
    uid = usuario["id"] if usuario else None
    for p in projetos:
        etapa = db.query(CicloEtapa).filter_by(
            projeto_nome=p.nome_safe, etapa_codigo=etapa_codigo
        ).first()
        if not etapa:
            etapa = CicloEtapa(projeto_nome=p.nome_safe, etapa_codigo=etapa_codigo)
            db.add(etapa)
        if etapa.status != "concluido":
            etapa.status         = "concluido"
            etapa.concluido_em   = agora
            etapa.responsavel_id = uid
    db.commit()


def _projeto_esta_bloqueado(nome_safe) -> bool:
    """True se o projeto foi aprovado/bloqueado (PROJETOS/<nome>/projeto.json -> 'bloqueado').
    Centraliza o gate pos-aprovacao usado pelos handlers de margens/descontos por orcamento."""
    proj = _carregar_projeto(nome_safe)
    return bool(proj and proj.get("bloqueado"))


def _contrato_assinado(nome_safe, db) -> bool:
    """True se o último contrato do projeto tem qualquer assinatura (1ª assinatura)
    ou status já assinado. Fonte única da trava total pós-assinatura."""
    c = (db.query(Contrato)
           .filter_by(projeto_nome=nome_safe)
           .order_by(Contrato.id.desc())
           .first())
    if not c:
        return False
    if c.status in ("assinado_loja", "assinado_cliente", "assinado", "vigente"):
        return True
    return len(c.assinaturas) > 0


def _contrato_totalmente_assinado(nome_safe, db) -> bool:
    """True somente quando AMBAS as partes assinaram (loja + cliente) — contrato
    totalmente assinado. Usado para esconder o botão 'Assinar Contrato' (nada mais
    a assinar). Difere de _contrato_assinado (que é True já na 1ª assinatura)."""
    c = (db.query(Contrato)
           .filter_by(projeto_nome=nome_safe)
           .order_by(Contrato.id.desc())
           .first())
    if not c:
        return False
    if c.status in ("assinado", "vigente"):
        return True
    return {"loja", "cliente"}.issubset({a.parte for a in c.assinaturas})


def _pool_ambiente_dict(pa) -> dict:
    return {
        "id":            pa.id,
        "projeto_id":    pa.projeto_id,
        "nome":          pa.nome,
        "versao":        pa.versao,
        "nome_exibicao": pa.nome_exibicao,
        "xml_path":      pa.xml_path,
        "budget_total":  pa.budget_total,
        "order_total":   pa.order_total,
        "created_at":    pa.created_at.strftime("%Y-%m-%d %H:%M") if pa.created_at else "",
    }


def _complemento_diferencas(db, nome_safe):
    """Correção da Fatia 3 (2026-07-21): diferenças por ambiente MARCADO para complemento —
        à_vista_complemento_i = venda_XML_complemento_i × (VAVA_contratado_i / VBVA_contratado_i)
        diferença_i           = à_vista_complemento_i − VAVA_contratado_i
    O fator é a razão do PRÓPRIO ambiente contratado (à vista ÷ bruto): carrega os descontos do
    contrato e a carga de custos adicionais EXATAMENTE como negociados naquele ambiente — objetivo
    do usuário ("ajuste proporcional relativo aos custos adicionais" + "desconto aplicado de forma
    idêntica"). Propriedade de validação (vale em QUALQUER composição — arq/fid/viagem/brinde;
    o fator único 1/(1−p) falhava com brinde e Custo Especial): XML idêntico ⇒ diferença ZERO.
    O Custo Especial fica naturalmente FORA (não está no VAVA por ambiente — coerente com a
    definição dele: não acompanha ambiente). O percentual único p = Cust_Ad/VAVO segue no resumo
    como INFORMAÇÃO (exibido no Apoio à negociação); fallback do fator se VBVA contratado = 0.
    Retorna (linhas, resumo) ou (None, erro_str). linhas só dos ambientes marcados."""
    ct = (db.query(Contrato).filter_by(projeto_nome=nome_safe)
            .order_by(Contrato.id.desc()).first())
    orc_ct = db.get(Orcamento, ct.orcamento_id) if ct else None
    if orc_ct is None:
        return None, "Projeto sem contrato para comparar."
    d_ct = _negociacao_breakdown(orc_ct, db)
    vava_ct = {a.get("id"): float(a.get("VAVA", 0.0)) for a in d_ct.get("ambientes", [])}
    vavo_ct = float(d_ct.get("VAVO") or 0.0)
    cad_ct = float(d_ct.get("Cust_Ad") or 0.0)
    fator_ca = (vavo_ct / (vavo_ct - cad_ct)) if (vavo_ct - cad_ct) > 0 else 1.0
    d_orc_ct = float(orc_ct.desconto_pct or 0.0) / 100.0
    d_amb_ct = {oa.pool_ambiente_id: float(oa.desconto_individual_pct or 0.0) / 100.0
                for oa in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc_ct.id).all()}
    compls = {a.pool_ambiente_id: a for a in
              db.query(ArquivoPE).filter_by(projeto_nome=nome_safe, formato="xml_compl").all()}
    linhas = []
    for pa in (db.query(PoolAmbiente).filter_by(projeto_id=nome_safe)
                 .order_by(PoolAmbiente.id.asc()).all()):
        if not pa.renegociar_pe:
            continue
        nome_amb = pa.nome_exibicao or pa.nome
        vc = round(vava_ct.get(pa.id, 0.0), 2)
        vbva_c = float(pa.budget_total or 0.0)
        a = compls.get(pa.id)
        carregado = a is not None and a.valor_venda is not None
        va_compl = dif = cfo_dif = 0.0
        if carregado:
            if vbva_c > 0 and vc > 0:
                va_compl = round(float(a.valor_venda) * (vc / vbva_c), 2)
            else:   # fallback (ambiente contratado sem valor): fator único aproximado
                va_compl = round(float(a.valor_venda) * (1 - d_orc_ct)
                                 * (1 - d_amb_ct.get(pa.id, 0.0)) * fator_ca, 2)
            dif = round(va_compl - vc, 2)
            cfo_dif = round(float(a.valor_atualizado or 0.0) - float(pa.order_total or 0.0), 2)
        linhas.append({"pool_ambiente_id": pa.id, "ambiente": nome_amb,
                       "vava_contratado": vc, "vava_complemento": va_compl,
                       "diferenca": dif, "cfo_diferenca": cfo_dif,
                       "compl_carregado": carregado})
    carregadas = [l for l in linhas if l["compl_carregado"]]
    resumo = {
        "pct_custos_adicionais": round((cad_ct / vavo_ct * 100.0) if vavo_ct else 0.0, 4),
        "fator_ca": round(fator_ca, 6),
        "desc_global_pct": float(orc_ct.desconto_pct or 0.0),
        "total_contratado": round(sum(l["vava_contratado"] for l in carregadas), 2),
        "total_complemento": round(sum(l["vava_complemento"] for l in carregadas), 2),
        "total_diferenca": round(sum(l["diferenca"] for l in carregadas), 2),
        "marcados": len(linhas), "carregados": len(carregadas),
    }
    return linhas, resumo


def _aditivo_dados_calculo(db, nome, contrato, orc_aj):
    """Números do Termo Aditivo numa passada só (spec 2026-07-22): as linhas por ambiente
    MARCADO (dados/6 marcadores antigos da Fatia 3) + a visão INTEGRAL do contrato
    pós-alteração (modal 2 — inclui os ambientes NÃO alterados) + inclusões/exclusões
    detectadas + totais do CONTRATO (original → novo). Inclusão = ambiente do complemento
    que não consta do orçamento contratado; exclusão = ambiente contratado cujo valor
    pós-alteração zera. O operador sempre pode editar no wizard — isto é o DEFAULT."""
    linhas_cmp, _res = _complemento_diferencas(db, nome)
    base_orig = {l["pool_ambiente_id"]: l["vava_contratado"] for l in (linhas_cmp or [])}
    d_aj = _negociacao_breakdown(orc_aj, db)
    pa_nome = {pa.id: (pa.nome_exibicao or pa.nome) for pa in
               db.query(PoolAmbiente).filter_by(projeto_id=nome).all()}
    linhas_amb, tot_orig_marc, tot_dif = [], 0.0, 0.0
    dif_por_amb = {}
    for a in d_aj.get("ambientes", []):
        vo = round(float(base_orig.get(a.get("id"), 0.0)), 2)
        dif_amb = round(float(a.get("VAVA", 0.0)), 2)   # diferença negociada
        dif_por_amb[a.get("id")] = dif_amb
        tot_orig_marc += vo; tot_dif += dif_amb
        linhas_amb.append({"pool_ambiente_id": a.get("id"),
                           "ambiente": pa_nome.get(a.get("id"), "?"),
                           "vava_original": vo,
                           "vava_novo": round(vo + dif_amb, 2),
                           "diferenca": dif_amb})
    orc_ct = db.get(Orcamento, contrato.orcamento_id) if contrato.orcamento_id else None
    d_ct = _negociacao_breakdown(orc_ct, db) if orc_ct is not None else {"ambientes": []}
    lista_integral, inclusoes, exclusoes = [], [], []
    ids_ct, tot_ct_orig = set(), 0.0
    for a in d_ct.get("ambientes", []):
        aid = a.get("id"); ids_ct.add(aid)
        vo = round(float(a.get("VAVA", 0.0)), 2)
        novo = round(vo + dif_por_amb.get(aid, 0.0), 2)
        tot_ct_orig += vo
        nome_amb = pa_nome.get(aid, "?")
        if novo <= 0.005 and vo > 0:
            exclusoes.append((nome_amb, vo))            # zerou → saiu do rol
        else:
            lista_integral.append((nome_amb, novo))
    for aid, dif_amb in dif_por_amb.items():
        if aid not in ids_ct:                           # não constava do contrato → inclusão
            nome_amb = pa_nome.get(aid, "?")
            lista_integral.append((nome_amb, dif_amb))
            if dif_amb > 0:
                inclusoes.append((nome_amb, dif_amb))
    dif = round(tot_dif, 2)
    tot_ct_orig = round(tot_ct_orig, 2)
    return {"linhas_amb": linhas_amb,
            "tot_orig_marc": round(tot_orig_marc, 2),
            "tot_novo_marc": round(round(tot_orig_marc, 2) + dif, 2),
            "dif": dif,
            "lista_integral": lista_integral, "inclusoes": inclusoes, "exclusoes": exclusoes,
            "contrato_original": tot_ct_orig,
            "contrato_novo": round(tot_ct_orig + dif, 2)}


def _aditivo_condicoes_default(orc_aj):
    """Texto-base das condições de pagamento do bloco de valores (modal 5). O complemento
    nasce à vista/entrada 0 (plano zerado) — plano negociado vira contagem simples; o
    detalhamento fino é edição do operador no wizard."""
    try:
        fp = json.loads(orc_aj.forma_pagamento) if orc_aj.forma_pagamento else {}
    except Exception:
        fp = {}
    parcelas = fp.get("parcelas") or []
    if len(parcelas) > 1:
        return "em %d parcelas, conforme plano negociado no complemento" % len(parcelas)
    return "à vista, na data de assinatura deste TERMO ADITIVO"


def _aditivo_defaults_blocos(db, nome, contrato, orc_aj):
    """(defaults_dict, calc) — os 5 textos-padrão do wizard + os números que os geraram."""
    import mod_contrato as _mc
    calc = _aditivo_dados_calculo(db, nome, contrato, orc_aj)
    defaults = _mc.montar_defaults_aditivo(
        lista_integral=calc["lista_integral"], inclusoes=calc["inclusoes"],
        exclusoes=calc["exclusoes"], valor_original=calc["contrato_original"],
        valor_novo=calc["contrato_novo"], diferenca=calc["dif"],
        condicoes=_aditivo_condicoes_default(orc_aj))
    return defaults, calc


def _aditivo_ordinal_atual(db, contrato, aditivo=None):
    """Posição deste aditivo na contagem do contrato (1 → PRIMEIRO…). Sem aditivo aberto
    (ou com o último assinado), é a posição do PRÓXIMO."""
    if aditivo is not None and aditivo.status != "assinado" and aditivo.id is not None:
        return (db.query(Aditivo).filter(Aditivo.contrato_id == contrato.id,
                                         Aditivo.id < aditivo.id).count() + 1)
    return db.query(Aditivo).filter_by(contrato_id=contrato.id).count() + 1


# ── Ajustes Excepcionais de Fábrica (spec 2026-07-21) — composition root ─────────────────────
# O razão só BOOKA (mod_contabil); o cálculo é do mod_ajustes_fabrica (puro). O saldo POR ACORDO
# vem da trilha de aplicações (a conta do razão consolida acordos da mesma natureza da loja).

def _contraparte_dict(c):
    return {"id": c.id, "nome": c.nome, "tipo": c.tipo,
            "cnpj": c.cnpj or "", "telefone": c.telefone or "", "email": c.email or "",
            "cep": c.cep or "", "logradouro": c.logradouro or "", "numero": c.numero or "",
            "complemento": c.complemento or "", "bairro": c.bairro or "",
            "cidade": c.cidade or "", "uf": c.uf or ""}


def _acordo_saldos(db, acordo):
    """Saldo do acordo (revisão Acordos Financeiros, 2026-07-21) = implantado + aplicações COM
    SINAL + movimentos manuais. Sinal das aplicações por (tipo do acordo, tipo do ajuste):
    crédito consumido por desconto → reduz; dívida-fábrica amortizada por acréscimo → reduz;
    dívida-EMPRESA financiando desconto → ACUMULA (a dívida com a credora cresce, sem cap).
    Sem acerto/pendências: cada loja registra só o seu lado. disponivel == saldo (cap)."""
    rows = (db.query(AjusteFabricaAplicacao, AjusteFabrica)
              .join(AjusteFabrica, AjusteFabricaAplicacao.ajuste_id == AjusteFabrica.id)
              .filter(AjusteFabrica.acordo_id == acordo.id).all())
    saldo = float(acordo.valor_implantado or 0)
    acumulado = 0.0
    for ap, aj in rows:
        if acordo.tipo == "divida" and aj.tipo == "desconto":
            saldo += ap.valor          # desconto financiado pela credora: dívida cresce
            acumulado += ap.valor
        else:
            saldo -= ap.valor          # consumo de crédito / amortização de dívida
    movs = db.query(AcordoMovimento).filter_by(acordo_id=acordo.id).all()
    _IN = ("atualizacao", "transferencia_in", "acrescimo_manual")
    _OUT = ("pagamento", "recebimento", "transferencia_out", "baixa_encerramento", "abatimento_manual")
    for m in movs:
        if m.tipo in _IN:
            saldo += m.valor
        elif m.tipo in _OUT:
            saldo -= m.valor
        # demais (ex.: juros_pagos) são neutros — despesa direta, não mexem no principal
    saldo = round(saldo, 2)
    return {"contabil": saldo, "acumulado": round(acumulado, 2),
            "disponivel": max(saldo, 0.0)}


def _ajuste_fabrica_dict(a):
    try:
        projetos = json.loads(a.projetos_json) if a.projetos_json else None
    except Exception:
        projetos = None
    return {"id": a.id, "acordo_id": a.acordo_id, "loja_id": a.loja_id,
            "descricao": a.descricao or "", "tipo": a.tipo, "natureza": a.natureza,
            "pct": a.pct, "base": a.base, "tratamento": a.tratamento,
            "vigencia_de": a.vigencia_de.strftime("%Y-%m-%d") if a.vigencia_de else None,
            "vigencia_ate": a.vigencia_ate.strftime("%Y-%m-%d") if a.vigencia_ate else None,
            "projetos": projetos, "ativo": bool(a.ativo)}


def _owner_da_loja(db, loja_id):
    return mod_contabil_owner(db, loja_id)


def mod_contabil_owner(db, loja_id):
    import mod_contabil
    return mod_contabil.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})


def _aplicar_ajustes_conferencia(db, ot, own_id, loja_id, nome_safe, valor_conferido,
                                 aplicar=True):
    """Aplica os ajustes vigentes da loja sobre o valor conferido (etapa 12). Ordem/caps no motor
    puro; aqui só o ledger + a trilha. Intercompany decidido por OWNER (lojas da MESMA rede
    compartilham razão → consumo direto; owners distintos → conta corrente, SÓ na compradora).
    Idempotente por ref `ajx:<projeto>:<ajuste_id>`. Retorna o cálculo + aplicados."""
    import mod_contabil
    rows = {r.id: r for r in db.query(AjusteFabrica)
            .filter_by(loja_id=loja_id, ativo=1, tratamento="custo").all()}
    ajustes = [dict(_ajuste_fabrica_dict(r)) for r in rows.values()]
    # Revisão 2026-07-22: a vigência é avaliada pela DATA DA VENDA ("caso o pedido seja vendido
    # dentro do prazo de vigência") — o desconto muda a condição comercial DAQUELE período,
    # mesmo que a conferência aconteça depois. Sem contrato, cai em hoje.
    ct_v = (db.query(Contrato).filter_by(projeto_nome=nome_safe)
              .order_by(Contrato.id.desc()).first())
    data_venda = (ct_v.gerado_em.date().isoformat()
                  if (ct_v is not None and ct_v.gerado_em) else None)
    calc = mod_ajustes_fabrica.calcular_aplicacoes(valor_conferido, ajustes,
                                                   hoje=data_venda, projeto=nome_safe)
    if not aplicar:            # preview (GET): só o cálculo, nenhum lançamento
        calc["aplicadas"] = []
        return calc
    aplicadas = []
    for ap in calc["aplicacoes"]:
        aj = rows[ap["id"]]
        # RECONFERÊNCIA (QA Vera, 🟠): lança o DELTA entre o recalculado (PE atual) e o LÍQUIDO
        # já aplicado — o razão acompanha o PE novo e a resposta reflete o que foi lançado.
        ja_rows = (db.query(AjusteFabricaAplicacao)
                     .filter_by(ajuste_id=ap["id"], projeto_nome=nome_safe).all())
        ja = round(sum(r.valor for r in ja_rows), 2)
        delta = round(ap["valor"] - ja, 2)
        if abs(delta) < 0.005:
            continue   # idempotente: nada mudou para este ajuste
        ref = "ajx:%s:%s" % (nome_safe, ap["id"])
        if ja_rows:
            ref = "%s:r%d" % (ref, len(ja_rows))       # rebase N da mesma venda
        # revisão 2026-07-22: todo ajuste é de CUSTO — delta na provisão de fábrica
        # (ativo diferido × provisão, nunca DRE); desconto reduz, acréscimo aumenta
        mudanca = -delta if ap["tipo"] == "desconto" else delta
        atual = round(mod_contabil._mov(db, ot, own_id, "2.1.04.06", "credor", None, None,
                                        projeto_id=nome_safe), 2)
        mod_contabil.ajustar_provisao_delta(db, ot, own_id, nome_safe, "custo_fabrica",
                                            atual, round(atual + mudanca, 2), ref=ref)

        db.add(AjusteFabricaAplicacao(ajuste_id=ap["id"], projeto_nome=nome_safe,
                                      base_calculo=ap["base_calculo"], pct_snapshot=ap["pct"],
                                      valor=delta, status="n/a", lancamento_ref=ref))
        aplicadas.append({**ap, "delta_lancado": delta, "status": "n/a"})
    calc["aplicadas"] = aplicadas
    return calc


def _reverter_aplicacoes_fabrica(db, ot, own_id, nome_safe, fracao, ref_base):
    """Devolução (spec, risco 'Devolução de venda'): reverte as aplicações consumir_saldo do
    projeto na fração devolvida — devolve saldo ao acordo (ledger inverso na própria loja;
    aplicação NEGATIVA na trilha). Revisão Acordos Financeiros 2026-07-21: status é sempre
    'n/a' (o fluxo de acerto foi eliminado). Idempotente por ref."""
    import mod_contabil
    out = []
    rows = (db.query(AjusteFabricaAplicacao)
              .join(AjusteFabrica, AjusteFabricaAplicacao.ajuste_id == AjusteFabrica.id)
              .filter(AjusteFabricaAplicacao.projeto_nome == nome_safe,
                      AjusteFabricaAplicacao.valor > 0,
                      # SÓ consumir_saldo: aplicações de tratamento=custo movem o par
                      # provisão×ativo que o devolver_venda genérico JÁ reverte pelos saldos
                      # atuais — reverter aqui de novo re-adicionaria o valor (QA Vera, 🔴)
                      AjusteFabrica.tratamento == "consumir_saldo").all())
    for row in rows:
        rev = round(float(row.valor) * float(fracao), 2)
        if rev <= 0:
            continue
        ref = "%s:ajx:%d" % (ref_base, row.id)
        if mod_contabil.lancamento_por_ref(db, ot, own_id, ref) is not None:
            continue
        orig = mod_contabil.lancamento_por_ref(db, ot, own_id, row.lancamento_ref or "")
        if orig is None:
            continue
        # lançamento INVERSO do original (contas trocadas), mesma compradora
        mod_contabil.lancar(db, ot, own_id, orig["conta_credito_id"], orig["conta_debito_id"],
                            rev, projeto_id=nome_safe, origem="devolucao",
                            historico="Devolução — reversão de ajuste excepcional de fábrica",
                            ref=ref)
        db.add(AjusteFabricaAplicacao(ajuste_id=row.ajuste_id, projeto_nome=nome_safe,
                                      base_calculo=None, pct_snapshot=row.pct_snapshot,
                                      valor=-rev, status="n/a", lancamento_ref=ref))
        # acordo volta a ter saldo → reativa se estava esgotado
        aj = db.get(AjusteFabrica, row.ajuste_id)
        ac = db.get(AcordoFabrica, aj.acordo_id) if (aj and aj.acordo_id) else None
        if ac is not None and ac.status == "esgotado":
            ac.status = "ativo"
        out.append({"aplicacao_id": row.id, "revertido": rev})
    return out


def _aprovacao_pe_dict(a) -> dict:
    """Serialização da Aprovação do PE (correção Fatia 3) para o frontend."""
    try:
        dados = json.loads(a.dados_json) if a.dados_json else None
    except Exception:
        dados = None
    return {
        "id": a.id, "num_aprovacao": a.num_aprovacao or "", "status": a.status,
        "tem_pdf": bool(a.pdf_path and os.path.exists(a.pdf_path)),
        "gerado_em": a.gerado_em.strftime("%Y-%m-%d %H:%M") if a.gerado_em else "",
        "dados": dados,
        "assinaturas": [{"parte": s.parte, "nome": s.nome,
                         "assinado_em": s.assinado_em.strftime("%Y-%m-%d %H:%M") if s.assinado_em else ""}
                        for s in a.assinaturas],
    }


def _aditivo_dict(a) -> dict:
    """Serialização do Termo Aditivo (Fatia 3 PE) para o frontend."""
    try:
        dados = json.loads(a.dados_json) if a.dados_json else None
    except Exception:
        dados = None
    return {
        "id": a.id, "num_aditivo": a.num_aditivo or "", "status": a.status,
        "tem_pdf": bool(a.pdf_path and os.path.exists(a.pdf_path)),
        "gerado_em": a.gerado_em.strftime("%Y-%m-%d %H:%M") if a.gerado_em else "",
        "dados": dados,
        "assinaturas": [{"parte": s.parte, "nome": s.nome,
                         "assinado_em": s.assinado_em.strftime("%Y-%m-%d %H:%M") if s.assinado_em else ""}
                        for s in a.assinaturas],
    }


def _orcamento_dict(o) -> dict:
    return {
        "id":              o.id,
        "projeto_id":      o.projeto_id,
        "nome":            o.nome,
        "ordem":           o.ordem,
        "desconto_pct":    o.desconto_pct    or 0.0,
        "forma_pagamento": o.forma_pagamento or "",
        "valor_total":     o.valor_total     or 0.0,
        "valor_liquido":   o.valor_liquido   or 0.0,
        "created_at":      o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
        "updated_at":      o.updated_at.strftime("%Y-%m-%d %H:%M") if o.updated_at else "",
        "complemento_pe":       bool(getattr(o, "complemento_pe", 0)),   # Fatia 3 PE: orçamento de ajuste
        "ambientes":       [],  # preenchido por rotas específicas
        # ── modo sombra: derivados do motor de negociação (Task 7) ──
        "sombra": _sombra_dict(o),
    }


def _sombra_dict(o) -> dict:
    """Sub-objeto com os derivados sombra de um orçamento — cadeia completa do motor
    (modo sombra), para o bloco de validação HOJE × NOVO do modal."""
    return {
        "vbvo":         o.vbvo         or 0.0,
        "cfo":          o.cfo          or 0.0,
        "vbno":         o.vbno         or 0.0,
        "vavo":         o.vavo         or 0.0,
        "com_arq_orc":  o.com_arq_orc  or 0.0,
        "pro_fid_orc":  o.pro_fid_orc  or 0.0,
        "cust_ad":      o.cust_ad      or 0.0,
        "val_liq":      o.val_liq      or 0.0,
        "desc_tot_pct": o.desc_tot_pct or 0.0,
        "markup":       o.markup       or 0.0,
        "val_cont":     o.val_cont     or 0.0,
    }


def _cfg_financeira_loja(db, loja_id):
    """config_financeira (dict) da loja, ou o default. Base dos defaults de negociação
    (comissão do arquiteto, fidelidade, carga tributária) herdados por projetos novos."""
    import mod_provisoes
    loja = db.get(Loja, loja_id) if loja_id else None
    if loja and loja.config_financeira_json:
        try:
            # Normaliza o STORED antes do merge: config legada (sem cronograma_formato) é convertida de
            # acumulado para durações. O merge preenche chaves novas sem apagar o já configurado.
            _stored = mod_provisoes.normalizar_cronograma_formato(json.loads(loja.config_financeira_json))
            return {**mod_provisoes.config_financeira_default(), **_stored}
        except Exception:
            pass
    return mod_provisoes.config_financeira_default()


def _extras_marcadores_contrato(db, nome_safe, loja_id):
    """Valores dos marcadores DATA_PREVISTA_ENTREGA/PREVISAO_MEDICAO/PRAZO_CONTRATUAL/
    VENDA_PROGRAMADA (Fatia 3), lidos do Projeto (projetos_meta) e da config financeira
    da loja. Mescla em ctx antes de gerar_pdf_contrato(); ausência de projeto/datas
    resulta em campos em branco (marcador some do PDF, não quebra a geração)."""
    projeto = db.get(Projeto, nome_safe)
    data_entrega    = projeto.data_entrega    if projeto else None
    previsao_med    = projeto.previsao_medicao if projeto else None
    venda_prog      = bool(projeto.venda_programada) if projeto else False
    prazo_dias = _cfg_financeira_loja(db, loja_id).get("prazo_contratual_dias_uteis", 50)
    return {
        "data_prevista_entrega": data_entrega.strftime("%d/%m/%Y") if data_entrega else "",
        "previsao_medicao":      previsao_med.strftime("%d/%m/%Y") if previsao_med else "",
        "prazo_contratual":      "%d dias úteis a partir da assinatura" % prazo_dias,
        "venda_programada_txt":  ("Trata-se de VENDA PROGRAMADA: a medição depende da "
                                   "liberação da obra pelo cliente.") if venda_prog else "",
    }


def _params_iniciais_projeto(db, projeto_nome, loja_id):
    """parametros de um projeto SEM parametros_json salvos: defaults da loja e — se houver
    parceiro no projeto — comissão do arquiteto e fidelidade já ATIVAS (valores de cadastro).
    % do arquiteto = o do próprio parceiro; se ausente, o default da loja. Fidelidade entra
    sempre que houver parceiro. São apenas os valores INICIAIS: uma vez salvos em
    parametros_json, passam a ser respeitados como estão (as edições persistem)."""
    from integracoes import projetos_store
    from mod_orcamento_params import parametros_default_loja
    par = parametros_default_loja(_cfg_financeira_loja(db, loja_id))
    proj_json = projetos_store._carregar_projeto(projeto_nome) or {}
    parceiro_id = proj_json.get("parceiro_id")
    if parceiro_id:
        parc = db.get(Parceiro, int(parceiro_id))
        pct_parc = float(getattr(parc, "comissao_padrao_pct", 0) or 0) if parc else 0.0
        par["comissao_arq_ativa"] = True
        if pct_parc > 0:
            par["comissao_arq_pct"] = pct_parc
        par["fidelidade_ativa"] = True
    return par


def _negociacao_breakdown(orc, db, vbva_override=None):
    """Calcula a cadeia do motor lendo SÓ os insumos salvos (parametros_json, desconto do
    orçamento, descontos por ambiente, forma_pagamento). Sem overrides do frontend. NÃO grava.
    vbva_override: {pool_ambiente_id: VBVA} — substitui o valor bruto de ambientes específicos
    (Fatia venda da Revisão de PE: VBVA extraído do XML de PE passa pelo MESMO motor, com os
    mesmos parâmetros/descontos, para comparar venda à vista maçã-com-maçã). Motor inalterado."""
    import mod_negociacao, mod_provisoes, mod_orcamento_params
    proj = db.query(Projeto).filter_by(nome_safe=orc.projeto_id).first()
    # Carrega cfg da loja uma única vez — usado para defaults de params E para provisões
    _loja = db.get(Loja, orc.loja_id) if getattr(orc, "loja_id", None) else None
    cfg = {}
    if _loja and _loja.config_financeira_json:
        try:
            cfg = json.loads(_loja.config_financeira_json)
        except Exception:
            cfg = {}
    if not cfg:
        cfg = mod_provisoes.config_financeira_default()
    # Projetos sem parametros_json herdam os defaults de negociação da loja (incl. carga_trib)
    params = (json.loads(proj.parametros_json) if (proj and proj.parametros_json)
              else mod_orcamento_params.parametros_default_loja(cfg))
    desc_orc = orc.desconto_pct or 0.0
    # Orçamento de COMPLEMENTO (correção Fatia 3, 2026-07-21): cada ambiente entra pela
    # DIFERENÇA (à vista do XML complemento com os descontos do CONTRATO e o fator de custos
    # adicionais − à vista contratado — ver _complemento_diferencas). Params NEUTROS e desconto
    # global ZERO (o fator já carrega os custos adicionais; a única alavanca aqui é o desconto
    # por ambiente, sobre a diferença). Negociação nasce à vista.
    compl_diff, compl_cfa = {}, {}
    if getattr(orc, "complemento_pe", 0):
        linhas_c, _res = _complemento_diferencas(db, orc.projeto_id)
        for l in (linhas_c or []):
            if l["compl_carregado"]:
                compl_diff[l["pool_ambiente_id"]] = l["diferenca"]
                compl_cfa[l["pool_ambiente_id"]] = l["cfo_diferenca"]
        params = {}
        desc_orc = 0.0
    ambs, ids = [], []
    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
        if pa:
            if getattr(orc, "complemento_pe", 0):
                vbva = compl_diff.get(lk.pool_ambiente_id, 0.0)
                cfa = compl_cfa.get(lk.pool_ambiente_id, 0.0)
            else:
                vbva = pa.budget_total or 0.0
                cfa = pa.order_total or 0.0
            vbva = (vbva_override or {}).get(lk.pool_ambiente_id, vbva)
            ambs.append({"VBVA": vbva, "CFA": cfa,
                         "desc_amb_pct": float(lk.desconto_individual_pct or 0.0)})
            ids.append(lk.pool_ambiente_id)
    total_cliente = None
    try:
        fp = json.loads(orc.forma_pagamento) if orc.forma_pagamento else None
        if isinstance(fp, dict) and fp.get("total_cliente"):
            total_cliente = float(fp["total_cliente"])
    except Exception:
        total_cliente = None
    pool_proj = db.query(PoolAmbiente).filter_by(projeto_id=orc.projeto_id).all()
    n_total_proj = len(pool_proj) or None
    vbvo_proj = sum((pa.budget_total or 0.0) for pa in pool_proj) or None
    d0 = mod_negociacao.calcular_orcamento(ambs, params, desc_orc,
                                           n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    cust_fin = 0.0 if total_cliente is None else max(0.0, total_cliente - d0["VAVO"])
    d = mod_negociacao.calcular_orcamento(ambs, params, desc_orc, cust_fin=cust_fin,
                                          n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    for i, amb in enumerate(d.get("ambientes", [])):
        amb["id"] = ids[i] if i < len(ids) else None
    # v1: usa o Val_Liq do próprio orçamento como proxy do acumulado mensal do consultor.
    # Fase 2 troca por um acumulador mensal por (consultor, loja, mês). Ver spec/PROVISOES_E_VARIAVEIS.md.
    com_venda_pct = mod_provisoes.resolver_comissao_venda(cfg, d.get("Val_Liq", 0.0), desc_orc)
    prov = mod_provisoes.provisoes_orcamento(d, cfg, out_forn=(orc.out_forn or 0.0),
                                             com_venda_pct=com_venda_pct)
    d.update(prov)
    return d


def _registrar_provisao_venda(db, orc, por_id):
    """Grava (ou re-snapshota) a versão 'venda' das provisões a partir do breakdown atual."""
    d = _negociacao_breakdown(orc, db)
    itens = mod_provisoes.itens_provisao(d)
    existente = db.query(ProvisaoRegistro).filter_by(
        orcamento_id=orc.id, versao="venda").first()
    if existente:
        db.delete(existente); db.flush()
    db.add(ProvisaoRegistro(
        orcamento_id=orc.id, versao="venda",
        itens_json=json.dumps(itens, ensure_ascii=False),
        cfo=float(d.get("CFO") or 0), val_liq=float(d.get("Val_Liq") or 0),
        cust_var=float(d.get("Cust_Var") or 0), marg_cont=float(d.get("Marg_Cont") or 0),
        decisao=None, por_id=por_id))


def _recalcular_orcamento(orc, db):
    """Recalcula a negociação pelo motor e GRAVA: colunas sombra + valor_total/valor_liquido.
    `valor_total` vem da modalidade (forma_pagamento.total_cliente, já calculada com o VAVO);
    à vista ⇒ valor_total = VAVO. NÃO grava se contrato assinado (chamador já checa)."""
    d = _negociacao_breakdown(orc, db)
    orc.vbvo, orc.cfo, orc.vbno, orc.vavo = d["VBVO"], d["CFO"], d["VBNO"], d["VAVO"]
    orc.cust_ad, orc.val_liq = d["Cust_Ad"], d["Val_Liq"]
    orc.com_arq_orc, orc.pro_fid_orc = d["Com_Arq"], d["Pro_Fid"]
    orc.desc_tot_pct, orc.markup, orc.prov_imp = d["Desc_Tot"], d["Markup"], d["Prov_Imp"]
    orc.cust_fin, orc.val_cont = d["Cust_Fin"], d["Val_Cont"]
    # persistência autoritativa (cutover):
    orc.valor_total = d["Val_Cont"]
    orc.valor_liquido = d["Val_Liq"]


def _get_usuario_telefone(usuario_id: int, db) -> str:
    """Retorna telefone do usuário ou string vazia se não encontrado."""
    u = db.get(Usuario, usuario_id)
    return (u.telefone or "").strip() if u else ""


def _ambientes_valor_para_contrato(orcamento_id, db):
    """Lista [(nome_exibicao, valor_com_financeiro), ...] para a seção de ambientes
    do contrato. Reusa o breakdown do motor e o rateio de mod_contrato."""
    from mod_contrato import ambientes_valor_contrato
    orc = db.get(Orcamento, orcamento_id)
    if not orc:
        return []
    d = _negociacao_breakdown(orc, db)
    nome_por_id = {
        oa.pool_ambiente_id: oa.pool_ambiente.nome_exibicao
        for oa in db.query(OrcamentoAmbiente)
                    .filter_by(orcamento_id=orcamento_id)
                    .join(PoolAmbiente).all()
    }
    itens = [(nome_por_id.get(a.get("id"), ""), float(a.get("VAVA") or 0.0))
             for a in d.get("ambientes", [])]
    return ambientes_valor_contrato(itens, d.get("VAVO", 0.0), d.get("Val_Cont", 0.0))


def _previsoes_fases(req, n):
    """Previsões pedidas no desmembramento (2026-08-02): `req["previsoes"]` é uma lista paralela
    aos grupos, cada item {liberacao: 'AAAA-MM-DD', entrega: 'AAAA-MM-DD'} (ambos opcionais).
    Retorna n pares (liberacao_date|None, entrega_date|None); entrada inválida vira None."""
    from datetime import datetime as _dt
    prevs = req.get("previsoes") or []
    out = []
    for i in range(n):
        item = prevs[i] if (i < len(prevs) and isinstance(prevs[i], dict)) else {}
        par = []
        for chave in ("liberacao", "entrega"):
            v = item.get(chave)
            try:
                par.append(_dt.strptime(str(v)[:10], "%Y-%m-%d").date() if v else None)
            except ValueError:
                par.append(None)
        out.append(tuple(par))
    return out


def _valores_contrato_por_ambiente(orcamento_id, db):
    """({pool_ambiente_id: valor_de_contrato}, Val_Cont) — rateio do Val_Cont por ambiente (base da
    fração #5 das parcelas do desmembramento). Reusa o breakdown + mod_contrato.ambientes_valor_contrato."""
    from mod_contrato import ambientes_valor_contrato
    orc = db.get(Orcamento, orcamento_id)
    if not orc:
        return {}, 0.0
    d = _negociacao_breakdown(orc, db)
    ambs = d.get("ambientes", [])
    valores = ambientes_valor_contrato([("", float(a.get("VAVA") or 0.0)) for a in ambs],
                                       d.get("VAVO", 0.0), d.get("Val_Cont", 0.0))
    out = {}
    for a, (_n, v) in zip(ambs, valores):
        aid = a.get("id")
        if aid is not None:
            out[aid] = round(float(v or 0), 2)
    return out, round(float(d.get("Val_Cont") or 0), 2)


def _agenda_dados_projetos(db, ator, loja_id, proj_filtro=None):
    """Dados por projeto para o motor da Agenda (mod_agenda) — extraído do handler
    GET /api/agenda para reuso pelo painel de Montagem (Gantt/espelho). Aplica os escopos:
    posse (consultor), atribuição (operacional) e filtro opcional de projeto."""
    projs = (db.query(Projeto)
               .join(Contrato, Contrato.projeto_nome == Projeto.nome_safe)
               .filter(Projeto.loja_id == loja_id)
               .distinct().all())
    if proj_filtro:
        projs = [p for p in projs if p.nome_safe == proj_filtro]
    if _ve_apenas_proprios_projetos(ator.get("nivel")):
        projs = [p for p in projs if p.criado_por_id in (None, ator.get("id"))]
    if mod_escopo.escopo_por_atribuicao(ator):
        _atrib = _projetos_atribuidos_ao_usuario(db, ator.get("id"), loja_id)
        projs = [p for p in projs if p.nome_safe in _atrib]
    dados = []
    for pr in projs:
        if pr.status == "perdido":
            continue
        contrato = (db.query(Contrato).filter_by(projeto_nome=pr.nome_safe)
                      .order_by(Contrato.id.desc()).first())
        orc = db.get(Orcamento, contrato.orcamento_id) if contrato else None
        cli = db.get(Cliente, pr.cliente_id) if pr.cliente_id else None
        etapas = {}
        for e in db.query(CicloEtapa).filter_by(projeto_nome=pr.nome_safe).all():
            etapas[e.etapa_codigo] = {
                "prevista": e.data_prevista_conclusao,
                "concluida_em": (e.concluido_em
                                 if e.status in mod_ciclo.STATUS_CONCLUSIVOS else None)}
        parcs = (db.query(ParcelaProjeto).filter_by(projeto_nome=pr.nome_safe)
                   .order_by(ParcelaProjeto.ordem.asc()).all())
        cards = {c.parcela_id: c for c in
                 db.query(CicloLogistico)
                   .filter(CicloLogistico.projeto_nome == pr.nome_safe,
                           CicloLogistico.parcela_id != None).all()}  # noqa: E711
        card_glob = (db.query(CicloLogistico)
                       .filter_by(projeto_nome=pr.nome_safe, parcela_id=None)
                       .order_by(CicloLogistico.id.desc()).first())
        fases = []
        for f in parcs:
            card = cards.get(f.id)
            fases.append({"id": f.id, "ordem": f.ordem, "status": f.status,
                          "val_liq": f.val_liq_congelado,
                          "entrega_prevista": f.entrega_prevista,
                          "card_prazo_entrega": card.prazo_entrega if card else None,
                          "card_data_entrega": card.data_entrega if card else None})
        if not fases:
            _c16 = etapas.get("16") or {}
            fases = [{"id": None, "ordem": None, "status": None,
                      "val_liq": (orc.valor_liquido if orc else None),
                      "entrega_prevista": None,
                      "card_prazo_entrega": card_glob.prazo_entrega if card_glob else None,
                      "card_data_entrega": ((card_glob.data_entrega if card_glob else None)
                                            or _c16.get("concluida_em"))}]
        dados.append({"nome_safe": pr.nome_safe,
                      "cliente": (cli.nome if cli else None),
                      "val_liq": (orc.valor_liquido if orc else None),
                      "orcamento_id": (contrato.orcamento_id if contrato else None),
                      "previsao_medicao": pr.previsao_medicao,
                      "data_entrega": pr.data_entrega,
                      "etapas": etapas, "fases": fases})
    return dados


def _montagem_itens_enriquecidos(db, ator, loja_id, cfg_agenda, proj_filtro=None,
                                 papel="montagem"):
    """Itens do Gantt do OPERACIONAL enriquecidos (papel = montagem | projeto_executivo):
    ambientes da fase com Val_Liq por ambiente (referência da comissão) e o RESPONSÁVEL do
    papel no Mapa (específico do ambiente prevalece sobre projeto-inteiro). Base do GET
    /api/agenda/montagem (com ?papel=) e do aviso de conflito no POST de atribuição."""
    import mod_agenda as _mag
    dados = _agenda_dados_projetos(db, ator, loja_id, proj_filtro)
    itens = (_mag.itens_pe(dados, cfg_agenda) if papel == "projeto_executivo"
             else _mag.itens_montagem(dados, cfg_agenda))
    por_proj = {d["nome_safe"]: d for d in dados}
    cache_liq, cache_atr, cache_nome = {}, {}, {}
    def _nome_alvo(fid, tid):
        chave = ("f:%d" % fid) if fid else ("t:%d" % tid)
        if chave not in cache_nome:
            alvo = db.get(Funcionario, fid) if fid else db.get(Terceiro, tid)
            cache_nome[chave] = alvo.nome if alvo else None
        return chave, cache_nome[chave]
    for it in itens:
        d = por_proj.get(it["projeto"]) or {}
        oid = d.get("orcamento_id")
        if oid not in cache_liq:
            cache_liq[oid] = _liquidos_contrato_por_ambiente(oid, db)[0] if oid else {}
        if it["projeto"] not in cache_atr:
            cache_atr[it["projeto"]] = _atribuicoes_dicts(db, it["projeto"])
        liq, atribs = cache_liq[oid], cache_atr[it["projeto"]]
        if it.get("fase_id"):
            amb_ids = [a.pool_ambiente_id for a in
                       db.query(ParcelaAmbiente).filter_by(parcela_id=it["fase_id"]).all()]
        else:
            amb_ids = ([lk.pool_ambiente_id for lk in
                        db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()]
                       if oid else [])
        pa_nome = {pa.id: (pa.nome_exibicao or pa.nome)
                   for pa in db.query(PoolAmbiente).filter(PoolAmbiente.id.in_(amb_ids)).all()} \
            if amb_ids else {}
        ambs, montadores = [], {}
        for aid in amb_ids:
            # plural (2026-08-06): Montagem aceita vários executores por ambiente —
            # `resolver_responsaveis` devolve a lista inteira (PE/Medição seguem com 0 ou 1,
            # é o próprio banco quem garante isso, não esta leitura).
            resps = mod_escopo.resolver_responsaveis(atribs, aid, papel)
            ms = []
            for resp in resps:
                chave, nome = _nome_alvo(resp.get("funcionario_id"), resp.get("terceiro_id"))
                m = {"chave": chave, "nome": nome}
                ms.append(m)
                montadores[chave] = m
            ambs.append({"id": aid, "nome": pa_nome.get(aid, ""),
                         "val_liq": liq.get(aid), "montadores": ms,
                         # compat: quem só quer "tem alguém?" (1º da lista, ou None)
                         "montador": (ms[0] if ms else None)})
        it["ambientes"] = ambs
        it["montadores"] = list(montadores.values())
    return itens


def _liquidos_contrato_por_ambiente(orcamento_id, db):
    """({pool_ambiente_id: Val_Liq_Amb}, Val_Liq) — rateio do Val_Liq (VAVO − Cust_Ad, a base
    das comissões e da Agenda) por ambiente, proporcional ao VAVA, com o resíduo no último
    (Σ exata). Gêmeo de _valores_contrato_por_ambiente; mesma lógica de
    mod_comissao._liquidos_por_ambiente, mas com soma exata p/ congelamento (Agenda Fatia 1)."""
    from mod_contrato import ambientes_valor_contrato
    orc = db.get(Orcamento, orcamento_id)
    if not orc:
        return {}, 0.0
    d = _negociacao_breakdown(orc, db)
    ambs = d.get("ambientes", [])
    valores = ambientes_valor_contrato([("", float(a.get("VAVA") or 0.0)) for a in ambs],
                                       d.get("VAVO", 0.0), d.get("Val_Liq", 0.0))
    out = {}
    for a, (_n, v) in zip(ambs, valores):
        aid = a.get("id")
        if aid is not None:
            out[aid] = round(float(v or 0), 2)
    return out, round(float(d.get("Val_Liq") or 0), 2)


def _reparar_parametros_segmentados(db):
    """Reparo ÚNICO (idempotente) do dano do bug 🔴 do E2E (2026-08-03): projetos assinados
    ANTES do fix ficaram com parametros_json contendo SÓ a segmentação (os defaults vivos
    foram descartados no congelamento). Restaura os defaults da loja POR BAIXO das chaves
    existentes (a segmentação congelada prevalece). Retorna nº de projetos reparados."""
    from mod_orcamento_params import parametros_default_loja
    n = 0
    for pj in db.query(Projeto).filter(Projeto.parametros_json.isnot(None)).all():
        try:
            par = json.loads(pj.parametros_json)
        except ValueError:
            continue
        if not isinstance(par, dict) or not par:
            continue
        if set(par.keys()) <= {"pct_mercadoria", "pct_servico"}:
            base = parametros_default_loja(_cfg_financeira_loja(db, pj.loja_id))
            base.update(par)
            pj.parametros_json = json.dumps(base, ensure_ascii=False)
            n += 1
    db.flush()
    return n


def _backfill_val_liq_fases(db):
    """Backfill ÚNICO (idempotente) do val_liq_congelado em fases legadas (NULL): melhor
    aproximação disponível = motor atual, somando o rateio líquido dos ambientes de cada fase.
    Roda no start (fail-soft por projeto). Retorna nº de fases preenchidas."""
    pendentes = (db.query(ParcelaProjeto)
                   .filter(ParcelaProjeto.val_liq_congelado == None).all())  # noqa: E711
    por_projeto = {}
    for p in pendentes:
        por_projeto.setdefault(p.projeto_nome, []).append(p)
    n = 0
    for nome, fases in por_projeto.items():
        try:
            oid = next((f.orcamento_id for f in fases if f.orcamento_id), None)
            if not oid:
                continue
            liq, _total = _liquidos_contrato_por_ambiente(oid, db)
            for f in fases:
                ambs = db.query(ParcelaAmbiente).filter_by(parcela_id=f.id).all()
                f.val_liq_congelado = round(sum(liq.get(a.pool_ambiente_id, 0.0) for a in ambs), 2)
                n += 1
            db.flush()
        except Exception as e:
            db.rollback()
            logging.getLogger(__name__).warning(
                "backfill val_liq_congelado falhou no projeto %s: %s", nome, e)
    db.commit()
    return n


def _montar_dados_projeto_para_contrato(nome_safe: str, orcamento_id: int, db) -> tuple:
    """
    Retorna (projeto_dict, cliente_dict, orcamento_dict) para geração do contrato.
    Lança ValueError se dados essenciais estiverem faltando.
    """
    import json as _json
    proj_path = os.path.join(PROJETOS_DIR, nome_safe, "projeto.json")
    if not os.path.exists(proj_path):
        raise ValueError(f"Projeto não encontrado: {nome_safe}")
    with open(proj_path, encoding="utf-8") as f:
        proj = _json.load(f)

    orcamento = db.get(Orcamento, orcamento_id)
    if not orcamento or orcamento.projeto_id != nome_safe:
        raise ValueError(f"Orçamento {orcamento_id} não pertence ao projeto {nome_safe}")

    ambientes_orc = db.query(OrcamentoAmbiente)\
                      .filter_by(orcamento_id=orcamento_id)\
                      .join(PoolAmbiente)\
                      .all()
    nomes_ambientes = [oa.pool_ambiente.nome_exibicao for oa in ambientes_orc]

    cliente_id = proj.get("cliente_id")
    # Fallback: projetos_meta também guarda cliente_id para projetos novos
    if not cliente_id:
        p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
        if p_meta:
            cliente_id = p_meta.cliente_id
    cliente = db.get(Cliente, cliente_id) if cliente_id else None

    projeto_dict = {
        "nome_projeto": proj.get("nome_projeto", nome_safe),
        "criado_em":    proj.get("criado_em", ""),
        "consultor":    proj.get("consultor_nome", ""),
    }
    if cliente:
        cliente_dict = _cliente_dict(cliente)
        # Preenche campos vazios do banco com o que foi salvo no projeto.json
        cli_proj = proj.get("cliente") or {}
        for campo in ("nome", "cpf", "email", "telefone"):
            if not cliente_dict.get(campo) and cli_proj.get(campo):
                cliente_dict[campo] = cli_proj[campo]
    else:
        # Projeto legado sem registro no banco: usa dados do projeto.json
        cli_proj = proj.get("cliente") or {}
        cliente_dict = {
            "nome":     cli_proj.get("nome")  or proj.get("nome_cliente", ""),
            "cpf":      cli_proj.get("cpf")   or "",
            "email":    cli_proj.get("email") or "",
            "telefone": cli_proj.get("telefone") or "",
            "logradouro": "", "numero": "", "complemento": "",
            "bairro": "", "cidade": "", "estado": "", "cep": "",
            "inst_mesmo_residencial": True,
            "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
            "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
        }
    orcamento_dict = {
        "nome":            orcamento.nome,
        "valor_total":     orcamento.valor_total  or 0.0,
        "valor_liquido":   orcamento.valor_liquido or 0.0,
        "forma_pagamento": orcamento.forma_pagamento or "",
        "ambientes":       nomes_ambientes,
    }
    return projeto_dict, cliente_dict, orcamento_dict


def _parceiro_dict(p, db=None) -> dict:
    d = {
        "id":                  p.id,
        "nome":                p.nome,
        "cpf_cnpj":            p.cpf_cnpj            or "",
        "tipo":                p.tipo                 or "",
        "email":               p.email                or "",
        "telefone":            p.telefone             or "",
        "whatsapp":            p.whatsapp             or "",
        "comissao_padrao_pct": p.comissao_padrao_pct  if p.comissao_padrao_pct is not None else 0.0,
        "observacoes":         p.observacoes          or "",
        "pix":                 p.pix                  or "",
        "abrangencia":         p.abrangencia          or "loja",
        "rede_id":             p.rede_id,
        "criado_em":           p.criado_em.strftime("%Y-%m-%d") if p.criado_em else "",
        "lojas":               [],
    }
    if db is not None:
        vincs = db.query(ParceiroLoja).filter_by(parceiro_id=p.id).all()
        d["lojas"] = [{"loja_id": v.loja_id,
                       "comissao_padrao_pct": v.comissao_padrao_pct or 0.0}
                      for v in vincs]
    return d


def _aplicar_abrangencia_parceiro(db, p, req, ator):
    """Grava abrangencia/rede_id no parceiro e sincroniza os vínculos parceiro_lojas.
    Retorna lista de erros (vazia se ok). Só vincula lojas visíveis ao ator."""
    abr = (req.get("abrangencia") or "loja").strip()
    # Usuário de loja: sem seleção explícita de lojas, o parceiro entra na loja ATIVA do
    # ator. O seletor de lojas é conveniência administrativa; consultor/gerente não precisa
    # dele — "no mínimo", o parceiro entra na loja de quem o cadastrou.
    if abr == "loja" and not (req.get("lojas") or []):
        loja_ativa = ator.get("active_loja_id") or ator.get("loja_id")
        if loja_ativa is not None:
            req = {**req, "lojas": [{"loja_id": loja_ativa,
                                     "comissao_padrao_pct": req.get("comissao_padrao_pct") or 0}]}
    erros = mod_tenancy.validar_abrangencia_parceiro(req)
    if erros:
        return erros
    p.abrangencia = abr
    if abr == "rede":
        rede_id = req.get("rede_id")
        p.rede_id = rede_id
        # super_admin/admin_rede via política pura; diretor pode a rede da PRÓPRIA loja
        # (spec: o diretor também cria parceiro de abrangência 'rede').
        permitido = mod_tenancy.pode_ver_rede(ator, rede_id)
        if not permitido and ator.get("loja_id") is not None and rede_id is not None:
            loja_ator = db.get(Loja, ator.get("loja_id"))
            permitido = bool(loja_ator and loja_ator.rede_id == rede_id)
        if not permitido:
            return ["Rede fora do seu escopo."]
        db.query(ParceiroLoja).filter_by(parceiro_id=p.id).delete()
        return []
    p.rede_id = None
    lojas_req = req.get("lojas") or []
    db.query(ParceiroLoja).filter_by(parceiro_id=p.id).delete()
    for item in lojas_req:
        lid = item.get("loja_id")
        loja = db.get(Loja, lid) if lid else None
        if not loja or not mod_tenancy.pode_ver_loja(
                ator, {"id": loja.id, "rede_id": loja.rede_id}):
            return [f"Loja {lid} fora do seu escopo."]
        db.add(ParceiroLoja(parceiro_id=p.id, loja_id=lid,
                            comissao_padrao_pct=float(item.get("comissao_padrao_pct") or 0),
                            ativo=1))
    return []


def _rede_dict(r) -> dict:
    return {
        "id":        r.id,
        "nome":      r.nome,
        "cnpj":      r.cnpj or "",
        "ativo":     bool(r.ativo),
        "criado_em": r.criado_em.strftime("%Y-%m-%d") if r.criado_em else "",
    }


def _loja_dict(l) -> dict:
    return {
        "id":          l.id,
        "rede_id":     l.rede_id,
        "nome":        l.nome,
        "cnpj":        l.cnpj        or "",
        "codigo":      l.codigo      or "",
        "telefone":    l.telefone    or "",
        "email":       l.email       or "",
        "responsavel": l.responsavel or "",
        "cep":         l.cep         or "",
        "logradouro":  l.logradouro  or "",
        "numero":      l.numero      or "",
        "complemento": l.complemento or "",
        "bairro":      l.bairro      or "",
        "cidade":      l.cidade      or "",
        "estado":      l.estado      or "",
        "testemunha1_nome": l.testemunha1_nome or "",
        "testemunha1_cpf":  l.testemunha1_cpf  or "",
        "testemunha2_nome": l.testemunha2_nome or "",
        "testemunha2_cpf":  l.testemunha2_cpf  or "",
        "pct_mercadoria":   l.pct_mercadoria if l.pct_mercadoria is not None else 65.0,
        "pct_servico":      l.pct_servico    if l.pct_servico    is not None else 35.0,
        "loja_mae_id": l.loja_mae_id,
        "tipo":        l.tipo or "loja",
        "ativo":       bool(l.ativo),
        "criado_em":   l.criado_em.strftime("%Y-%m-%d") if l.criado_em else "",
    }


def _ator_dict(db, usuario_sessao, header_loja_id=None):
    """Re-consulta o usuário logado e resolve a loja ativa (multi-loja)."""
    if header_loja_id is None:
        header_loja_id = _REQ_LOJA_ATIVA
    u = db.get(Usuario, usuario_sessao.get("id"))
    if not u:
        return {"nivel": usuario_sessao.get("nivel"), "loja_id": None,
                "rede_id": None, "active_loja_id": None, "lojas_ids": []}
    membership = lojas_acessiveis_ids(db, u.id, u.nivel, u.loja_id)
    is_super = (u.nivel == "super_admin")
    active = mod_tenancy.resolver_loja_ativa(membership, header_loja_id, u.loja_id, is_super=is_super)
    # super_admin confia no header pra "entrar" na loja; mas header apontando loja inexistente
    # não pode virar loja ativa 'válida' (viraria tela vazia silenciosa) — trata como sem loja.
    if is_super and active is not None and db.get(Loja, active) is None:
        active = None
    # Função do Funcionário vinculado (re-chave da visão operacional, 2026-08-03): alimenta
    # mod_escopo.escopo_por_atribuicao/visao_do_papel. `id` incluído junto (predicados de
    # posse/atribuição usam ator.get("id")).
    from auth.auth import _funcao_do_usuario as _fdu
    _funcao_nome, _funcao_papeis = _fdu(u)
    return {"id": u.id, "nivel": u.nivel, "loja_id": u.loja_id, "rede_id": u.rede_id,
            "active_loja_id": active, "lojas_ids": membership,
            "funcao_nome": _funcao_nome, "funcao_papeis": _funcao_papeis}


def _resolver_pdf_contrato(pdf_path):
    """Resolve o caminho do arquivo do contrato de forma robusta. O `pdf_path` salvo pode ser
    um caminho ABSOLUTO (ex.: Windows 'E:/...') que não resolve neste ambiente (WSL/Linux,
    case-sensitive); nesse caso cai para CONTRATOS_DIR/<basename>. Retorna o caminho válido
    (existente) ou None."""
    if not pdf_path:
        return None
    if os.path.exists(pdf_path):
        return pdf_path
    from mod_contrato import CONTRATOS_DIR
    base = os.path.basename(str(pdf_path).replace('\\', '/'))
    alt = os.path.join(CONTRATOS_DIR, base)
    return alt if os.path.exists(alt) else None


def _obj_da_loja(db, Model, pk, loja_id):
    """Retorna o objeto se existir E pertencer à loja `loja_id`; senão None.
    None cobre 'sem id', 'não existe' e 'é de outra loja'."""
    if not pk or loja_id is None:
        return None
    obj = db.get(Model, pk)
    if obj is None or getattr(obj, "loja_id", None) != loja_id:
        return None
    return obj


def _projeto_da_loja(db, nome_safe, loja_id):
    """Retorna o projetos_meta (PK = nome_safe) se pertencer à loja; senão None.
    Ponto de escopo das entidades 'por projeto' (pool/medição/ciclo/contrato).
    Delega em _obj_da_loja para manter uma única fonte da regra de escopo."""
    return _obj_da_loja(db, Projeto, nome_safe, loja_id)


def _projeto_visivel_da_loja(db, nome_safe, loja_id, usuario):
    """Como `_projeto_da_loja`, MAS também aplica o escopo por projetista (Consultor só vê os que
    criou; gerência/atribuído/demais conforme `_projeto_visivel_ao_ator`). Devolve o meta ou None.
    Usado nos endpoints da CONVERSA do projeto (achado da Vera 2026-07-28): loja sozinha não basta."""
    meta = _projeto_da_loja(db, nome_safe, loja_id)
    if meta is None or not _projeto_visivel_ao_ator(meta, usuario, db):
        return None
    return meta


# ── Mapa de Atribuições (Regras_Funcoes_Perfis_Atribuicoes §4/§5) — helpers de I/O; a REGRA pura
#    mora em mod_escopo. ────────────────────────────────────────────────────────────────────────
def _pode_editar_mapa(nivel):
    """Abrir/editar o Mapa: Gerência+ (autorizar/aprovar_financeiro) ou Supervisor de Montagem."""
    return bool(nivel) and (perfis.pode(nivel, "autorizar") or perfis.pode(nivel, "aprovar_financeiro")
                            or nivel == "supervisor_montagem")


def _bloqueio_comercial(ator):
    """Visão do papel (Regras §3): operacional (PE/Medidor/Montagem) NUNCA vê o comercial
    (negociação, valores, margem, comissão). Retorna a msg de erro (403) ou None."""
    if mod_escopo.visao_do_papel(ator) == "operacional":
        return "Sem acesso ao comercial (visão operacional)."
    return None


def _usuario_de_pdv(usuario):
    """True se a loja do usuário é um Ponto de Venda (loja com mãe, spec 2026-07-22)."""
    lid = (usuario or {}).get("loja_id")
    if not lid:
        return False
    db = get_session()
    try:
        l = db.get(Loja, lid)
        return bool(l is not None and getattr(l, "loja_mae_id", None))
    finally:
        db.close()


def _sem_acesso_modulo(usuario, modulo_id, handler=None):
    """True se o PERFIL do usuário não acessa o módulo (Perfil-4 rev2 §2, matriz de acesso).
    Se `handler` for dado, honra um grant de step-up (senha de quem tem o perfil) na sessão.

    PDV (loja com mãe, spec 2026-07-22): Financeiro e Folha do PDV são operados pela
    loja-mãe — bloqueados aqui para QUALQUER perfil do PDV, sem step-up (QA Vera 🟠).
    Os lançamentos do razão do PDV seguem vivos (o wiring não passa por aqui)."""
    if modulo_id in ("financeiro", "folha") and _usuario_de_pdv(usuario):
        return True
    if perfis.acessa_modulo((usuario or {}).get("nivel"), modulo_id):
        return False
    if handler is not None:
        from auth.auth_routes import get_token_from_cookie
        token = get_token_from_cookie(handler.headers.get("Cookie", ""))
        if _stepup_valido(token, modulo_id):
            return False
    return True


# Etapa do ciclo → papel operacional do Mapa (Regras §7). O Mapa é o default do responsável da fase.
_ETAPA_PAPEL = {
    "9": "medicao", "10": "medicao",
    "11": "projeto_executivo", "11a": "projeto_executivo", "11b": "projeto_executivo",
    "11c": "projeto_executivo", "11e": "projeto_executivo",
    "17": "montagem", "18": "assistencia",
}

# Chat Fatia 2 (spec seção 6): defaults automáticos do responsável por FAIXA para as etapas
# que o _ETAPA_PAPEL (Mapa de Atribuições) não cobre. Precedência continua a do v12:
# responsavel_funcionario_id (manual OU transferido pelo chat) > default automático > nada.
_ETAPAS_FAIXA_VENDAS     = frozenset({"1", "2", "3", "4", "7"})
_ETAPAS_FAIXA_FINANCEIRO = frozenset({"8", "11d", "21"})
_ETAPAS_FAIXA_LOGISTICA  = frozenset({"12", "13", "14", "15", "16"})
_FUNCAO_FINANCEIRO = "Gerente Administrativo/Financeiro"
_FUNCAO_LOGISTICA  = "Assistente Logístico"


def _funcionario_do_usuario(db, usuario_id):
    """Ponte Usuário↔Funcionário (uma só, usada pelo default de Vendas e pelo resolver do
    bloqueador): Usuario.funcionario_id; fallback: o reverso Funcionario.usuario_id."""
    if not usuario_id:
        return None
    u = db.get(Usuario, usuario_id)
    if u is not None and u.funcionario_id:
        return u.funcionario_id
    f = db.query(Funcionario).filter_by(usuario_id=usuario_id).first()
    return f.id if f else None


def _consultor_funcionario_id(db, nome_safe):
    """Default de VENDAS: Briefing.consultor_id (Usuario) → Funcionario pela ponte única.
    Consultor sem Funcionário vinculado → None (etapa fica sem default; não é erro)."""
    b = (db.query(Briefing).filter_by(projeto_nome=nome_safe)
           .order_by(Briefing.id.desc()).first())
    if b is None or not b.consultor_id:
        return None
    return _funcionario_do_usuario(db, b.consultor_id)


def _responsavel_funcionario_etapa(db, nome_safe, loja_id, etapa_codigo):
    """Responsável efetivo (funcionario_id) de UMA etapa — mesma cadeia do GET /ciclo:
    override > Mapa de Atribuições > default de faixa > CRIADOR do projeto. Standalone para o
    PATCH (passagem oficial automática, decisão 17). None se nada resolve."""
    et = (db.query(CicloEtapa)
            .filter_by(projeto_nome=nome_safe, etapa_codigo=etapa_codigo).first())
    if et is not None and et.responsavel_funcionario_id:
        return et.responsavel_funcionario_id
    papel = _ETAPA_PAPEL.get(etapa_codigo)
    a = mod_escopo.resolver_responsavel(_atribuicoes_dicts(db, nome_safe), None, papel) \
        if papel else None
    if a and a.get("funcionario_id"):
        return a.get("funcionario_id")
    fid = _default_responsavel_faixa(db, nome_safe, loja_id, etapa_codigo, {})
    if fid:
        return fid
    pm = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
    return _funcionario_do_usuario(db, pm.criado_por_id) if pm and pm.criado_por_id else None


def _default_responsavel_faixa(db, nome_safe, loja_id, etapa_codigo, cache):
    """Resolve (e cacheia por request) o default da faixa da etapa — mesma filosofia do
    resolver-e-cachear que o GET /ciclo já usa para o Mapa de Atribuições."""
    import mod_chat as _mchat
    if etapa_codigo in _ETAPAS_FAIXA_VENDAS:
        faixa = "vendas"
    elif etapa_codigo in _ETAPAS_FAIXA_FINANCEIRO:
        faixa = "financeiro"
    elif etapa_codigo in _ETAPAS_FAIXA_LOGISTICA:
        faixa = "logistica"
    else:
        return None
    if faixa not in cache:
        if faixa == "vendas":
            cache[faixa] = _consultor_funcionario_id(db, nome_safe)
        elif faixa == "financeiro":
            cache[faixa] = _mchat.funcionario_por_funcao(db, loja_id, _FUNCAO_FINANCEIRO)
        else:
            cache[faixa] = _mchat.funcionario_por_funcao(db, loja_id, _FUNCAO_LOGISTICA)
    return cache[faixa]


def _ambientes_do_projeto(db, nome_safe):
    """[{id, nome}] dos PoolAmbiente do projeto (para a grade do Mapa)."""
    return [{"id": pa.id, "nome": pa.nome_exibicao or pa.nome}
            for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome_safe)
                        .order_by(PoolAmbiente.id.asc()).all()]


def _atribuicoes_dicts(db, nome_safe):
    """Atribuições vigentes do projeto como dicts puros (para mod_escopo)."""
    return [{"id": a.id, "papel": a.papel, "pool_ambiente_id": a.pool_ambiente_id,
             "funcionario_id": a.funcionario_id, "terceiro_id": a.terceiro_id}
            for a in db.query(AtribuicaoAmbiente).filter_by(projeto_nome=nome_safe).all()]


def _serializar_atribuicoes(db, nome_safe):
    """Atribuições do projeto com nomes resolvidos (funcionário/terceiro, função, ambiente)."""
    regs = db.query(AtribuicaoAmbiente).filter_by(projeto_nome=nome_safe).all()
    fio = {f.id: f for f in db.query(Funcionario).filter(Funcionario.id.in_(
        [r.funcionario_id for r in regs if r.funcionario_id])).all()} if regs else {}
    ter = {t.id: t for t in db.query(Terceiro).filter(Terceiro.id.in_(
        [r.terceiro_id for r in regs if r.terceiro_id])).all()} if regs else {}
    fnc = {}
    fids = {o.funcao_id for o in list(fio.values()) + list(ter.values()) if getattr(o, "funcao_id", None)}
    if fids:
        fnc = {f.id: f.nome for f in db.query(Funcao).filter(Funcao.id.in_(fids)).all()}
    amb = {pa.id: (pa.nome_exibicao or pa.nome)
           for pa in db.query(PoolAmbiente).filter_by(projeto_id=nome_safe).all()}
    out = []
    for r in regs:
        alvo = fio.get(r.funcionario_id) if r.funcionario_id else ter.get(r.terceiro_id)
        out.append({
            "id": r.id, "papel": r.papel, "pool_ambiente_id": r.pool_ambiente_id,
            "ambiente_nome": amb.get(r.pool_ambiente_id, "(projeto inteiro)") if r.pool_ambiente_id else "(projeto inteiro)",
            "funcionario_id": r.funcionario_id, "terceiro_id": r.terceiro_id,
            "responsavel_nome": (alvo.nome if alvo else ""),
            "funcao_nome": fnc.get(getattr(alvo, "funcao_id", None), "") if alvo else "",
        })
    return out


# ── Perfil fiscal: lógica comum entre o dono LOJA (loja.emitente_id) e o dono
#    REDE (rede.emitente_central_id). Os handlers só resolvem o Emitente do dono
#    (via _emitente_do_dono) e delegam a estas funções puras. ────────────────────
def _opcoes_emitente(db, kind, obj):
    """Opções de Emitente que um dono (loja|rede) pode escolher no Perfil de Emissão.
    Loja: o próprio CNPJ (self) + a central da rede (se houver). Rede: só a central."""
    ops = []
    if kind == "loja":
        if getattr(obj, "emitente_id", None):
            e = db.get(Emitente, obj.emitente_id)
            if e:
                ops.append({"id": e.id,
                            "label": "Este CNPJ — " + (e.razao_social or e.cnpj or str(e.id)),
                            "papel": "self"})
        if getattr(obj, "rede_id", None):
            r = db.get(Rede, obj.rede_id)
            if r and r.emitente_central_id:
                c = db.get(Emitente, r.emitente_central_id)
                if c:
                    ops.append({"id": c.id,
                                "label": "Central da rede — " + (c.razao_social or c.cnpj or str(c.id)),
                                "papel": "central"})
    else:
        if getattr(obj, "emitente_central_id", None):
            c = db.get(Emitente, obj.emitente_central_id)
            if c:
                ops.append({"id": c.id,
                            "label": "Central da rede — " + (c.razao_social or c.cnpj or str(c.id)),
                            "papel": "central"})
    return ops


def _perfil_emissao_get(db, kind, owner_id, obj):
    """Estado do Perfil de Emissão do dono: emitente_id de cada tipo_doc + opções."""
    out = {"ok": True, "opcoes": _opcoes_emitente(db, kind, obj)}
    for tipo in ("produto", "servico"):
        pe = (db.query(PerfilEmissao)
                .filter_by(owner_tipo=kind, owner_id=owner_id, tipo_doc=tipo).first())
        out[tipo] = pe.emitente_id if pe else None
    return out


def _perfil_emissao_put(db, kind, owner_id, obj, req):
    """Upsert/delete das linhas de PerfilEmissao conforme {produto, servico}.
    Só toca um tipo se a chave estiver presente no corpo. Valida contra as opções.
    Retorna (payload_ou_erro, code)."""
    opcoes_ids = [o["id"] for o in _opcoes_emitente(db, kind, obj)]
    for tipo in ("produto", "servico"):
        if tipo not in req:
            continue
        val = req.get(tipo)
        pe = (db.query(PerfilEmissao)
                .filter_by(owner_tipo=kind, owner_id=owner_id, tipo_doc=tipo).first())
        if val is None:
            if pe:
                db.delete(pe)
            continue
        try:
            val = int(val)
        except (TypeError, ValueError):
            return {"ok": False, "erro": "emitente_id inválido"}, 400
        if val not in opcoes_ids:
            return {"ok": False,
                    "erro": "emitente %s não é opção válida para este dono" % val}, 400
        if pe:
            pe.emitente_id = val
        else:
            db.add(PerfilEmissao(owner_tipo=kind, owner_id=owner_id,
                                 tipo_doc=tipo, emitente_id=val))
    db.commit()
    return _perfil_emissao_get(db, kind, owner_id, obj), 200


def _emitente_do_dono(db, kind, obj):
    """Devolve (Emitente|None, nome_do_atributo_FK) do dono (loja/rede)."""
    attr = "emitente_id" if kind == "loja" else "emitente_central_id"
    eid = getattr(obj, attr, None)
    return (db.get(Emitente, eid) if eid else None), attr


def _fiscal_criar_emitente(db, obj, attr, rede_id):
    """Cria um Emitente novo (homologação) e o linka ao dono. Retorna o Emitente."""
    em = Emitente(ambiente_ativo="homologacao", rede_id=rede_id)
    db.add(em); db.flush()
    setattr(obj, attr, em.id)
    return em


def _fiscal_get(em):
    """Payload do GET do perfil fiscal. NUNCA vaza token (só *_definido)."""
    from fiscal import mod_fiscal, fiscal_cripto
    if not em:
        padrao = mod_fiscal.emitente_padrao_teste()
        placeholders = padrao.pop("placeholders")
        return {"ok": True, "existe": False, "perfil": padrao,
                "placeholders": placeholders, "ambiente_ativo": "homologacao",
                "token_homolog_definido": False, "token_prod_definido": False,
                "cert_validade": None, "cert_cnpj": None}
    perfil = {c: getattr(em, c) for c in (
        "razao_social", "inscricao_estadual", "inscricao_municipal", "regime_tributario",
        "csosn_padrao", "csosn_contribuinte", "cfop_dentro_uf", "cfop_fora_uf",
        "serie_nfe", "discrimina_impostos", "cnae_servico", "cod_servico_municipio",
        "aliquota_iss", "retencao_json", "municipio_ibge", "papel_cnpj",
        "logradouro", "numero", "bairro", "cidade", "uf", "cep")}
    return {"ok": True, "existe": True, "perfil": perfil,
            "placeholders": json.loads(em.placeholders_json or "[]"),
            "ambiente_ativo": em.ambiente_ativo,
            "token_homolog_definido": fiscal_cripto.token_definido(em.focus_token_homolog_enc),
            "token_prod_definido": fiscal_cripto.token_definido(em.focus_token_prod_enc),
            "cert_validade": em.cert_validade.isoformat() if em.cert_validade else None,
            "cert_cnpj": em.cert_cnpj}


def _fiscal_put_config(em, req):
    """Aplica a allowlist de config não-secreta no Emitente (já resolvido/criado)."""
    for c in ("razao_social", "inscricao_estadual", "inscricao_municipal", "regime_tributario",
              "csosn_padrao", "csosn_contribuinte", "cfop_dentro_uf", "cfop_fora_uf",
              "serie_nfe", "discrimina_impostos", "cnae_servico", "cod_servico_municipio",
              "aliquota_iss", "retencao_json", "municipio_ibge", "papel_cnpj",
              "logradouro", "numero", "bairro", "cidade", "uf", "cep",
              "cert_validade", "cert_cnpj"):
        if c in req:
            setattr(em, c, req[c])
    if "placeholders" in req:
        em.placeholders_json = json.dumps(req["placeholders"], ensure_ascii=False)


def _fiscal_put_segredos(em, req):
    """Grava tokens cifrados (write-only). None limpa; "" mantém."""
    from fiscal import fiscal_cripto
    for campo, col in (("focus_token_homolog", "focus_token_homolog_enc"),
                       ("focus_token_prod", "focus_token_prod_enc")):
        if campo in req:
            v = req[campo]
            if v is None:
                setattr(em, col, None)
            elif v != "":
                setattr(em, col, fiscal_cripto.encrypt(v))


def _fiscal_put_ambiente(em, amb):
    """Troca o ambiente ativo. Retorna (ok, erro). Guarda produção via placeholders."""
    from fiscal import mod_fiscal
    if amb == "producao":
        placeholders = json.loads(em.placeholders_json or "[]")
        if not mod_fiscal.pode_ativar_producao(placeholders):
            return False, ("Não é possível ativar produção com valores de teste pendentes: "
                           + ", ".join(placeholders))
    em.ambiente_ativo = amb
    return True, None


def _enriquecer_cliente_do_projeto(proj, db):
    """Atualiza o bloco 'cliente' do projeto.json (snapshot) com os dados VIVOS do cadastro
    (tabela clientes), para a tela de etapas nunca exibir contato defasado após uma edição."""
    if not isinstance(proj, dict):
        return
    cid = proj.get("cliente_id") or (proj.get("cliente") or {}).get("id")
    if not cid:
        return
    try:
        c = db.get(Cliente, int(cid))
    except (TypeError, ValueError):
        return
    if c is not None:
        proj["cliente"] = {**(proj.get("cliente") or {}), **_cliente_dict(c)}


def _parceiro_visivel_loja(db, parceiro, loja_id):
    """True se o parceiro é visível à loja `loja_id` (abrangência 'loja' com vínculo,
    ou 'rede' com a rede da loja)."""
    if parceiro is None or loja_id is None:
        return False
    abr = (getattr(parceiro, "abrangencia", None) or "loja")
    if abr == "loja":
        vin = db.query(ParceiroLoja).filter(
            ParceiroLoja.parceiro_id == parceiro.id,
            ParceiroLoja.loja_id == loja_id).first()
        return vin is not None
    if abr == "rede":
        loja = db.get(Loja, loja_id)
        return loja is not None and loja.rede_id is not None and parceiro.rede_id == loja.rede_id
    return False


def _ve_apenas_proprios_projetos(nivel):
    """True se o perfil vê só os projetos que criou (base operador). Gerência+ — e os
    operacionais de pós-venda — veem todos da loja. Dirigido pela BASE (perfis.py) para
    sobreviver à migração de nivel e escopar corretamente perfis customizados."""
    return perfis.base(nivel) == "operador"


def _usuario_ids_atribuidos_projeto(db, nome_safe):
    """Conjunto de usuario_id com QUALQUER atribuição no projeto (Mapa) — resolve
    Funcionario.usuario_id / Terceiro.usuario_id. Alimenta mod_escopo (Regras §5)."""
    regs = db.query(AtribuicaoAmbiente).filter_by(projeto_nome=nome_safe).all()
    if not regs:
        return set()
    fids = {r.funcionario_id for r in regs if r.funcionario_id}
    tids = {r.terceiro_id for r in regs if r.terceiro_id}
    uids = set()
    if fids:
        uids |= {u for (u,) in db.query(Funcionario.usuario_id).filter(Funcionario.id.in_(fids)).all() if u}
    if tids:
        uids |= {u for (u,) in db.query(Terceiro.usuario_id).filter(Terceiro.id.in_(tids)).all() if u}
    return uids


def _projetos_atribuidos_ao_usuario(db, usuario_id, loja_id):
    """Nomes dos projetos (na loja) onde o login `usuario_id` está atribuído no Mapa (via
    Funcionário/Terceiro vinculado). Vazio se o login não tem vínculo/atribuição."""
    if not usuario_id:
        return set()
    from sqlalchemy import or_
    fids = [r[0] for r in db.query(Funcionario.id).filter(Funcionario.usuario_id == usuario_id).all()]
    tids = [r[0] for r in db.query(Terceiro.id).filter(Terceiro.usuario_id == usuario_id).all()]
    conds = []
    if fids:
        conds.append(AtribuicaoAmbiente.funcionario_id.in_(fids))
    if tids:
        conds.append(AtribuicaoAmbiente.terceiro_id.in_(tids))
    if not conds:
        return set()
    return {r[0] for r in db.query(AtribuicaoAmbiente.projeto_nome).filter(
        AtribuicaoAmbiente.loja_id == loja_id, or_(*conds)).all()}


def _projeto_visivel_ao_ator(meta, ator, db=None):
    """Visibilidade DENTRO da loja (Regras §3/§6), via mod_escopo. Gerência+ tudo; Consultor por
    posse; operacional (PE/Medidor/Montagem) só o atribuído no Mapa; admin nada. `db` é necessário
    só para os operacionais (resolver o Mapa)."""
    if meta is None:
        return False
    if not mod_escopo.escopo_por_atribuicao(ator):
        return mod_escopo.pode_ver_projeto(ator, meta, set())     # fast path — sem consulta ao Mapa
    if db is None:
        return False                                              # conservador: operacional sem Mapa não vê
    atribuidos = _usuario_ids_atribuidos_projeto(db, getattr(meta, "nome_safe", None))
    return mod_escopo.pode_ver_projeto(ator, meta, atribuidos)


def _filtrar_projetos_por_loja(projetos, db, loja_id, ator=None):
    """Mantém só os projetos da loja (F4) e, dentro dela, o que o ator pode ver (Regras §3):
    Consultor → os que criou/legados; operacional (PE/Medidor/Montagem) → só os atribuídos no Mapa;
    demais → tudo na loja."""
    from sqlalchemy import or_
    nomes = [p.get("nome_safe") for p in projetos if p.get("nome_safe")]
    if not nomes:
        return []
    q = db.query(Projeto.nome_safe).filter(
        Projeto.nome_safe.in_(nomes), Projeto.loja_id == loja_id)
    if ator and _ve_apenas_proprios_projetos(ator.get("nivel")):
        q = q.filter(or_(Projeto.criado_por_id == ator.get("id"),
                         Projeto.criado_por_id.is_(None)))
    permitidos = {r[0] for r in q.all()}
    if ator and mod_escopo.escopo_por_atribuicao(ator):
        atrib = _projetos_atribuidos_ao_usuario(db, ator.get("id"), loja_id)
        permitidos &= atrib
    return [p for p in projetos if p.get("nome_safe") in permitidos]


def _loja_dict_para_contrato(db, loja_id):
    """Dict plano dos dados da loja para alimentar/snapshotar o contrato (F3).
    Retorna {} se não houver loja resolvível.

    PDV (loja com mãe, spec 2026-07-22): a CONTRATADA é a mãe — nome/CNPJ/endereço/
    contato vêm dela (juridicamente o cliente contrata com a matriz). Ficam do PDV o
    `codigo` (numeração rastreia a origem da venda) e as testemunhas quando o PDV as
    tem (cadastro próprio; vazias, caem nas da mãe)."""
    if not loja_id:
        return {}
    loja = db.get(Loja, loja_id)
    if not loja:
        return {}
    dona = loja   # quem "assina": a própria loja, ou a mãe quando é PDV
    if getattr(loja, "loja_mae_id", None):
        mae = db.get(Loja, loja.loja_mae_id)
        if mae is not None:
            dona = mae
    t1n = loja.testemunha1_nome or dona.testemunha1_nome
    t1c = loja.testemunha1_cpf  or dona.testemunha1_cpf
    t2n = loja.testemunha2_nome or dona.testemunha2_nome
    t2c = loja.testemunha2_cpf  or dona.testemunha2_cpf
    return {
        "id": loja.id,
        "nome": dona.nome or "", "cnpj": dona.cnpj or "", "codigo": loja.codigo or "",
        "telefone": dona.telefone or "", "email": dona.email or "",
        "cep": dona.cep or "", "logradouro": dona.logradouro or "",
        "numero": dona.numero or "", "complemento": dona.complemento or "",
        "bairro": dona.bairro or "", "cidade": dona.cidade or "", "estado": dona.estado or "",
        "testemunha1_nome": t1n or "", "testemunha1_cpf": t1c or "",
        "testemunha2_nome": t2n or "", "testemunha2_cpf": t2c or "",
    }


def _serializar_modelo_documento(m):
    """Dict raso de um DocumentoModelo para a tela (Task 9). NUNCA inclui corpo_md
    aqui — a listagem é só metadado; o corpo completo vai na resposta de importar/preview."""
    return {
        "id": m.id, "tipo": m.tipo, "versao": m.versao, "nome": m.nome,
        "origem_nome": m.origem_nome, "origem_sha256": m.origem_sha256,
        "ativo": bool(m.ativo),
        "criado_em": m.criado_em.isoformat() if m.criado_em else None,
        "criado_por_id": m.criado_por_id,
    }


def _remover_staging_seguro(caminho):
    """Apaga o arquivo de staging quando a importação não vira versão (conversão falhou
    ou o corpo saiu vazio). Sem isto, todo upload que não vira versão fica pra sempre em
    _staging/ (débito já documentado em guardar_staging).

    "Seguro" aqui é confinamento de verdade, não só engolir exceção: só apaga arquivo
    (isfile, nunca diretório) sob DOCS_LOJA_DIR. Hoje o `caminho` só vem de
    guardar_staging — gerado pelo servidor —, mas uma função com "seguro" no nome que
    não confina mente para o próximo chamador, e apagar é irreversível.
    """
    import mod_documentos as _mdoc
    if not caminho:
        return
    try:
        alvo = os.path.realpath(caminho)
        base = os.path.realpath(_mdoc.DOCS_LOJA_DIR)
        # commonpath levanta ValueError p/ drives diferentes (Windows) — caso a recusar.
        if os.path.commonpath([base, alvo]) != base:
            return
        if os.path.isfile(alvo):
            os.remove(alvo)
    except (OSError, ValueError):
        pass


# == MAIN ==
def main():
    # Postgres OBRIGATÓRIO (faxina 2026-07-23: SQLite removido por inteiro — o escape
    # ORIZON_ALLOW_SQLITE da S85 deixou de existir). Sem DATABASE_URL, explica e sai.
    import sys as _sys
    import database as _db
    if not _db.DATABASE_URL or not _db.DATABASE_URL.startswith("postgresql"):
        print("=" * 74)
        print("  DATABASE_URL ausente ou nao-Postgres. O Orizon roda SO em PostgreSQL.")
        print("  Configure e rode de novo, por exemplo:")
        print("    export DATABASE_URL='postgresql+psycopg2://orizon:SENHA@localhost/orizon'")
        print("    python3 main.py            (ou use ./run.sh)")
        print("=" * 74)
        _sys.exit(1)
    init_db()
    # FASE A (infra contábil): backfill do plano de contas nos owners existentes — planos antigos
    # ganham as contas novas de PLANO_PADRAO (Adiantamento de Clientes, Provisão Custo Fábrica etc.).
    # Idempotente + fail-soft (não aborta o start). main.py é o composition root: pode importar domínio.
    try:
        import mod_contabil as _mc
        _dbp = get_session()
        try:
            # ORDEM: formalismo ANTES do backfill — a migração recodifica as contas 5.6 para os
            # códigos formais; se o backfill rodasse antes, criaria as contas formais vazias e
            # forçaria o caminho de merge à toa. Idempotentes os dois.
            _mc.migrar_plano_formalismo(_dbp)
            _mc.backfill_plano_todos_owners(_dbp)
            # Perfis padrão em todas as lojas + padronização de títulos (Gerencial → Gerente,
            # 2026-07-22). Idempotente.
            from auth import perfil_store as _pst
            _pst.backfill_perfis_todas_lojas(_dbp)
            # Agenda Fatia 1: fases legadas ganham o val_liq_congelado (motor atual, 1x).
            _nliq = _backfill_val_liq_fases(_dbp)
            if _nliq:
                print(f"[AGENDA] backfill val_liq_congelado: {_nliq} fase(s) preenchida(s)")
            # Agenda pós-Vera (🟡3): cronogramas legados ganham as datas das subfases do PE.
            import mod_cronograma as _mcr_bf
            _nsf = _mcr_bf.backfill_subfases_pe(_dbp)
            _dbp.commit()
            if _nsf:
                print(f"[AGENDA] backfill subfases do PE: {_nsf} data(s) prevista(s) preenchida(s)")
            # E2E 🔴 (2026-08-03): repara projetos assinados com parametros_json zerado.
            _nrep = _reparar_parametros_segmentados(_dbp)
            _dbp.commit()
            if _nrep:
                print(f"[NEGOCIACAO] reparo parametros_json pós-assinatura: {_nrep} projeto(s)")
        finally:
            _dbp.close()
    except Exception as _e:
        logging.getLogger(__name__).warning("backfill plano de contas falhou: %s", _e)
    # (migrações margens->orcamento e margens->parametros removidas na faxina: a coluna
    #  Orcamento.margens foi removida; parâmetros vêm de Projeto.parametros_json e o desconto
    #  de Orcamento.desconto_pct.)
    # Porta de bind configurável via ORIZON_PORT (default 8765). Permite 2 instâncias
    # no mesmo servidor (ex.: INTEGRAÇÃO :8765 e PRÉ-HOMOLOGAÇÃO :8766).
    port   = porta_do_ambiente()
    max_body_bytes()   # valida ORIZON_MAX_BODY_MB no bootstrap: env inválido cai AQUI, não no 1º upload
    # Host de bind configurável: padrão 127.0.0.1 (dev local seguro);
    # em produção defina ORIZON_HOST=0.0.0.0 para aceitar acesso externo.
    host   = os.environ.get("ORIZON_HOST", "127.0.0.1")
    server = HTTPServer((host, port), Handler)
    eh_local = host in ("127.0.0.1", "localhost")
    print("\n  Orizon Manager")
    print("  Bind: %s:%d" % (host, port))
    if eh_local:
        url = "http://127.0.0.1:%d" % port
        print("  Acesse: %s" % url)
        # Conveniencia de dev local: abre o navegador. Em producao (ORIZON_HOST=0.0.0.0) nao abre.
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    else:
        print("  Acesse pelo IP/dominio do servidor na porta %d (bind em %s)" % (port, host))
    print("  Pressione Ctrl+C para encerrar\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.\n")


if __name__ == "__main__":
    main()
