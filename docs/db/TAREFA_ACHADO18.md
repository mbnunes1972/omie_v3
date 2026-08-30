# Passo 9 do ROTEIRO — a guarda de `valor_total > 0`

Passo pequeno, de propósito. O aceite já existe desde o passo 4.

## O que entra

Recusa explícita, com mensagem, em dois pontos:
- geração de contrato;
- emissão de NF-e / NFS-e.

Se o orçamento do projeto tiver `valor_total` nulo ou zero, a operação não
acontece.

## Por que, já que não é alcançável

Medido em 29/08: nenhum caminho conhecido chega lá. O que impede não é
validação — é a **coincidência** de que o único jeito de dar valor a um
orçamento já recalcula na mesma requisição. Coincidência de desenho não é
proteção: ela some no próximo redesenho, e ninguém é avisado.

O passo 7 já mostrou como isso escala — a seleção do orçamento no
`POST /aditivo` ficou **mais** perigosa depois que o passo 6 passou a criar
orçamentos históricos. Desenho muda; guarda escrita fica.

## Detalhe que mudou desde a medição

`_valores_segmentados_do_projeto` agora soma **contrato + aditivos
assinados** (passo 7). A guarda deve olhar o valor que de fato vai ser
faturado — o total contratado —, não só o `valor_total` do orçamento do
contrato. Um contrato zerado com aditivo positivo não deve ser recusado.

## Aceites

Os dois escritos no passo 4 saem do `xfail` neste commit. Acrescente o caso
novo acima: contrato zerado **com** aditivo assinado positivo **passa**.

## O que NÃO fazer

- Não transformar a guarda em recálculo: ela lê, não corrige.
- Não mexer no ACHADO-02/03 — passo 10.
