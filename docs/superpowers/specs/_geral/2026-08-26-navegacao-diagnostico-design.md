# Navegação — diagnóstico e princípios

**Data:** 2026-08-26 · **Repo medido em:** `26714a7`
**Status:** diagnóstico fechado, princípios propostos, **decisões em aberto com o Marcelo**

> Este documento **não é uma ordem de serviço**. A §5 lista o que pode ser feito já; o resto
> depende de decisões que o Marcelo e o Claude (Cowork) vão fechar antes de virar código.

---

## 1. O que a navegação é hoje, medido

### 1.1 A tela é um número

```js
function goPage(n){
  const navId  = n === 9 ? 'nav-cfg' : (n >= 10 ? 'nav-'+n : 'nav-0'+n);
  const pageId = n === 9 ? 'page-09' : (n >= 10 ? 'page-'+n : 'page-0'+n);
  ...
  if(n===2)  _sbParamsAtualizar();
  if(n===0)  projCarregar();
  if(n===7)  adminCarregarConsole();
  if(n===9)  cfgRender();
  if(n===10) cadRender();
  if(n===11) adminFiscalCarregar();
  if(n===12) finTab('prov');
  if(n===13) expedicaoKanbanCarregar();
  if(n===15) comercialDashCarregar();
  if(n===16) agendaAbrir();
  if(n===18) operacionalAbrir();
}
```

A identidade de cada tela é um **inteiro**, que vaza para os ids do DOM (`page-02`, `nav-02`). O
roteador carrega uma cadeia de **doze efeitos colaterais** e, com isso, **conhece todos os módulos** —
é o oposto da fronteira que o `modulos.py` declara no backend.

São **18 painéis** para **32 chamadas** de `goPage`, mais **quatro roteadores paralelos**:
`goPage`, `goPageOrizon` (3), `goPageRede` (5), `goPageEstrategico` (2).

### 1.2 Nenhuma tela tem endereço

Não há rota na barra do navegador. Tudo acontece em `/`, e o único "navegar" real do sistema é
`window.location.href = '/'` ou `'/login'`. Consequências concretas:

- **Voltar e avançar do navegador não funcionam** — os botões que o usuário mais conhece.
- **Não dá para mandar um link** de um projeto para um colega.
- **Não dá para favoritar** uma tela.
- **Recarregar não devolve onde você estava** de forma previsível.
- Abrir dois projetos em duas abas não é possível.

### 1.3 Dois vocabulários para "visível"

`.page` usa a classe `active` (inglês). `#ciclo-panel` usa `ativo` (português). `goPage` limpa
apenas `active` — nunca `ativo`. É a mecânica mais provável por trás do estado que reproduzi na
revisão (lista de Projetos e fichário de outro projeto renderizados empilhados após recarregar).

### 1.4 Duas portas para o mesmo projeto, e a errada é a padrão

"Abrir →" na lista sempre cai na **Negociação**, seja qual for a fase. Abri um projeto com
FASE DO CICLO = *Briefing* e caí na tela de orçamento, com o briefing por preencher e nada na tela
dizendo isso. O sistema mostra a fase na coluna ao lado do botão e ignora essa informação ao abrir.

### 1.5 O cabeçalho do fichário virou depósito

Oito botões em **duas linhas** (a 1512px), misturando cinco naturezas sem hierarquia visual:

| natureza | botões |
|---|---|
| navegação | ← Voltar |
| contexto | Responsável: … · etapa N — … |
| consulta | Cronograma, Auditoria Contábil, Provisões |
| ação que mexe no razão | Retenção |
| configuração | Equipe, Mapa de Atribuições, Grupo de Acompanhamento |

Todos com o mesmo peso, tamanho e cor.

### 1.6 A navegação principal é o elemento mais espremido da tela

A lombada do fichário é o menu de 15 destinos do projeto, e mostra **6**. Medido: 239px de altura
para 586px de conteúdo, com 300px de tela vazia logo abaixo. (Causa e correção verificada no
relatório de achados, P1-2.)

### 1.7 Outros atritos de navegação já medidos

- **Sete elementos "Voltar"** numa única tela do fichário.
- Na **Negociação não existe volta** para Projetos — só pela sidebar.
- **Consulta abre em modal por cima do contexto**: Provisões e Retenção cobrem o fichário inteiro.
- **Sidebar de 14 destinos sem hierarquia de papel** — um consultor e um gerente
  administrativo-financeiro entram na mesma tela e veem a mesma lista.
- **Numeração dupla**: o mesmo código `13` aparece como "9 Logística e Expedição" (lombada),
  "13 · Visão geral" (sub-aba) e "etapa 13 · Produção" (modal de Retenção). E as etapas internas
  8 e 9 não têm aba nenhuma, com o cabeçalho imprimindo código cru que colide com a numeração de
  exibição.
- **O filtro da lista de projetos** persiste ao recarregar mas aceita digitação por cima,
  concatenando ("Teste_0820Teste_0820" → nenhum resultado, sem causa visível).

---

## 2. O padrão por trás dos sintomas

Os itens acima não são doze problemas independentes. São **três**:

**a) Não existe um modelo de endereço.** Sem URL, a "tela atual" é uma variável global e o estado é
reconstruído por efeito colateral. Daí vêm: voltar/avançar quebrados, reload imprevisível, painéis
empilhados, filtro perdido, impossibilidade de compartilhar link.

