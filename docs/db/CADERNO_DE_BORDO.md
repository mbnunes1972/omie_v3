# Caderno de Bordo

Estado vivo da execução das fatias. Existe para que QUALQUER sessão — o Marcelo, o Claude
Code, uma sessão de orientação, ou uma sessão agendada — retome de onde parou sem reconstruir
o contexto na conversa. Criado em 06/09/2026.

**Não é** o ROTEIRO (a fila do que fazer), nem os ACHADOS (o que está errado), nem o
MODELO_CONTABIL (a regra). É o diário: o que foi feito hoje, o que está vermelho agora, e o
que está travado esperando decisão.

---

## Regras da execução

**1. Um executor por vez.** A árvore de trabalho é uma só. Antes de editar qualquer arquivo,
conferir aqui quem está com a mão nele. Duas sessões escrevendo no mesmo arquivo é estrago
difícil de desfazer — e nenhuma das duas percebe na hora.

**2. O gate é a suíte inteira, não a parte que der para rodar.** [MEDIDO 06/09] A sessão de
orientação alcança a máquina do Marcelo por um shell Linux com a pasta montada. Nesse shell:
  - RODA: testes de motor puro (mod_negociacao, mod_provisoes, cálculo sem banco).
    As dependências do requirements.txt instalam ali (rede aberta).
  - NÃO RODA: tudo que precisa do PostgreSQL (`localhost:5432` recusa conexão — o banco é do
    Windows, a VM não o enxerga) — ou seja, toda a camada contábil, AF, contrato e razão.
  - NÃO RODA: E2E de browser.
  - NÃO FAZ: git (deixa `.git/index.lock` preso) e não apaga arquivos.
Portanto: verificação parcial NUNCA autoriza avançar de fatia. Ela serve para detectar
vermelho cedo, não para dar verde.

**3. O que interrompe a corrente e espera o Marcelo:**
  - qualquer teste que estava verde e ficou vermelho;
  - qualquer decisão de DESENHO — o que é certo para o negócio (não o que é certo no código);
  - qualquer coisa que mude número que o cliente vê, ou que mexa em dinheiro;
  - Produção, sempre.

**4. Decisão de desenho não se automatiza.** [DECIDIDO 06/09, Marcelo e orientação] Em 06/09 o
desenho do ACHADO-63 mudou duas vezes, as duas por conhecimento de negócio que não está no
repositório (a rota B foi recomendada pela orientação e barrada pelo Marcelo: o cliente confere
o desconto na mesa). Nenhum teste teria pego. Automatizar o mecânico — medir, aplicar, testar,
registrar, parar. Nunca o que decide o que é certo.

**5. Toda entrada é datada e marcada:** [MEDIDO] o que foi conferido no código/no razão,
[DECIDIDO] o que o Marcelo fechou, [ABERTO] o que ainda não tem resposta.

---

## Estado em 06/09/2026

### Em execução agora

**F2-32 — ACHADO-63/64 (negociação: custos adicionais acompanham o desconto)**
Executor: **Claude Code** (mão em `mod_negociacao.py`, `tests/`, e a seguir `static/index.html`).
- Fatia 1 (motor): [MEDIDO 14:30, verificação independente pela orientação; verificação em
  camadas completa por este executor, ~11:45]
  `mod_negociacao.py` com `termo_via_bri = (num_via + num_bri)` (+ `base_custos` e `cust_esp`
  ajustados, `Cust_Via_Recup`/`Bri_Recup`/`Cust_Esp_Recup`/`Desc_Efetivo` novos no retorno);
  `tests/test_negociacao.py` atualizado (5 casos rederivados à mão); `tests/
  test_achado63_custos_acompanham_desconto.py` criado (6 aceites). **26 testes passam** (motor
  puro) — e o subconjunto contábil/AF/contrato/negociação com banco (599 testes) também passa
  limpo, LP-16 incluído (não flakou nesta rodada). Verificação em camadas COMPLETA para esta
  fatia — commit `65b2d6c`. Sem tag/deploy (só quando o F2-32 inteiro fechar, regra #2 deste
  caderno). Parando aqui — o pedido recebido nesta sessão foi só a Fatia 1; Fatias 2-5 não
  iniciadas por este executor, aguardando instrução.
- Fatia 2 (desconto efetivo no quadro do Valor de Contrato): não iniciada.
- Fatia 3 (colunas "custa" × "cliente paga" nos parâmetros): não iniciada.
- Fatia 4 (unificar #neg-total-final, apagar o gêmeo #neg-parcelado): não iniciada.
- Fatia 5 (documentação da troca de regra): não iniciada.

### Fechado hoje

**F2-31 Fatia 1 — ACHADO-61** (`out_forn` dos Parâmetros não constituía provisão no contrato).
[MEDIDO] `main.py:785` com a chave `outros_forn`; comentário de `_PROV_FECHAMENTO` corrigido;
aceite novo com 3 testes; subconjunto contábil/AF/contrato (553 testes) verde exceto o flake
já documentado (LP-16). Commits 6120ed6 + e78e74d. **Sem tag e sem deploy.**

### Pendente, na ordem

1. **F2-31 Fatia 2 — ACHADO-62**: redução de Outros Fornecedores na AF é silenciosa
   (`_migracao = max(0, ...)` ignora decréscimo). Pacote escrito, não entregue.
   [ATENÇÃO] Enquanto não entrar, baixar esse campo na AF durante um percurso mostra o defeito
   conhecido — não é o pacote novo falhando.
2. Tag `v2026.09.06-beta3` (ou a que vier) + Integração/Homologação, quando F2-32 fechar.
3. Percurso do Marcelo no Projeto 8: Parâmetros com Outros Fornecedores ANTES da assinatura,
   depois AF1 subindo o valor. Não testar redução até a F2-31 Fatia 2 entrar.
4. Itens 3 e 4 do percurso do beta2 (o razão do modelo, cinco checkpoints; a despesa avulsa).

### Aberto, sem dono

- **LP-16 e LP-21**: dois testes não determinísticos. [ABERTO] Com dois casos, o método muda:
  comparar os dois procurando fixture/seed/ordem em comum, em vez de perseguir cada um.
- **LP-15** (markup de ajuste), **LP-18** (fases/recebimento), resto da LP-13.
- **Item 5 do bloco fiscal** (F2-21, SUSPENSO — o modelo de emissão mudou por baixo).
- **Produção**: fora da esteira desde 28/08, aguarda rebuild a partir de tag; o serviço roda
  como root, a corrigir só no rebuild. NÃO TOCAR até lá.
- Topologia `papel_cnpj` + `pct_mercadoria`/`pct_servico` no painel fiscal.
