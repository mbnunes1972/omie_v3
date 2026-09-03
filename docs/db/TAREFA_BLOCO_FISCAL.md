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

## 2 · Validar o XML no upload, não na emissão (ACHADO-31) · FEITO 03/09

`fiscal/mod_nfe.problemas_de_upload` + recusa 400 no upload da etapa 15; medido antes de
travar, nenhum dos 5 XML conhecidos seria rejeitado. Detalhes no ACHADO-31.

**Atenção ao marcar este item como fim do ACHADO-31: não é.** A outra metade do achado — o
*markup de ajuste*, decidido em 31/08 — nunca foi implementada e não é item nenhum deste bloco.
Foi para a `LISTA_PARALELA.md` como LP-15 em 03/09, para não ficar sem dono.

Hoje o upload aceita qualquer arquivo e quem rejeita é
`mod_nfe.preview`, dois passos depois, sem dizer que o problema é o arquivo.
**Parsear no upload e recusar ali.**

Medição já feita: as NF-e reais da fábrica
(`nfe_amostras/NFe-1632*.xml`) parseiam sem erro — 12 itens, com NCM,
CFOP, unidade. O parser está bom; falta a validação estar no lugar certo.

## 3 · Mostrar o detalhamento do erro do Focus · FEITO 03/09

`FocusError` **guarda** a lista de erros da SEFAZ em `self.erros`
(integracoes/focus_client.py:12, alimentada de `dados.get("erros")`). O
handler captura `Exception` genérica e devolve `"Falha na emissão: " +
str(e)` — e `str()` de uma exceção mostra só a mensagem, nunca o `.erros`.

Resultado medido: a tela diz *"verifique o detalhamento dos erros"* e não
mostra detalhamento nenhum. A mensagem do Focus pede que se olhe uma lista
que o sistema descartou uma linha antes de exibir.

**Capturar `FocusError` explicitamente e devolver os `erros`** — cada um
nomeia o campo e o motivo.

## 4 · Selo de "pronto para emitir" na tela Fiscal · MEDIDO 03/09, decisão pendente do Marcelo

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
   `nfe_amostras/`, isso é achado: elas parseiam hoje.


---

# Pacote de execução — itens 3, 4 e 5 (medido em 03/09)

Escrito depois de fechar os itens 1 e 2, para ser executado pelo Claude Code na
bancada. **As medições abaixo são leitura estática do código, com linha citada** —
foram feitas numa sessão sem Postgres e sem rota para os servidores, então tudo que
depende de RODAR (suíte, contagem em base real, `alembic current`) está marcado como
tarefa de quem executa, nunca como fato já apurado.

**Duas coisas que este pacote NÃO autoriza:**
- **Não mexer no markup de ajuste.** É a metade não implementada do ACHADO-31, virou
  **LP-15** em 03/09 e tem decisão própria. Item 2 fechado não é ACHADO-31 fechado.
- **Não trocar o endereço do destinatário da nota.** `fiscal/mapa_fiscal.py:63-64` monta
  o destinatário do **cadastro** do Cliente (`logradouro/numero/bairro/cidade/estado/cep`).
  Existe também um endereço de instalação (`Cliente.inst_*`) que a nota **não** usa —
  parece bug e não é decisão deste item; se for o caso, vira achado com número.

## Item 3 — detalhamento do erro do Focus

**Medido:** `FocusError` guarda a lista da SEFAZ em `self.erros`
(`integracoes/focus_client.py:8-12`). **São TRÊS rotas que a engolem, não uma** — o texto
original do item fala em "o handler", no singular:

| rota | linha |
|---|---|
| `POST /api/admin/lojas/<id>/nfe/emitir-teste` | `main.py:15220` |
| `POST /api/projetos/<nome>/ciclo/15/emitir-nfe` | `main.py:15433` |
| `POST /api/projetos/<nome>/ciclo/15/emitir-nfse` | `main.py:15539` |

As três fazem `except Exception as e: "Falha na emissão: " + str(e)`, e `str()` de uma
exceção mostra só a mensagem — nunca o `.erros`. É a regra dos irmãos do ACHADO-26:
consertar uma e deixar duas é o mesmo defeito com outro endereço.

**O que fazer:** `except FocusError as e` **antes** do `except Exception`, devolvendo os
`erros` no JSON (lista, além da mensagem) nas três; a tela mostra item a item. Manter o
`except Exception` como rede de trás.

**Aceite exigido:** um teste que injeta `FocusError(..., erros=[...])` e prova que a lista
chega na resposta — **nas três rotas**. Sem decisão pendente; pode ser feito direto.

## Item 4 — selo de "pronto para emitir"

