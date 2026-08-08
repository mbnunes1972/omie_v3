"""Regressão dos achados da Vera resolvidos em 2026-08-08 (item 2, urgente pra v1 comercial):
o servidor era HTTPServer single-thread — uma emissão fiscal (chamada de rede à Focus/SEFAZ,
~segundos a ~1min) travava a loja INTEIRA: ninguém mais conseguia nem logar enquanto isso
rodava (medido pela Vera, ~60s). Virou ThreadingHTTPServer, e o estado por-requisição
(`main._req_local`, ex-global `_REQ_LOJA_ATIVA`) virou thread-local pra não vazar a loja ativa
de uma requisição pra outra rodando ao mesmo tempo numa thread diferente — isso seria um bug de
tenancy grave (usuário A veria/editaria dado da loja de B)."""
import socket
import threading
import time
from urllib.parse import urlparse

import main


def test_req_local_e_thread_local_nao_global():
    """Guarda estrutural: se alguém reverter pra uma variável global simples, este teste
    denuncia — threading.local() isola por thread por desenho; um global comum vazaria."""
    assert isinstance(main._req_local, threading.local)


def test_servidor_usa_threadinghttpserver():
    """Checagem estrutural do main(): ninguém reverte pra HTTPServer single-thread sem que a
    suíte reclame — o bug da Vera ficou invisível por meses até medir sob carga real."""
    import inspect
    src = inspect.getsource(main.main)
    assert "ThreadingHTTPServer(" in src
    assert "= HTTPServer(" not in src


def test_loja_ativa_nao_vaza_entre_threads_concorrentes():
    """O bug real que o global causava: thread A define loja 111, thread B define loja 222 ao
    MESMO tempo — com threading.local(), cada uma só enxerga a sua própria. Um threading.Barrier
    força as duas a já terem setado o próprio valor antes de qualquer uma ler, garantindo que a
    leitura aconteça com as duas "em voo" simultaneamente (não é uma corrida sortuda)."""
    barreira = threading.Barrier(2)
    resultados = {}

    def trabalhar(nome, loja_id):
        main._req_local.loja_ativa = loja_id
        barreira.wait(timeout=5)     # as duas threads já setaram o próprio valor aqui
        time.sleep(0.05)             # janela pra uma eventual corrida se manifestar
        resultados[nome] = main._req_loja_ativa()

    ta = threading.Thread(target=trabalhar, args=("A", 111))
    tb = threading.Thread(target=trabalhar, args=("B", 222))
    ta.start(); tb.start()
    ta.join(timeout=5); tb.join(timeout=5)

    assert resultados == {"A": 111, "B": 222}


def test_req_loja_ativa_helper_sem_thread_local_setado():
    """Uma thread nova (nunca passou por do_GET/POST/PUT/PATCH) não tem o atributo ainda —
    o helper devolve None, não AttributeError (mesmo comportamento do global == None default)."""
    resultado = {}

    def trabalhar():
        resultado["v"] = main._req_loja_ativa()

    t = threading.Thread(target=trabalhar)
    t.start(); t.join(timeout=5)
    assert resultado["v"] is None


def test_conexao_lenta_nao_bloqueia_conexao_rapida_concorrente(servidor):
    """Prova em nível de transporte, batendo no servidor de teste real: abre uma conexão e manda
    só METADE de uma requisição HTTP (headers sem a linha em branco final) — o handler daquela
    conexão fica bloqueado esperando o resto. Enquanto isso, uma SEGUNDA conexão, completa, deve
    ser aceita e respondida sem esperar a primeira terminar.

    Sob o HTTPServer single-thread antigo isso não acontecia: o accept-loop fica preso servindo a
    primeira conexão e nunca chega a aceitar a segunda — exatamente o mecanismo que travava a loja
    inteira durante uma emissão fiscal real (a chamada de rede à Focus segurava a única thread)."""
    u = urlparse(servidor)
    host, port = u.hostname, u.port

    lenta = socket.create_connection((host, port), timeout=5)
    try:
        # request line + 1 header, SEM a linha em branco que fecha os headers — o servidor fica
        # bloqueado em rfile.readline() esperando o resto que nunca chega.
        lenta.sendall(b"GET /login HTTP/1.1\r\nHost: x\r\n")

        inicio = time.monotonic()
        rapida = socket.create_connection((host, port), timeout=5)
        try:
            rapida.sendall(b"GET /login HTTP/1.1\r\nHost: x\r\n\r\n")
            resposta = rapida.recv(4096)
        finally:
            rapida.close()
        duracao = time.monotonic() - inicio

        assert resposta.startswith(b"HTTP/1.")
        assert duracao < 2.0, (
            "a conexão rápida esperou %.1fs — servidor voltou a serializar requisições "
            "(regressão pro HTTPServer single-thread)" % duracao)
    finally:
        lenta.close()   # libera a thread travada do lado do servidor (EOF na leitura pendente)
