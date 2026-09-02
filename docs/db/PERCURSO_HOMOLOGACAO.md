# Percurso manual de homologação

O teste que a suíte não faz. Repete-se **inteiro** a cada candidato, não só
na parte que mudou — a razão está no ROTEIRO: a suíte prova o servidor, o
percurso prova o sistema.

**Candidato atual:** `v2026.09.01-beta1` (Integração e Homologação;
Produção não recebeu nada).

**Como reportar:** defeito encontrado vira achado numerado, não vira
recado. Diga em que etapa, o que você esperava, o que apareceu.

---

## Antes de começar

O percurso é do **cadastro do cliente até o projeto Concluído**, passando
por todas as etapas. Não pule as que "não mudaram": as correções desta
rodada mexeram no **fichário do Ciclo**, que é o contêiner de todas elas.

---

## A · O fichário (correção nova — ninguém viu funcionar ainda)

1. Abra um projeto com **plano de pagamento longo** (Cartão 15x ou Aymoré
   parcelado) — o defeito só aparece quando a negociação é mais alta que a
   tela.
2. Abra o Ciclo e **role até o fim**. Nada da negociação pode aparecer
   embaixo: nem valor de contrato, nem tabela de parcelas.
3. Ainda dentro do Ciclo, abra a **Reconciliação do projeto**. O modal tem
   que aparecer normalmente — ele é filho da mesma página que foi escondida,
   e é a exceção da regra.
4. Feche o Ciclo. A negociação volta inteira.

## B · Os selos da Conciliação Final

Na etapa da Conciliação Final, olhe a **coluna de estado** antes de clicar
em nada:

5. Rubrica que nunca teve movimento neste projeto mostra **—**, não
   "Resolvida". Se aparecer uma tela de verde em rubricas que nunca
   aconteceram, o conserto não pegou.
6. Rubrica com efetivação parcial mostra **Parcialmente Efetivada** — e
   mostra isso mesmo sendo rubrica de veredito nomeado. O selo fala do
   dinheiro, não de onde se age.

## C · Efetivar (o que voltou depois do ACHADO-33)

7. Na linha de **Provisão de Montagem**: o botão **Efetivar existe e está
   habilitado**, e o **Resolver não existe** — no lugar dele, o link "Dar
   veredito na Fila de Provisões".
8. Digite um valor e efetive. Confira três coisas: o toast diz **"Efetivado
   R$ <valor>"**, a linha **realça** por um instante, e a coluna
   **Efetivado** muda.
9. **Clique de novo com o mesmo valor, no mesmo dia.** Tem que dizer **"Já
   efetivado hoje"** e a coluna Efetivado **não pode dobrar**. Este é o
   teste de que o sistema conta o que aconteceu, não o que foi digitado.
10. Passe o mouse nos botões. O texto explica **o efeito no livro** (despesa
    na competência, ativo diferido, destino da sobra), não o nome do botão.

## D · A Fila de Provisões — nunca vista por olho humano

A tela existe desde ontem e nenhum ser humano deu um veredito nela. É o
trecho mais arriscado do percurso.

11. Pelo link da linha, chegue à Fila (Financeiro → Fila de Provisões).
12. Dê os vereditos das rubricas abertas. Use pelo menos um de cada:
    - **encerrada_valor_menor** com um valor efetivado real;
    - **nao_se_aplica** — ele **exige motivo escrito**; tente sem motivo
      primeiro e confirme que recusa;
    - **ainda_vai_chegar** em uma rubrica, e então volte e tente concluir a
      Conciliação Final: **tem que recusar**, dizendo qual rubrica. Depois
      troque o veredito para poder seguir.

## E · Fechar

13. Concluir Conciliação Final. O projeto vira **Concluído**, com data.
14. Reabra o projeto concluído e confira que a etapa mostra o estado final,
    sem oferecer ação nenhuma.

---

## O que este percurso não cobre, e por quê

**O selo fiscal** (`TAREFA_BLOCO_FISCAL.md`, item 4) não está neste
candidato — é o próximo. A etapa 15 vai emitir sem avisar se o emitente
está completo; ela já emitiu uma vez com a configuração atual, então não
deve travar, mas o silêncio é conhecido e não é achado novo.

**F2-8** (a folha que resolve provisão sem veredito) está na fila ativa e
não neste candidato. Um projeto cuja comissão já passou por folha paga
chega à Conciliação Final sem essa rubrica em aberto — é esperado, não é
defeito desta rodada.