**Medido:** `fiscal/mod_fiscal.py:56-82`. No ramo `produto`, `prontidao_emitente` confere
**apenas** `regime_tributario` e `uf`. O endereço do emitente inteiro passa, e o
**destinatário não é conferido em lugar nenhum** — que é a terceira falta que custou o
percurso de 01/09 (o erro de schema `cMun`/`xLgr`). No ramo `servico` ele já confere quatro
campos, então o desenho de "lista nomeada do que falta" já existe e é o que estender.

**Campos que o selo cobre (todos `nullable` hoje, conferido no modelo):**
- *Emitente — identificação e regime:* `cnpj`, `inscricao_estadual`, `regime_tributario`,
  `csosn_padrao`, `csosn_contribuinte`, `cfop_dentro_uf`, `cfop_fora_uf`, `municipio_ibge`,
  `uf`, mais o token do ambiente ativo.
- *Emitente — endereço:* `logradouro`, `numero`, `bairro`, `cidade`, `uf`, `cep`.
- *Destinatário — endereço (Cliente):* `logradouro`, `numero`, `bairro`, `cidade`,
  **`estado`** (o Cliente não tem coluna `uf`; `inst_uf` é do endereço de instalação, que a
  nota não usa), `cep`.

**DECISÃO PENDENTE — o selo avisa ou BARRA?** O texto do item diz "mostra o que falta" e
"avisa antes"; não diz se recusa a emissão. *Recomendação:* barrar, **com medição antes** —
contar nos três ambientes quantos emitentes e quantos clientes de projeto na etapa 15
ficariam incompletos. Se der zero, barrar não custa nada e fecha a classe; se não der,
a contagem vira a decisão. **Não barrar sem essa contagem** — é a regra que o projeto
aplicou no ACHADO-44, no 45 e no 48.

**Medido em 03/09, nos três ambientes reais** (script pontual, não commitado — leitura, sem
travar nada):

| ambiente | emitentes (total) | incompleto — identificação | incompleto — endereço | incompleto — token | clientes na etapa 15 | incompleto — endereço |
|---|---|---|---|---|---|---|
| Integração | 1 | 1 (`inscricao_estadual`, `csosn_padrao`, `csosn_contribuinte`, `cfop_dentro_uf`, `cfop_fora_uf`) | 1 | 1 | 0 | 0 |
| Homologação | 1 | 1 (`csosn_padrao`, `csosn_contribuinte`) | 0 | 0 | 1 | 0 |
| Produção | 0 | 0 | 0 | 0 | 0 | 0 |

**Não deu zero.** 2 dos 2 emitentes reais (Integração + Homologação) ficariam incompletos
pelo menos num grupo — a contagem não fecha a classe sozinha, vira decisão do Marcelo (avisar
vs. barrar, e o que fazer com os 2 emitentes já incompletos se a resposta for barrar).
"Clientes de projeto na etapa 15" medido como: `Cliente` ligado a um `Projeto` (`projetos_meta`)
que tem alguma linha em `ciclo_etapas` com `etapa_codigo='15'` — sem filtrar por status da
etapa (medida a população que já *chegou* na etapa de emissão, não só a que está parada nela
agora); o único encontrado (Homologação) está completo no endereço. **Não implementado —
aguardando a decisão.**

**Aceite exigido:** um teste por bloco (identificação, endereço do emitente, endereço do
destinatário), provando que a falta é nomeada campo a campo; e a etapa 15 avisando antes de
o usuário chegar na emissão. Nota de UX já medida no item: os dois botões de salvar
(configuração fiscal e credenciais Focus) são independentes de propósito — falta dizer na
tela que os dois são obrigatórios.

## Item 5 — NF-e H e NF-e P

**Já decidido em 01/09** (ver a seção do item): a receita é escriturada na H, a P troca o
documento e não cria o fato; o projeto **não conclui** com a P pendente; marcador com "N"
ao lado do nome do projeto. Com o ACHADO-13 consertado, a emissão da P fatura só o delta —
zero se a H já faturou o total, então nada duplica.

**DECISÕES PENDENTES antes de escrever:** (a) **onde** mora o gate "não conclui" — qual
etapa/endpoint fecha o projeto hoje e passa a recusar; (b) **em quais listas** o marcador
aparece (o item diz "toda lista e cabeçalho onde o projeto aparece", que precisa virar uma
lista concreta de renderizadores).

**Recomendação de ordem:** 3 e 4 primeiro, num candidato; o 5 sozinho depois. Ele é o único
que muda **regra de fechamento de projeto**, e misturá-lo com dois consertos pequenos
transforma um percurso de teste em três de uma vez.
