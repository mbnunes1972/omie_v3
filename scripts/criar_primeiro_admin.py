"""Cria o PRIMEIRO super_admin de um ambiente com `usuarios` vazia — Produção reconstruída do
zero (decisão de Marcelo, 2026-08-28): login/senha configuráveis, `senha_provisoria=1` para o
app obrigar a troca no primeiro login.

NÃO é script de criação de usuário — é de PRIMEIRO ACESSO. Por isso se recusa a rodar se
`usuarios` já tiver qualquer linha (ver `_conferir_base_vazia`): criar mais um super_admin, ou
qualquer outro usuário, é a tela de administração (ou `seed.py`, que semeia contas de
DESENVOLVIMENTO — inclusive o super_admin, também via `ORIZON_ADMIN_LOGIN`/`_SENHA` desde
28/08/2026, mesma regra de senha provisória, mas sem a guarda de base vazia — não serve pra
Produção reconstruída, que é este script).

Só existia `seed.py` como caminho parecido antes deste script — não servia pra este caso (e
tinha o próprio problema: login/senha "sad2026"/"trocar123" hardcoded em `database.py`, sem
`senha_provisoria`, acabaram como super_admin de verdade na Integração/Homologação via dump —
corrigido em 28/08/2026, mas o script continua sem a guarda de base vazia que Produção precisa).
Este script cobre o caso que faltava — dado configurável, guarda de primeiro-acesso, senha
provisória — sem duplicar a lógica de hash: usa `Usuario.set_senha()` (`database.py`,
`_hash_senha` — "Fonte única de hashing"), nunca hash escrito à mão.

Login, nome e senha vêm por argumento OU variável de ambiente (nunca hardcoded no script nem
commitados): --login/ORIZON_ADMIN_LOGIN, --nome/ORIZON_ADMIN_NOME (opcional), --senha/
ORIZON_ADMIN_SENHA. Prefira a variável de ambiente pra senha — argumento de linha de comando
fica visível em `ps`/histórico do shell.

Uso:
    ORIZON_ADMIN_SENHA='...' DATABASE_URL='postgresql+psycopg2://...' \\
        python3 scripts/criar_primeiro_admin.py --login mbn1972@gmail.com --nome "Marcelo"
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Usuario


def _conferir_base_vazia(db):
    n = db.query(Usuario).count()
    if n:
        print(f"RECUSADO: 'usuarios' já tem {n} linha(s). Este é script de PRIMEIRO ACESSO, "
              "não de criação de usuário — rodar contra uma base já povoada duplicaria (ou "
              "confundiria) o caminho de administração normal (tela de admin, ou seed.py em "
              "desenvolvimento). Se o objetivo é outro super_admin, use a tela.",
              file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--login", default=os.environ.get("ORIZON_ADMIN_LOGIN"),
                     help="login (aceita e-mail) — ou ORIZON_ADMIN_LOGIN")
    ap.add_argument("--nome", default=os.environ.get("ORIZON_ADMIN_NOME", "Administrador"),
                     help="nome — ou ORIZON_ADMIN_NOME (default: Administrador)")
    ap.add_argument("--senha", default=os.environ.get("ORIZON_ADMIN_SENHA"),
                     help="senha inicial — ou ORIZON_ADMIN_SENHA (recomendado; evita expor "
                          "a senha em `ps`/histórico do shell)")
    args = ap.parse_args()

    if not args.login or not args.login.strip():
        print("RECUSADO: login vazio (--login ou ORIZON_ADMIN_LOGIN).", file=sys.stderr)
        sys.exit(1)
    if not args.senha or len(args.senha) < 6:
        print("RECUSADO: senha ausente ou com menos de 6 caracteres (--senha ou "
              "ORIZON_ADMIN_SENHA).", file=sys.stderr)
        sys.exit(1)

    db = get_session()
    try:
        _conferir_base_vazia(db)

        admin = Usuario(nome=args.nome.strip(), login=args.login.strip(),
                         email=args.login.strip(), nivel="super_admin",
                         loja_id=None, rede_id=None, senha_provisoria=1)
        admin.set_senha(args.senha)
        db.add(admin)
        db.commit()

        print(f"Criado: {admin.nome!r}, login={admin.login!r}, nivel=super_admin, "
              f"senha_provisoria=1 (id={admin.id}). Senha NÃO impressa.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
