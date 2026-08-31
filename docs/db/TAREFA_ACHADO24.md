# F2-1 — aditivo (e contrato?) com plano de pagamento vazio

Passo pequeno. **Medir primeiro**, e a medição tem uma pergunta a mais do
que o achado registrou.

## O achado

`_materializar_recebiveis_venda_seguro` é chamada com uma `forma_pagamento`
que não produz recebível nenhum — `{"tipo": "avista", "total_cliente": 0}`
sem `parcelas` nem `entrada_valor`. `mod_recebiveis.materializar` nunca lê
`total_cliente`, devolve zero linhas, e a venda fica sem cobrança. O código
já prevê o caso e responde com um `logging.warning` (main.py:842-846).

## A pergunta a mais

**A função é compartilhada.** O aditivo é o chamador novo (passo 6-c), mas o
antigo é a geração do contrato (main.py:13865) — e o `warning` está dentro
da função, não no chamador. Então a exposição pode não ser só do aditivo.

Meça os **dois** caminhos:

1. **Aditivo:** a tela de assinatura exige parcelas, ou aceita plano vazio
   como o fixture do teste de ciclo?
2. **Contrato:** a geração aceita um `pagamento_json` que materializa zero
   recebíveis? Se aceitar, o ACHADO-24 é maior do que foi registrado — um
   contrato inteiro pode ficar sem cobrança, não só um aditivo.

Se a tela impedir, diga **o que** impede: validação explícita ou campo
obrigatório de formulário. A diferença é a de sempre — formulário muda com
um redesenho, validação não.

## O conserto

Valor > 0 tem que materializar ao menos um `Recebivel`, ou a operação é
recusada com mensagem. O `logging.warning` vira recusa, nos dois chamadores
se a medição mostrar que os dois estão expostos.

**Cuidado com o caso legítimo:** valor zero não é afetado — a guarda é sobre
valor > 0 sem cobrança, não sobre cobrança ausente em geral. Se existir
algum caso real de venda com valor e sem recebível (cortesia, permuta,
algo que a loja faça), **pare e reporte** em vez de bloquear: seria decisão
do Marcelo, não sua.

## Aceites

Antes do conserto, `xfail(strict=True)` citando ACHADO-24:

1. Aditivo assinado com plano vazio é **recusado**.
2. Contrato gerado com plano vazio é **recusado** — só se a medição mostrar
   que hoje é aceito.
3. Controle positivo: plano normal materializa recebíveis e passa, sem
   ruído. Sem ele, uma guarda que recusasse sempre passaria nos dois
   primeiros.

E conserte o fixture do ciclo (`test_dre_ciclo_completo_e2e`) para mandar um
plano real no aditivo — hoje ele descreve um plano vazio, e é de lá que o
achado saiu. O resíduo de R$ 5.000 em 1.1.02 deve desaparecer; se não
desaparecer, isso é achado novo.

## Depois

Anote em `docs/db/PLANO_AJUSTES.md`, Grupo 5, uma varredura por
`logging.warning`/`print` em caminho de dinheiro. Este é o quarto lugar onde
alguém previu a falha e escolheu seguir com um aviso — os outros três são o
ACHADO-19 (seis rotas), o ACHADO-23 (congelamento da segmentação) e o
ACHADO-18. Cada aviso desses é um lugar onde alguém viu o problema e não
teve tempo.
