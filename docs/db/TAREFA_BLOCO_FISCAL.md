# Bloco fiscal — os cinco ajustes da etapa 15

Levantado pelo Marcelo em 31/08 e 01/09, percorrendo a Homologação. Todos
nasceram do mesmo percurso e se tocam; por isso vão juntos.

**Não é ciclo de estabilização — é o bloco seguinte.** O beta3 sobe sem
isto, com a etapa 15 registrada como não testada.

---

## 1 · Apagar e substituir documento de fase (ACHADO-30) · FEITO 03/09

**Era o que estava travando.** DECIDIDO: remover é MARCAR, não apagar (`removido_em`/
`removido_por_id`); detalhes do conserto no ACHADO-30 em `ACHADOS_CONTABEIS.md`.
Os itens 2 a 5 seguem abertos.

*O diagnóstico original, preservado:* não há lixeira nem botão de sobrescrever;
as tentativas se acumulam na tela e não há como remover a errada.

- **Enquanto a fase está aberta:** apagar e substituir livremente, vários
  arquivos permitidos.
- **Depois de a fase fechar:** imutável.

Vale para os arquivos de **medição** e para o **XML da NF-e da fábrica**, e
deve ser o padrão de `CicloDocumento`. É a regra 3 do plano — *o que já
virou fato se lê de onde foi congelado* — estendida de lançamento para
documento.

## 2 · Validar o XML no upload, não na emissão (ACHADO-31)

Hoje o upload aceita qualquer arquivo e quem rejeita é
`mod_nfe.preview`, dois passos depois, sem dizer que o problema é o arquivo.
**Parsear no upload e recusar ali.**

Medição já feita: as NF-e reais da fábrica
(`tests/fixtures/nfe/NFe-1632*.xml`) parseiam sem erro — 12 itens, com NCM,
CFOP, unidade. O parser está bom; falta a validação estar no lugar certo.

## 3 · Mostrar o detalhamento do erro do Focus

`FocusError` **guarda** a lista de erros da SEFAZ em `self.erros`
(integracoes/focus_client.py:12, alimentada de `dados.get("erros")`). O
handler captura `Exception` genérica e devolve `"Falha na emissão: " +
str(e)` — e `str()` de uma exceção mostra só a mensagem, nunca o `.erros`.

Resultado medido: a tela diz *"verifique o detalhamento dos erros"* e não
mostra detalhamento nenhum. A mensagem do Focus pede que se olhe uma lista
que o sistema descartou uma linha antes de exibir.

**Capturar `FocusError` explicitamente e devolver os `erros`** — cada um
nomeia o campo e o motivo.

## 4 · Selo de "pronto para emitir" na tela Fiscal

O que custou o percurso do Marcelo: **nada valida a configuração do emitente
antes da emissão**. Ele descobriu na última etapa, duas vezes seguidas —
primeiro o token do Focus ausente, depois os campos fiscais.

A emissão depende de campos **todos `nullable`** em `Emitente`:
`cfop_dentro_uf`, `cfop_fora_uf` (fiscal/mapa_fiscal.py:91 escolhe entre os
dois conforme a UF do destinatário), `csosn_padrao`, `csosn_contribuinte`,
`regime_tributario`, `cnpj`, `inscricao_estadual`, `municipio_ibge`, `uf`,
mais o token do ambiente ativo.

**A tela Fiscal mostra o que falta**, item a item, e diz se o emitente está
pronto para emitir. E a etapa 15 avisa **antes** de o usuário chegar nela.

Nota de UX medida: a tela tem **dois botões independentes** — "Salvar
configuração fiscal" e "Salvar credenciais Focus". O Marcelo salvou um e
achou que estava completo. Independentes está certo (há comentário no código
explicando por quê); o que falta é dizer que os dois são obrigatórios.

### Terceira ocorrência, medida em 01/09 — o endereço

Depois do token e dos campos fiscais, a emissão parou numa terceira falta, e
dessa vez a mensagem não nomeia nada:

