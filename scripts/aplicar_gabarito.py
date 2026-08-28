"""Aplica o gabarito completo (árvore de centro de custo + plano de contas + classificação do
grupo 5) a TODOS os owners existentes no banco apontado por `DATABASE_URL` — mesmo mecanismo de
`mod_contabil.aplicar_gabarito_completo`, o 3º ponto de entrada (docs/db/TAREFA_CENTRO_CUSTO_2.md
item 6): migration (`46a93cfd591b`) cobre banco já povoado; criação de loja (main.py) cobre a
loja nova; este script cobre o banco RECÉM-RESTAURADO.

Por quê precisa existir: a migration deriva owners de `redes`/`lojas`, mas roda como parte de
`alembic upgrade head` — passo 1 (Estrutura) da reconstrução de ambiente, ANTES do passo 2
(Configuração, o dump com redes/lojas de verdade). Num ambiente novo, a migration roda contra
`redes`/`lojas` ainda vazias e não semeia nada. Este script roda DEPOIS do dump — passo 3, ver
docs/db/RESTAURAR.md — quando redes/lojas já existem.

Idempotente (mesma função, mesma regra: só cria o que falta, só classifica o que ainda está
NULL) — rodar de novo não duplica nem sobrescreve reclassificação manual.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Rede, Loja
import mod_contabil


def main():
    db = get_session()
    try:
        owners = [("rede", r.id) for r in db.query(Rede).all()] + \
                 [("loja", l.id) for l in db.query(Loja).all()]

        if not owners:
            print("Nenhum owner em redes/lojas — nada a fazer (rode depois de restaurar a "
                  "configuração; ver docs/db/RESTAURAR.md).")
            return

        centro_custo_criado = conta_criada = centro_custo_setado = natureza_setado = 0
        for owner_tipo, owner_id in owners:
            out = mod_contabil.aplicar_gabarito_completo(db, owner_tipo, owner_id)
            centro_custo_criado += out["centro_custo_criado"]
            conta_criada += out["conta_criada"]
            centro_custo_setado += out["centro_custo_setado"]
            natureza_setado += out["natureza_setado"]
            print("%-4s %6d: %2d no(s) de centro_custo criado(s), %3d conta(s) criada(s), "
                  "%2d centro_custo_id setado(s), %2d natureza_custo setado(s)" %
                  (owner_tipo, owner_id, out["centro_custo_criado"], out["conta_criada"],
                   out["centro_custo_setado"], out["natureza_setado"]))

        criadas = centro_custo_criado + conta_criada
        atualizadas = centro_custo_setado + natureza_setado
        print("-" * 88)
        print("Gabarito aplicado a %d owner(s) (%d rede(s), %d loja(s))." %
              (len(owners), sum(1 for ot, _ in owners if ot == "rede"),
               sum(1 for ot, _ in owners if ot == "loja")))
        print("Linhas criadas: %d (%d centro_custo, %d conta) — linhas atualizadas: %d "
              "(%d centro_custo_id, %d natureza_custo)." %
              (criadas, centro_custo_criado, conta_criada, atualizadas,
               centro_custo_setado, natureza_setado))
    finally:
        db.close()


if __name__ == "__main__":
    main()
