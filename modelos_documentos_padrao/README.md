# Modelos de documento PADRÃO do Orizon (sem empresa)

Diretório criado em 2026-08-20 (pedido do usuário) para guardar as versões-mestre dos
modelos de documento que o **Orizon oferece por padrão** — texto e regras já
padronizadas, **sem dado de nenhuma loja específica** (nome, CNPJ, endereço etc. ficam
como marcador, nunca hardcoded). A ideia: toda loja nasce com esse modelo ativo e pode
adequar (ou substituir por completo) via **Config → Documentos** — o modelo daqui é o
ponto de partida, não o único texto possível.

## Onde cada coisa mora hoje (contexto pra não confundir)

- **Este diretório (`modelos_documentos_padrao/`)** — fonte-mestre em Markdown,
  versionada no git, **sem** dado de loja. É daqui que se importa (via LibreOffice/
  `mod_documentos_import.normalizar`, se vier de `.docx`) a versão inicial de cada tipo.
- **`contrato_template/`** — o fallback GLOBAL antigo (pré-sistema por loja), só usado
  quando uma loja **nunca** ativou nenhum modelo próprio (`documento_modelos` vazio) —
  ver `mod_documentos.py`. Hoje só cobre `contrato`/`termo_aditivo`. Continua existindo
  por compatibilidade; não é o lugar de editar o texto padrão novo — esse passa a ser
  aqui.
- **`documentos_loja/<loja_id>/<tipo>/`** — staging/versões do **importador por loja**
  (`mod_documentos_import`), **gitignored** (é dado de runtime de cada instalação, não
  do repositório — cada loja real, incl. produção, tem sua própria pasta local).
- **Tabela `documento_modelos` (Postgres)** — a **fonte de verdade em produção**: uma
  versão ATIVA por loja+tipo, imutável depois de persistida (editar = criar a próxima).
  O conteúdo daqui vira a *primeira* versão de cada loja nova; depois disso, cada loja
  evolui a própria independentemente.

## Tipos registrados (`mod_documentos.TIPOS`)

`contrato`, `proposta`, `termo_aditivo`, `aprovacao_pe`, `termo_vistoria`,
`termo_responsabilidade`, `solicitacao_medicao`, `checklist_eletros`,
`autorizacao_foto_video`, `carta_agradecimento` — mais os customizados (`doc_*`, por
loja, fora deste diretório por definição).

**Nem todo tipo registrado tem geração real ligada na tela do projeto ainda** —
`termo_vistoria`/`termo_responsabilidade` por exemplo só têm o *cadastro* do modelo
habilitado; o botão que gera pra um projeto real é frente futura (achado ao investigar
os documentos reais da Inspirium, 2026-08-20 — ver DEV_LOG Sessão 199/200).

## Convenção de marcador

`[MARCADOR_EM_MAIUSCULO]` — bracket style, **nunca** `{{ jinja_style }}` (achado real:
um modelo ativo tinha `{{ data_contrato }}`/`{{ consultor_nome }}` no corpo e nunca
substituía nada — a API só reconhece o formato com colchetes). Catálogo oficial dos
marcadores válidos: `mod_marcadores.CATALOGO` (travado contra `mod_contrato.
_montar_mapping` por teste anti-drift — todo marcador usado no corpo precisa constar
lá).

## Arquivos

**IMPORTANTE:** cada `.md` daqui é lido e usado **INTEIRO** como corpo do documento
(`mod_documentos.carregar_modelo_padrao` → botão "Usar modelo padrão Orizon" em Config →
Documentos) — não coloque comentário/nota de desenvolvimento dentro do `.md` (nem em
marcador entre colchetes de exemplo: viraria `desconhecido` na análise e bloquearia a
ativação, ou pior, saía impresso literal no PDF). Notas de contexto ficam **aqui**.

- `termo_vistoria.md` — rascunho convertido do PDF real da Inspirium ("Documento de
  Vistoria", Documento 109, Revisão -, 16/03/2022 —
  `DOCUMENTOS LOJA\Atuais\termo_vistoria_ambiente.pdf`). Campos OK/Não-Ok simples, mapeia
  razoavelmente pro modelo de "clause + marcador" do sistema. O original tem um campo
  livre "Ambiente:" por vistoria que ficou como linha em branco (`___`) — não existe
  `AMBIENTE` no `CATALOGO` ainda; a frente que ligar a geração real (pra um projeto, com
  múltiplos ambientes) precisa decidir se vira marcador novo ou campo do formulário.
- `termo_responsabilidade.md` — idem, do "Termo de Aceite e Finalização de Montagem"
  (Documento 111, Revisão -, 16/03/2022 — `DOCUMENTOS LOJA\Atuais\termo_vistoria_final.pdf`).

Ambos ainda **não têm geração real ligada na tela do projeto** — só o cadastro do modelo
(Config → Documentos) está habilitado; o botão que gera o documento preenchido pra um
projeto real é frente futura (ver DEV_LOG Sessão 199/200).

**Ficaram de fora desta rodada** (2026-08-20) — não são conversão direta de "texto de
cláusula com alguns marcadores", são **formulários** com estrutura própria que o motor de
documento atual não suporta:
- **Termo de solicitação/aprovação de medição** (o real da Inspirium): checklist técnico
  item-a-item (gesso, batentes, elétrica, colunas...) com parecer + motivo por item, mais
  uma tabela de ambientes dinâmica. Bem mais rico que o que `solicitacao_medicao` gera hoje
  (Termo de Responsabilidade simples + 2 assinaturas). Fundir os dois exigiria decidir se o
  motor de documento ganha CAMPOS DINÂMICOS (não só marcador de texto) — decisão de produto,
  não só de conteúdo.
- **Termo de reserva de slot de entrega/montagem** (documento novo, 2026): tabelas de datas
  planejadas + período/recurso reservado + lista de regras. Não tem `tipo` correspondente
  ainda no catálogo (`mod_documentos.TIPOS`).

Modelo de contrato (`contrato.md`) e proposta ainda não replicados aqui — o
`contrato_template/contrato.md` já cumpre esse papel hoje (é o fallback global ativo,
usado pelo localhost); mover pra cá é reorganização, não urgente.
