"""
seed.py — Cria os usuários iniciais no banco de dados
Orizon Manager | Dalmóbile

Uso: python3 seed.py
"""

import os

import database
from database import init_db, get_session, Usuario, Funcao, loja_seed_id, FUNCOES_PADRAO

# Perfil-4 (rev2 §2): Perfil = nível de ACESSO (master/gerencial/operador). O cargo é a
# FUNÇÃO (semeada em Config › Funções); é atribuído pelo cadastro de Funcionário, não pelo login.
USUARIOS = [
    {"nome": "Pedro da Mota",        "login": "pdm2026", "senha": "teste123", "nivel": "master"},
    {"nome": "Luiz da Silva",        "login": "lds2026", "senha": "teste234", "nivel": "gerencial"},
    {"nome": "Marcia dos Santos",    "login": "mds2026", "senha": "teste345", "nivel": "operador"},
    {"nome": "Gabriela Adm/Fin",     "login": "gaf2026", "senha": "teste456", "nivel": "master"},
    {"nome": "Sonia Suporte",        "login": "sup2026", "senha": "teste567", "nivel": "operador"},
    {"nome": "Marcos Medidor",       "login": "med2026", "senha": "teste012", "nivel": "operador"},
]


def criar_usuarios_seed(db, usuarios, loja_id):
    """Cria os usuários que ainda não existem, vinculados à loja `loja_id`.
    Idempotente: pula logins já existentes. Retorna o nº de usuários criados."""
    criados = 0
    for dados in usuarios:
        if db.query(Usuario).filter_by(login=dados["login"]).first():
            print(f"  [ja existe] {dados['login']} ({dados['nivel']})")
            continue
        u = Usuario(nome=dados["nome"], login=dados["login"],
                    nivel=dados["nivel"], loja_id=loja_id)
        u.set_senha(dados["senha"])
        db.add(u)
        criados += 1
        print(f"  [criado]    {dados['login']} ({dados['nivel']}) - {dados['nome']}")
    db.commit()
    return criados


def criar_funcoes_seed(db, loja_id):
    """Semeia a Tabela de Funções da loja com os cargos padrão (Regras_Funcoes_Perfis §0b).
    Idempotente por (loja_id, nome): pula os que já existem. Retorna o nº de funções criadas."""
    if loja_id is None:
        return 0
    existentes = {f.nome for f in db.query(Funcao).filter_by(loja_id=loja_id).all()}
    criadas = 0
    for nome in FUNCOES_PADRAO:
        if nome in existentes:
            continue
        usa_comissao_vendas = 1 if nome == "Consultor de Vendas" else 0
        db.add(Funcao(loja_id=loja_id, nome=nome, status="ativo",
                      usa_comissao_vendas=usa_comissao_vendas))
        criadas += 1
    db.commit()
    return criadas


def seed():
    init_db()                         # cria schema + tenancy_v1 (loja seed) + tenancy_v2 (super_admin)
    db = get_session()
    try:
        if not db.query(Usuario).filter_by(nivel="super_admin").first():
            login = os.environ.get("ORIZON_ADMIN_LOGIN")
            senha = os.environ.get("ORIZON_ADMIN_SENHA")
            if not login or not senha:
                print("  [recusado] super_admin NAO criado: defina ORIZON_ADMIN_LOGIN e "
                      "ORIZON_ADMIN_SENHA no ambiente. Nada de valor default -- foi um login/"
                      "senha hardcoded aqui que virou super_admin de verdade na Integracao e "
                      "na Homologacao (achado de 28/08/2026).")
            else:
                sa = Usuario(nome=database._SEED_SA_NOME, login=login,
                             nivel="super_admin", loja_id=None, rede_id=None,
                             senha_provisoria=1)   # mesma regra do scripts/criar_primeiro_admin.py
                sa.set_senha(senha)
                db.add(sa); db.commit()
                print(f"  [criado]    {login} (super_admin, senha_provisoria=1)")

        loja_id = loja_seed_id(db)    # a loja seed já existe pela migração
        if loja_id is None:
            print("  [aviso] loja seed nao encontrada; usuarios serao criados sem loja_id.")
        criados = criar_usuarios_seed(db, USUARIOS, loja_id)
        existentes = len(USUARIOS) - criados
        funcoes = criar_funcoes_seed(db, loja_id)
        print(f"\n  OK: {criados} usuario(s) criado(s), {existentes} ja existia(m); "
              f"{funcoes} funcao(oes) semeada(s); loja seed id={loja_id}.")
    finally:
        db.close()


if __name__ == "__main__":
    print("\nCriando usuarios iniciais...\n")
    seed()