**b) Não existe hierarquia declarada.** Nada diz o que é navegação, o que é ação e o que é consulta.
Daí vêm: cabeçalho-depósito, sete "Voltar", consulta em modal sobre contexto, ação destrutiva com o
mesmo peso de um relatório.

**c) O ponto de entrada ignora o estado do objeto.** O sistema sabe em que fase o projeto está e abre
sempre no mesmo lugar. Daí vêm: porta errada por padrão, briefing pendente invisível, e o usuário
tendo que descobrir sozinho para onde ir.

---

## 3. Princípios propostos

Cinco, em ordem de impacto. Cada um é discutível — estão aqui para serem aceitos ou recusados
explicitamente, não para serem implementados de imediato.

**P1 · Toda tela tem endereço.** Um roteador único, com a rota na URL. Voltar e avançar do navegador
passam a funcionar; um projeto vira link; recarregar devolve onde você estava.

**P2 · Uma porta por projeto, e ela abre onde o projeto está.** "Abrir →" leva ao lugar que a fase
indica — ou a uma visão do projeto que mostra a fase e oferece o próximo passo.

**P3 · O cabeçalho separa navegação de ação.** Voltar e contexto de um lado; ação primária visível;
consulta e configuração recolhidas. Um botão que mexe no razão nunca tem o mesmo peso de um relatório.

**P4 · Consulta não cobre contexto.** O que se consulta *enquanto* se trabalha (Provisões, Cronograma)
não deveria ser modal em cima do fichário.

**P5 · Um vocabulário só.** `active`/`ativo`, numeração interna/de exibição, "Fechado"/"Concluído" —
escolher um de cada e valer em toda parte.

---

## 4. Decisões em aberto — Marcelo + Claude (Cowork)

Nada disto vira código antes de estar fechado aqui.

**D1 · Adotar URL de verdade: antes ou depois da V1?**
Roteamento por *hash* (`/#/projeto/NAV_QA_P1/etapas/10`) é barato, não exige nada do servidor e já
resolve voltar/avançar/link/favorito. `history.pushState` é mais limpo mas exige o servidor devolver
o `index.html` em qualquer caminho. Recomendação: **hash, antes da V1** — é a mudança de maior
retorno por risco de toda a lista.

**D2 · "Abrir →" leva a quê?**
(a) à etapa atual do ciclo; (b) à Visão Geral do projeto, que já existe e mostra fases, financeiro e
histórico; (c) à Negociação, como hoje, mas com aviso quando há pendência anterior.
Recomendação: **(b)** — a Visão Geral já é a tela que responde "onde este projeto está", e serve a
qualquer fase.

**D3 · O cabeçalho vira o quê?**
Uma barra com Voltar + contexto à esquerda, ação primária à direita, e o resto num menu recolhido?
Ou os botões de consulta migram para dentro da Visão Geral? Precisa de mockup antes de decidir.

**D4 · Sidebar por módulo ou por papel?**
Hoje são 14 destinos por módulo, iguais para todos. A alternativa é a entrada mudar por perfil.
Depende de quantos perfis reais existem na operação — pergunta de negócio, não de software.

**D5 · Isso entra antes ou depois da modularização?**
O roteador único (D1) é justamente o tipo de coisa que quer nascer em `static/js/nucleo/`. Fazer a
navegação antes obriga a refazer depois; fazer depois atrasa o ganho. Recomendação: **P1/D1 primeiro,
já pensado como núcleo**; o resto depois da fase 3 da modularização.

---

## 5. O que pode ser feito AGORA, sem esperar as decisões

Itens de navegação já decididos, sem risco de retrabalho quando D1–D5 fecharem.

**N1 · Unificar o vocabulário de "visível".** `.page` usa `active`, `#ciclo-panel` usa `ativo`, e
`goPage` só limpa `active`. Escolher um e aplicar. Baixo risco, e provavelmente elimina o estado de
painéis empilhados.

**N2 · Numeração de exibição também nas sub-abas e nos rótulos de modal.** Hoje as sub-abas usam o
código cru (`13 · Visão geral`) e `_etapaRotulo` usa o nome de `ETAPAS_CICLO` (`13 · Produção`),
enquanto a lombada mostra `9 Logística e Expedição`. Passar tudo por `_fichaNumeroExibicao` e
`_fichaTituloGrupo`.

**N3 · Etapas internas 8 e 9 não têm aba** e o cabeçalho imprime o código cru, que colide com a
numeração de exibição. Decidir se ganham aba, se viram sub-abas de `7` (Contrato — onde as ações
delas já vivem, via `_FICHA_PENDENCIAS`), ou se o cabeçalho passa a mostrar o número da mãe.

**N4 · O fichário em 1/3 da tela** (`.content { display:block }`). Correção verificada no relatório
de achados, P1-2 — com a ressalva de regressão nas outras telas.

**N5 · O filtro da lista de projetos** que persiste e concatena ao recarregar.

**N6 · Limpar os "Voltar" redundantes** no fichário (sete elementos hoje).

---

## 6. Fora de escopo desta frente

- **Cancelamento de Ambiente** — tem mockup próprio (rev 3) e quatro decisões do §7 ainda abertas.
- **Modularização** — spec própria; a fase 3 e esta frente se cruzam em D5.
- Os defeitos não-navegacionais do relatório de 26/08 (datas, pollers, Montagem concluída, sessão).
