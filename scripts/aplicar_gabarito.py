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

Depois de aplicar o gabarito, varre e remove `conta`/`centro_custo` órfã — cujo owner NÃO
está (mais) em `redes`/`lojas` (docs/db/TAREFA_CENTRO_CUSTO_2.md item 7). `c1ab3f8007c4` grava
gabarito incondicional pra rede,1/loja,1/loja,3; num ambiente que não tenha algum desses 3
owners de verdade (ex.: Integração, só tem loja,1), sobram linhas órfãs sem FK que as detecte —
este é o ponto do procedimento em que a verdade sobre os owners já está no banco (depois do
passo 2, a restauração da configuração). Só remove o que não tem lançamento nem outra linha
apontando pra ele; o resto fica retido e reportado (ver `mod_contabil.varrer_orfaos_gabarito`).

Semear e varrer são DUAS ETAPAS, NUNCA uma condicionada à outra — bug real de Produção
(28/08/2026): um `return` cedo quando `redes`/`lojas` vinham vazias ("nada a fazer") pulava a
varredura junto. É exatamente o caso em que ela mais importa: banco sem owner nenhum tem TODO
o gabarito da `c1ab3f8007c4` (480 `conta`/48 `centro_custo`, os 3 owners fixos) órfão, e ficava
assim pra sempre. A varredura roda sempre, mesmo quando não há owner nenhum pra semear.
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

        # Semear e varrer são DUAS ETAPAS — nunca uma condicionada à outra (bug real de
        # produção, 28/08/2026: um `return` cedo aqui, quando `owners` vinha vazio, pulava a
        # varredura inteira — exatamente o caso em que ela mais importa: banco sem owner
        # nenhum tem TODO o gabarito da c1ab3f8007c4 (480 conta/48 centro_custo, os 3 owners
        # fixos) órfão, e ficava assim pra sempre).
        if not owners:
            print("Nenhum owner em redes/lojas — nada a semear (rode depois de restaurar a "
                  "configuração; ver docs/db/RESTAURAR.md). Varredura de órfãos roda mesmo "
                  "assim, abaixo.")
        else:
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

        print()
        print("Varredura de órfãos (owner sem correspondente em redes/lojas):")
        orf = mod_contabil.varrer_orfaos_gabarito(db)
        for r in orf["retidos_conta"]:
            print("  RETIDA conta %s,%s %s (id=%d): %s" %
                  (r["owner_tipo"], r["owner_id"], r["codigo"], r["id"], r["motivo"]))
        for r in orf["retidos_centro_custo"]:
            print("  RETIDO centro_custo %s,%s %s (id=%d): %s" %
                  (r["owner_tipo"], r["owner_id"], r["nome"], r["id"], r["motivo"]))
        print("-" * 88)
        print("Órfãos encontrados: %d conta, %d centro_custo." %
              (orf["encontrados_conta"], orf["encontrados_centro_custo"]))
        print("Removidos: %d conta, %d centro_custo." %
              (orf["removidos_conta"], orf["removidos_centro_custo"]))
        print("Retidos (reportados acima): %d conta, %d centro_custo." %
              (len(orf["retidos_conta"]), len(orf["retidos_centro_custo"])))
    finally:
        db.close()


if __name__ == "__main__":
    main()
