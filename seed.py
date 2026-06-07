"""
seed.py — Cria os usuários iniciais no banco de dados
Omie_V3 | Dalmóbile

Uso: python3 seed.py
"""

from database import init_db, get_session, Usuario

USUARIOS = [
    {"nome": "Pedro da Mota",    "login": "pdm2026", "senha": "teste123", "nivel": "diretor"},
    {"nome": "Luiz da Silva",    "login": "lds2026", "senha": "teste234", "nivel": "gerente"},
    {"nome": "Marcia dos Santos","login": "mds2026", "senha": "teste345", "nivel": "consultor"},
]

def seed():
    init_db()
    db = get_session()
    try:
        criados   = 0
        existentes = 0
        for dados in USUARIOS:
            existe = db.query(Usuario).filter_by(login=dados["login"]).first()
            if existe:
                print(f"  [já existe] {dados['login']} ({dados['nivel']})")
                existentes += 1
                continue

            u = Usuario(nome=dados["nome"], login=dados["login"], nivel=dados["nivel"])
            u.set_senha(dados["senha"])
            db.add(u)
            criados += 1
            print(f"  [criado]    {dados['login']} ({dados['nivel']}) — {dados['nome']}")

        db.commit()
        print(f"\n  ✓ {criados} usuário(s) criado(s), {existentes} já existia(m).")
    finally:
        db.close()

if __name__ == "__main__":
    print("\nCriando usuários iniciais...\n")
    seed()
