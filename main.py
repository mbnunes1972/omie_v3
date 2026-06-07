"""
main.py — Servidor HTTP, rotas e inicialização.
Ponto de entrada da aplicação: python main.py
"""
import os, io, json, time, re, threading, webbrowser
import sys
import email
from email import policy as _email_policy
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from auth_routes import handle_auth_get, handle_auth_post, get_usuario_sessao
from database import init_db
from urllib.parse import urlparse

from storage import (
    _BASE_DIR, PROJETOS_DIR, CPF_CORINGA,
    PERFIS_PADRAO, PERFIS_FILE,
    storage_ler_json, storage_salvar_json, storage_salvar_binario,
    storage_salvar_texto, storage_ler_texto, storage_ler_binario,
    storage_existe, storage_listar, storage_deletar,
    config_carregar, config_salvar,
    perfis_carregar, perfis_salvar,
    session_get, session_set, session_reset_exportacao,
    _set_credenciais, _sleep_interval, _omie_key,
    get_omie_key, get_omie_secret,
    so_digitos, normalizar
)
from mod_omie import (
    omie_post, buscar_cliente_cpf, pesquisar_clientes, criar_cliente,
    garantir_conta_corrente, buscar_categoria, criar_pedido,
    garantir_grupos_omie, exportar_ambientes, gerar_excel,
    _listar_projetos, _buscar_projetos, _carregar_projeto, _salvar_projeto,
    _criar_projeto, _adicionar_ambientes, _arquivar_xmls,
    _buscar_projetos_omie, _projeto_path, carregar_xmls,
    bloquear_projeto, verificar_integridade_xmls
)
from mod_margens import calcular_margens, _normalizar_faixas
from mod_fin import calcular_aymore, calcular_cartao, calcular_venda_programada, calcular_total_flex

# HTML servido como arquivo estático
_STATIC_DIR = os.path.join(_BASE_DIR, "static")

