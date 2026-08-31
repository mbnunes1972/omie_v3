# Passo 11 do ROTEIRO — a segmentação não congelada trava a AF1

Último passo da Fase 1. **Teste primeiro**, como todos os outros — e aqui
isso importa mais que de costume: o ACHADO-23 nasceu de uma medição, nunca
teve teste, e por isso o contador de xfails não o enxerga. Foi o único
achado da Fase 1 que quase passou despercebido no fechamento.

## O defeito

`_congelar_segmentacao_no_projeto` grava a segmentação efetiva no projeto na
2ª assinatura. O mecanismo funciona. O chamador engole as duas falhas:

```python
try:
    if _congelar_segmentacao_no_projeto(db, loja_id, nome_safe) is not None:
        db.commit()
except Exception as _eseg:
    db.rollback()
    print("[SEGMENTACAO] congelar na assinatura falhou:", _eseg)
```

Retorno `None` não commita e não reclama; exceção vira um `print`. Nos dois
casos a assinatura completa e o projeto passa a viver do default da loja ao
vivo, para sempre. Medido: **R$ 40.000 de diferença na face fiscal** de um
contrato de R$ 88.888,89, sem ninguém tocar no projeto.

## O conserto, decidido em 30/08

A assinatura **completa normalmente** — não se trava a venda com o cliente na
frente. A conferência vira condição da **Aprovação Financeira (AF1)**: sem
segmentação congelada, a AF1 não aprova.

A AF1 já existe, já é obrigatória (`mod_ciclo.exige_aprovacao_financeira`) e
nasce na mesma assinatura. Quem senta nela é o perfil que consegue resolver —
e a segmentação Mercadoria × Serviço é um dos números que ele revisa de
qualquer jeito. Ela estava sendo congelada num lugar onde ninguém olhava.

Três coisas no mesmo conserto:

1. A pendência diz **o que** falhou, com o projeto identificado. Quem lê é
   quem vai resolver, não o vendedor.
2. A AF1 consegue **disparar o congelamento** ali mesmo — não só recusar.
   Sem isso a trava não tem saída e a venda fica presa sem dono.
3. O `print` vira log de erro de verdade. Hoje ninguém fica sabendo, nem
   depois.

## Aceites

Escreva **antes** do conserto:

1. **Congelamento falhou → AF1 recusa**, com a razão nomeada. Hoje aprova →
   `xfail(strict=True)` citando ACHADO-23.
2. **A AF1 congela e passa a aprovar** — o caminho de reparo funciona.
3. **Congelamento normal → AF1 aprova sem ruído.** Controle positivo: sem
   ele, uma AF1 que recusasse sempre passaria nos outros dois.
4. **A assinatura completa nos dois casos.** É o que separa esta decisão da
   alternativa que foi descartada.

Force a falha por injeção, não esperando encontrá-la — e verifique que o
teste falha pelo motivo certo, não por erro de setup, como no passo 4.

## Depois deste passo

A Fase 1 fecha de verdade. O marco tem **duas** travas, não uma:

- `pytest -q` e nenhum xfail citando achado da Fase 1;
- `docs/db/ACEITE.md` sem nenhuma linha da Fase 1 em "SEM PROVA".

A primeira sozinha não bastou — foi ela que quase deu a Fase 1 por fechada
com o ACHADO-23 aberto.

Depois disso vem a implantação das migrations acumuladas
(`e031f6ad9c80`, `f47f22de46a7`) nos três servidores, com `confirmar.sh` em
cada um.