```
31:0: ERROR: Element '{...}cMun': This element is not expected.
Expected is ({...}xLgr).
```

Traduzido: o schema da NF-e abre o bloco de endereço por `xLgr`
(logradouro), `nro`, `xBairro`, e só então `cMun`. O validador encontrou
`cMun` na primeira posição — ou seja, **logradouro, número e bairro saíram
vazios** e o Focus os omitiu. A linha 31 cai dentro de `enderEmit`: é o
**emitente**, não o destinatário. A tela Fiscal tem a seção "Endereço do
emitente" e ela ficou em branco na limpeza da base.

O ponto que interessa para a tarefa: `mod_fiscal.prontidao_emitente`, no
ramo `produto`, checa **apenas** `regime_tributario` e `uf`. O endereço
inteiro passa. E o **destinatário não é checado em lugar nenhum** — um
cliente sem logradouro produz exatamente o mesmo erro, uma dezena de linhas
mais abaixo, em `enderDest`.

Então o selo do item 4 cobre os três blocos, não um:

1. **Emitente — identificação e regime**: os campos já listados acima.
2. **Emitente — endereço**: `logradouro`, `numero`, `bairro`, `cidade`,
   `uf`, `cep`. Todos obrigatórios pelo schema; hoje todos `nullable`.
3. **Destinatário — endereço**: os mesmos campos no `Cliente`, verificados
   na etapa 15 contra o cliente daquele projeto, antes de chamar a Focus.

E a regra que vale para os três: **erro de schema da SEFAZ é falha nossa de
validação**. Se a mensagem que chega ao usuário for uma linha de XSD, a
guarda não existia. `prontidao_emitente` nomeia o campo; a SEFAZ nunca deve
ser quem descobre que ele está vazio.

## 5 · NF-e H e NF-e P — dois botões na emissão

**Pedido do Marcelo, 01/09.** Em vez de emitir documento oficial e depois
cancelar quando algo entre fábrica e loja atrasa, emite-se em **homologação**
para destravar a fase e a entrega, e a **produção** sai depois.

- **NF-e H** — homologação. Destrava a fase, permite a entrega seguir.
- **NF-e P** — produção. O documento oficial.

### A regra que faz isso funcionar sem criar buraco

Uma NF-e de homologação **não tem validade fiscal**, mas a emissão dispara
contabilidade real (`faturar_segmento` escritura receita). Sem trava, o
projeto andaria com receita faturada sobre documento inexistente, e nada
marcaria que a nota oficial nunca saiu — entrega feita, obrigação fiscal
invisível.

**Avançar é livre; fechar não é.** A NF-e H destrava a fase e a entrega; o
projeto **não conclui** enquanto a NF-e P não sair. Vira pendência visível,
no mesmo formato do veredito de provisão: o sistema não decide sozinho que a
nota oficial não precisa existir.

### DECIDIDO 01/09 — a receita é escriturada na H

A mercadoria saiu, a entrega aconteceu, o resultado é real. A NF-e P **troca
o documento**, não cria o fato. É o mesmo princípio que orientou a auditoria
inteira: o livro registra o que aconteceu.

Com o ACHADO-13 consertado, a emissão da P fatura só o **delta** — que será
zero se a H já faturou o total. Nada duplica.

**A obrigação da P fica como providência posterior**, e precisa ser visível:

**Marcador no nome do projeto** — um bullet pequeno, sobrescrito, com um
**N** dentro, ao lado do nome, em toda lista e cabeçalho onde o projeto
aparece. Sai quando a NF-e P for emitida.

**E o projeto não conclui com a pendência aberta**, pela regra já escrita
acima: avançar é livre, fechar não é.

---

## O que reportar

1. Os itens 1 a 4 consertados, com aceite por item.
2. O item 5 **não implementado** até a decisão acima — só o desenho escrito.
3. Se a validação do item 2 rejeitar alguma das NF-e reais em
   `tests/fixtures/nfe/`, isso é achado: elas parseiam hoje.