def _serve_html():
    path = os.path.join(_STATIC_DIR, "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()

# == HANDLERS HTTP ==
# == HANDLERS HTTP ==
# -- Multipart -----------------------------------------------------------------
def _parse_multipart(body, ct):
    raw = b"Content-Type: " + ct.encode() + b"\r\n\r\n" + body
    msg = email.message_from_bytes(raw, policy=_email_policy.compat32)
    arquivos, campos = [], {}
    for part in msg.walk():
        cd = part.get("Content-Disposition", "")
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

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if handle_auth_get(self, path): return
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
            self.end_headers()
            self.wfile.write(body)

        elif path == "/config":
            self.send_json(config_carregar())

        elif path == "/perfis":
            self.send_json(perfis_carregar())

        elif path == "/perfis/ativo":
            dados = perfis_carregar()
            nome  = dados.get("perfil_ativo", "consultor")
            cfg   = dados["perfis"].get(nome, PERFIS_PADRAO["perfis"]["consultor"])
            self.send_json({"perfil_ativo": nome, "config": cfg})

        elif path == "/logs":
            logs_limpos = [l for l in (session_get("logs") or []) if l["msg"] != "__DONE__"]
            done = not session_get("running") and len(logs_limpos) > 0
            self.send_json({
                "logs":         logs_limpos,
                "done":         done,
                "confirm":      session_get("confirm_pending"),
                "pedidos":      session_get("pedidos", []),
                "pode_aprovar": session_get("idx_negociacao") is not None,
                "nome_cliente": session_get("nome_cliente", ""),
            })

        elif path == "/pagamentos":
            # Lista modalidades do mod_fin.py para popular o dropdown
            try:
                import mod_fin as _mf
                mods = _mf.listar_modalidades()
            except Exception:
                mods = [{"codigo": "a_vista", "descricao": "A Vista"}]
            self.send_json({"ok": True, "modalidades": mods})

        elif path == "/projetos":
            self.send_json({"ok": True, "projetos": _listar_projetos()})

        elif path == "/projetos/buscar":
            from urllib.parse import parse_qs
            q = (parse_qs(urlparse(self.path).query).get('q') or [''])[0].strip()
            locais = _buscar_projetos(q)
            # Marca origem
            for p in locais: p['origem'] = 'local'
            # Busca no Omie (assíncrono seria ideal; aqui faz sync com timeout curto)
            omie_res = _buscar_projetos_omie(q)
            # Evita duplicatas: se projeto local tem mesmo nome, não adiciona do Omie
            nomes_locais = {p['nome_projeto'].lower() for p in locais}
            omie_unicos = [p for p in omie_res if p['nome_projeto'].lower() not in nomes_locais]
            self.send_json({'ok': True, 'projetos': locais + omie_unicos})

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

            m = _re.match(r"^/projetos/([^/]+)$", path)
            if m:
                nome_safe = m.group(1)
                proj = _carregar_projeto(nome_safe)
                if proj:
                    session_set("projeto_ativo", nome_safe)
                    self.send_json({"ok": True, "projeto": proj})
                else:
                    self.send_json({"ok": False, "erro": "Projeto nao encontrado"}, code=404)
            else:
                self.send_response(404)
                self.end_headers()

    def do_POST(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        if handle_auth_post(self, path, body): return
        if path == "/config":
            config_salvar(json.loads(body))
            self.send_json({"ok": True})

        elif path == "/perfis":
            dados = json.loads(body)
            perfis_salvar(dados)
            self.send_json({"ok": True})

        elif path == "/perfis/ativo":
            dados = json.loads(body)
            cfg   = perfis_carregar()
            cfg["perfil_ativo"] = dados.get("perfil", "consultor")
            perfis_salvar(cfg)
            self.send_json({"ok": True, "perfil_ativo": cfg["perfil_ativo"]})

        elif path == "/cancel":
            session_set("cancel", True)
            session_set("running", False)
            self.send_json({"ok": True})

        elif path == "/confirm":
            data = json.loads(body)
            session_set("confirm_result", data["resp"])
            session_set("confirm_pending", None)
            if session_get("confirm_event"):
                session_get("confirm_event").set()
            self.send_json({"ok": True})

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

        elif path == "/exportar":
            req        = json.loads(body)
            cfg_salvo  = config_carregar()
            app_key    = req.get("app_key", "")    or cfg_salvo.get("app_key", "")
            app_secret = req.get("app_secret", "") or cfg_salvo.get("app_secret", "")
            intervalo  = float(req.get("intervalo") or cfg_salvo.get("intervalo", 0.5))
            ambientes_sel = req.get("ambientes", "todos")
            dados = session_get("dados_carregados")
            nome_safe_para_bloquear = None
            if not dados:
                # Fluxo v3: usa o projeto ativo carregado na sessão
                nome_safe = session_get("projeto_ativo")
                if not nome_safe:
                    self.send_json({"ok": False, "erro": "Nenhum projeto ativo. Abra um projeto primeiro."})
                    return
                proj = _carregar_projeto(nome_safe)
                if not proj:
                    self.send_json({"ok": False, "erro": "Projeto nao encontrado."})
                    return
                if proj.get("bloqueado"):
                    self.send_json({"ok": False, "erro": "Projeto ja aprovado e bloqueado em %s." % proj.get("bloqueado_em", "—")})
                    return
                ambs_selecionados = [a for a in proj.get("ambientes", []) if a.get("selecionado", True)]
                if not ambs_selecionados:
                    self.send_json({"ok": False, "erro": "Nenhum ambiente selecionado no projeto."})
                    return
                dados = {
                    "ok":            True,
                    "cliente":       proj.get("cliente", {}),
                    "ambientes":     ambs_selecionados,
                    "grupos_ref":    {},
                }
                ambientes_sel = "todos"
                nome_safe_para_bloquear = nome_safe
            session_set("running", True)
            session_set("logs", [])
            session_set("pedidos", [])
            session_set("confirm_pending", None)
            session_set("confirm_result", None)
            session_set("confirm_event", None)
            session_set("cancel", False)
            session_set("idx_negociacao", None)

            def log_cb(msg, tipo="info"):
                if msg == "__DONE__":
                    session_set("running", False)
                    return
                session_get("logs").append({"msg": msg, "tipo": tipo})

            def confirm_cb(tipo, dados_modal):
                evt = threading.Event()
                session_set("confirm_event", evt)
                if tipo == "sem_cpf":
                    session_set("confirm_pending", {
                        "tipo": "sem_cpf", "titulo": "CPF nao informado",
                        "corpo": "O cliente <span class='highlight'>%s</span> nao tem CPF no XML." % dados_modal["nome"],
                    })
                elif tipo == "nome_diferente":
                    session_set("confirm_pending", {
                        "tipo": "nome_diferente", "titulo": "Nome diferente",
                        "corpo": "XML: <span class='highlight'>%s</span><br>Omie: <span class='highlight'>%s</span>" % (dados_modal["nome_xml"], dados_modal["nome_omie"]),
                    })
                elif tipo == "sem_uf":
                    session_set("confirm_pending", {
                        "tipo": "sem_uf", "titulo": "Estado (UF) nao informado",
                        "corpo": "O cliente <span class='highlight'>%s</span> nao tem UF no cadastro." % dados_modal["nome"],
                    })
                evt.wait(timeout=120)
                return session_get("confirm_result", "")

            def run():
                try:
                    pedidos = exportar_ambientes(
                        app_key, app_secret, dados, ambientes_sel,
                        log_cb, confirm_cb, intervalo=intervalo,
                    )
                    session_set("pedidos", pedidos)
                    if nome_safe_para_bloquear:
                        try:
                            bloquear_projeto(nome_safe_para_bloquear)
                            log_cb("Projeto bloqueado — XMLs travados com hash SHA-256.", "ok")
                            session_set("projeto_bloqueado", True)
                        except Exception as e_lock:
                            log_cb("Aviso: nao foi possivel bloquear o projeto: %s" % e_lock, "warn")
                except Exception as e:
                    log_cb("ERRO: %s" % e, "err")
                finally:
                    session_set("running", False)

            _set_credenciais(app_key, app_secret)
            threading.Thread(target=run, daemon=True).start()
            self.send_json({"ok": True})

        elif path == "/buscar_cliente":
            req   = json.loads(body)
            query = req.get("query", "").strip()
            if not query:
                self.send_json({"ok": False, "erro": "Informe nome ou CPF para buscar"})
                return
            cfg = config_carregar()
            _set_credenciais(cfg.get("app_key", ""), cfg.get("app_secret", ""))
            try:
                clientes  = pesquisar_clientes(query)
                resultado = [
                    {"codigo": c.get("codigo_cliente_omie"), "nome": c.get("razao_social", ""),
                     "cpf": c.get("cnpj_cpf", ""), "cidade": c.get("cidade", ""),
                     "uf": c.get("estado", ""), "email": c.get("email", "")}
                    for c in clientes
                ]
                self.send_json({"ok": True, "clientes": resultado})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})

        elif path == "/vincular_cliente":
            req = json.loads(body)
            session_set("cliente_selecionado", {
                "codigo": req["codigo"], "nome": req["nome"],
                "cpf": req.get("cpf", ""), "uf": req.get("uf", ""),
            })
            self.send_json({"ok": True})

        elif path == "/limpar_cliente":
            session_set("cliente_selecionado", None)
            self.send_json({"ok": True})

        # == ROTAS DE NEGOCIAÇÃO ==
        # Stateless: recebem todos os dados no payload e devolvem resultado.
        # Pronto para nuvem sem alteração de assinatura.
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
            perfis = perfis_carregar()
            senha_correta = perfis.get("perfis", {}).get("gerente", {}).get("senha_gerente", "1234")
            if senha == senha_correta:
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

        elif path == "/calcular_margens":
            req = json.loads(body)
            fin_pct = req.get("custo_financeiro_pct", 0)
            bruto   = req.get("valor_bruto", 0)
            desc    = req.get("desconto_pct", 0)
            print("[CALC] bruto=%.2f desc=%.2f fin_pct=%.4f" % (bruto, desc, fin_pct))
            resultado = calcular_margens(
                valor_bruto              = bruto,
                desconto_pct             = desc,
                fora_da_sede             = req.get("fora_da_sede", False),
                custo_viagem             = req.get("custo_viagem", 0),
                comissao_arq_pct         = req.get("comissao_arq_pct", 0),
                comissao_arq_ativa       = req.get("comissao_arq_ativa", False),
                fidelidade_pct           = req.get("fidelidade_pct", 0),
                fidelidade_ativa         = req.get("fidelidade_ativa", False),
                custo_financeiro_pct     = fin_pct,
                brinde                   = req.get("brinde", 0),
                brinde_ativo             = req.get("brinde_ativo", False),
            )
            print("[CALC] saldo_desc=%.2f saldo_fin=%.2f acrescimo=%.2f final=%.2f" % (
                resultado["saldo_apos_desconto"], resultado["saldo_apos_financeiro"],
                resultado["acrescimo_financeiro"], resultado["valor_final"]))
            self.send_json({"ok": True, "resultado": resultado})

        elif path == "/projetos/novo":
            req = json.loads(body)
            nome_proj    = req.get('nome_projeto', '').strip()
            cli_nome     = req.get('cliente', {}).get('nome', '').strip()
            cli_cpf      = req.get('cliente', {}).get('cpf', '').strip()
            cli_email    = req.get('cliente', {}).get('email', '').strip()
            cli_telefone = req.get('cliente', {}).get('telefone', '').strip()
            if not nome_proj or not cli_nome:
                self.send_json({'ok': False, 'erro': 'nome_projeto e cliente.nome são obrigatórios'})
                return
            try:
                proj = _criar_projeto(nome_proj, cli_nome, cli_cpf, cli_email, cli_telefone)

                # Garante credenciais carregadas (main() já carrega, mas reforça)
                if not get_omie_key():
                    cfg = config_carregar()
                    if cfg.get('app_key'):
                        _set_credenciais(cfg['app_key'], cfg['app_secret'])

                # Diagnóstico sempre visível no terminal
                print("[OMIE] Tentando criar projeto: %r" % nome_proj)
                print("[OMIE] app_key: %s" % (get_omie_key()[:8] + "..." if get_omie_key() else "VAZIA"))

                # Tenta criar no Omie
                if get_omie_key():
                    try:
                        cod_int = (re.sub(r"[^A-Z0-9]", "", normalizar(nome_proj))[:9]
                                   + datetime.now().strftime("%y%m%d%H%M"))[:20]
                        r_omie = omie_post(
                            "/geral/projetos/", "IncluirProjeto",
                            {"nome": nome_proj, "inativo": "N", "codInt": cod_int},
                            lambda *_: None, no_rotate=True, timeout=10
                        )
                        print("[OMIE] Resposta bruta: %s" % r_omie)
                        cod = (r_omie.get("codigo") or r_omie.get("nCodProj")
                               or r_omie.get("nCod") or r_omie.get("codigo_projeto"))
                        proj["codigo_projeto_omie"] = cod
                        print("[OMIE] Projeto criado — codigo_projeto_omie: %s" % cod)
                    except Exception as e_omie:
                        proj["codigo_projeto_omie"] = None
                        proj["codigo_projeto_omie_erro"] = str(e_omie)
                        print("[OMIE] ERRO ao criar projeto: %s" % e_omie)
                    _salvar_projeto(proj)
                else:
                    print("[OMIE] Credenciais não configuradas — projeto criado apenas localmente.")

                session_set('projeto_ativo', proj['nome_safe'])
                self.send_json({'ok': True, 'projeto': proj})
            except Exception as e:
                self.send_json({'ok': False, 'erro': str(e)})

        else:
            import re as _re
            # Rota: POST /projetos/<nome_safe>/margens
            m_mar = _re.match(r"^/projetos/([^/]+)/margens$", path)
            if m_mar:
                nome_safe = m_mar.group(1)
                req  = json.loads(body)
                proj = _carregar_projeto(nome_safe)
                if not proj:
                    self.send_json({"ok": False, "erro": "Projeto não encontrado"})
                    return
                if proj.get("bloqueado"):
                    self.send_json({"ok": False, "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."})
                    return
                # Merge: preserva campos existentes e atualiza os enviados
                m_atual = proj.get("margens") or {}
                m_atual.update({
                    "desconto_pct":          float(req.get("desconto_pct",          m_atual.get("desconto_pct", 0))),
                    "custo_financeiro_pct":  float(req.get("custo_financeiro_pct",  m_atual.get("custo_financeiro_pct", 0))),
                    "fora_da_sede":          bool( req.get("fora_da_sede",           m_atual.get("fora_da_sede", False))),
                    "custo_viagem":       float(req.get("custo_viagem",        m_atual.get("custo_viagem", 0))),
                    "brinde":             float(req.get("brinde",              m_atual.get("brinde", 0))),
                    "brinde_ativo":       bool( req.get("brinde_ativo",        m_atual.get("brinde_ativo", False))),
                    "comissao_arq_pct":   float(req.get("comissao_arq_pct",   m_atual.get("comissao_arq_pct", 0))),
                    "comissao_arq_ativa": bool( req.get("comissao_arq_ativa",  m_atual.get("comissao_arq_ativa", False))),
                    "fidelidade_pct":     float(req.get("fidelidade_pct",     m_atual.get("fidelidade_pct", 0))),
                    "fidelidade_ativa":   bool( req.get("fidelidade_ativa",    m_atual.get("fidelidade_ativa", False))),
                })
                proj["margens"] = m_atual
                _salvar_projeto(proj)
                self.send_json({"ok": True, "margens": proj["margens"]})
                return

            m = _re.match(r"^/projetos/([^/]+)/ambientes/(adicionar|remover|atualizar|selecao)$", path)
            if m:
                nome_safe = m.group(1)
                acao = m.group(2)

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

            else:
                self.send_response(404)
                self.end_headers()


# == MAIN ==
def main():
    # Carrega credenciais do omie_config.json automaticamente
    cfg = config_carregar()
    if cfg.get("app_key") and cfg.get("app_secret"):
        _set_credenciais(cfg["app_key"], cfg["app_secret"])
        print("  Credenciais Omie carregadas automaticamente.")
    else:
        print("  Aviso: omie_config.json sem credenciais. Configure na sidebar.")

    init_db()
    port   = 8765
    server = HTTPServer(("127.0.0.1", port), Handler)
    url    = "http://127.0.0.1:%d" % port
    print("\n  Promob -> Omie  |  Negociacao de Margens  v7.3")
    print("  Acesse: %s" % url)
    print("  Pressione Ctrl+C para encerrar\n")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor encerrado.\n")


if __name__ == "__main__":
    main()
