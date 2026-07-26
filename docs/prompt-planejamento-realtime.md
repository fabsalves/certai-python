# Missão: novo canal de conversa por voz em tempo real (OpenAI Realtime)

Fala meu lindo, beleza?

Nossa aplicação `@certai-python/` já está redondinha na conversação IA ↔ aluno por texto/áudio via WhatsApp (integração Cinndi). Agora vamos evoluir: adicionar um **novo canal de conversa por voz em tempo real**, usando a **OpenAI Realtime API**, com o aluno falando direto pelo browser.

Sua tarefa agora é **PLANEJAR, não implementar**. Quero um plano de implementação completo, que outro agente consiga executar. Siga rigorosamente as fases abaixo.

---

## FASE 0 — Investigação obrigatória (antes de qualquer plano)

Não planeje nada antes de completar esta fase. Produza uma síntese escrita do que encontrou.

### 0.1 — Investigar `@certai-python/`
Mapeie e documente:
- Como uma **sessão de aluno na aula** é modelada e persistida (entidades, relacionamentos, ciclo de vida)
- Como as **conversas/mensagens** do canal WhatsApp são persistidas (modelo de dados, onde entra a Cinndi)
- Como o **pipeline de score** consome a conversa (que dados ele lê, em que formato, quando roda)
- Onde vivem os **prompts/instructions da Lira** (a persona que conduz a conversa) e como são montados por aula/trilha
- Como funciona hoje o **disparo do template Meta/Cinndi** que inicia a conversa
- Regras de isolamento existentes: como o sistema garante que conversas não se misturam entre alunos/aulas/sessões

### 0.2 — Investigar `@helena-rails/`
Este projeto já implementa OpenAI Realtime com voz no browser. Mapeie:
- Arquitetura da integração: quem abre a conexão com a OpenAI (browser ou servidor)? WebSocket ou WebRTC?
- Como a autenticação com a OpenAI é feita (procure por geração de token efêmero / ephemeral key no backend)
- Como os eventos da Realtime API são tratados (session config, transcrição de áudio do usuário, respostas da IA, encerramento)
- Como o contexto/instructions da sessão de voz é montado
- O que é persistido da conversa de voz e como

**Transporte já decidido: WebRTC** (é o que o helena-rails usa e é a recomendação da OpenAI para client-side). Confirme na investigação como o helena-rails faz o handshake (geração do client_secret/ephemeral token no backend, troca de SDP, data channel para eventos) e use como referência direta de padrão. Consulte a documentação atual da Realtime API para confirmar nomes de eventos e formato do session config — a doc vence em caso de divergência.

**CONSEQUÊNCIA ARQUITETURAL CRÍTICA do WebRTC:** a conexão é browser ↔ OpenAI direto. Os eventos de transcrição (fala do aluno e resposta da IA) chegam APENAS no browser, via data channel. O backend não vê a conversa passar, e a Realtime API não permite recuperar a conversa depois que a sessão encerra. Portanto, a persistência dos turnos depende inteiramente do cliente relayar os eventos para o backend — investigue como o helena-rails resolve isso (se resolve) e trate ingestão como componente de primeira classe no plano (ver princípio 2).

### Output da Fase 0
Síntese estruturada: modelo de dados atual, fluxo atual do WhatsApp, padrão Realtime do helena-rails, e lacunas/dúvidas encontradas. **Liste explicitamente toda suposição que você precisou fazer.**

---

## FASE 1 — Princípios inegociáveis do plano

O plano DEVE respeitar tudo abaixo. Se algum princípio conflitar com o que você encontrou no código, aponte o conflito em vez de ignorá-lo.

1. **Segurança do token:** a API key da OpenAI NUNCA vai para o browser. O FastAPI expõe um endpoint que gera credencial efêmera (ephemeral token) por sessão de voz, com escopo e expiração curtos. O browser usa só essa credencial.

2. **Persistência channel-agnostic (coração da missão):** a conversa por voz deve ser persistida como **turnos no MESMO modelo de conversa** usado pelo canal WhatsApp, com um discriminador de canal (ex.: `whatsapp_text`, `whatsapp_audio`, `realtime_voice`). O pipeline de score NÃO deve precisar saber de qual canal a conversa veio. Se o modelo atual não comporta isso, o plano propõe a evolução do schema (aditiva, sem quebrar o canal atual).
   Como os eventos de transcrição chegam só no browser (ver consequência do WebRTC na Fase 0), a ingestão deve ser desenhada para resiliência em browser mobile (tab pode ser morta a qualquer momento pelo iOS/Android):
   - **Relay incremental:** o cliente envia cada turno ao backend assim que o evento de transcrição chega (ou em micro-batches curtos), nunca acumulando para enviar só no final. Se a call morrer no turno 8, os turnos 1–7 já estão salvos e o score trabalha com o material parcial.
   - **Idempotência:** cada turno enviado carrega uma chave de idempotência (ex.: event_id/item_id da Realtime API) para o backend deduplicar reenvios.
   - **Heartbeat de sessão:** o cliente sinaliza periodicamente que a call está viva; ausência de heartbeat sem encerramento explícito leva a sessão ao estado "abandonada por timeout".
   - **Reconciliação no encerramento limpo:** ao encerrar explicitamente, o cliente envia um evento de fechamento e o backend valida a integridade da sequência de turnos.

3. **Mesmas regras de sessão:** a sessão de voz nasce amarrada à sessão do aluno na aula, exatamente como no WhatsApp. Uma sessão de voz por sessão de aula. Conversas não se misturam entre alunos, aulas ou trilhas. Defina o ciclo de vida: início, reconexão (queda de rede no meio da call), encerramento explícito e encerramento por timeout/abandono.

4. **Continuidade de contexto entre canais (requisito central):** a conversa persistida não serve só ao score — ela É o contexto que a IA usa para conduzir. Concretamente:
   - **Ao iniciar a sessão de voz:** as instructions da sessão Realtime são montadas injetando o histórico da conversa daquela sessão de aula (turnos do WhatsApp que precederam a call, ou de calls anteriores). A Lira atende a call sabendo tudo o que já foi conversado — nunca começa do zero.
   - **Ao reconectar:** call caiu e o aluno voltou → nova sessão Realtime nasce re-seedada a partir dos turnos persistidos, continuando de onde parou.
   - **Ao voltar pro WhatsApp:** se o aluno abandona a voz e responde por texto, o canal WhatsApp conduz com o contexto completo, incluindo o que foi falado na call. Isso só funciona se o relay incremental (princípio 2) estiver correto — os dois princípios são interdependentes.
   - O plano deve especificar COMO o histórico é injetado na sessão Realtime (via instructions no session config, ou via conversation items iniciais — confirmar na doc atual o mecanismo adequado e limites de tamanho) e como o histórico é resumido/truncado se exceder limites.

5. **Uma fonte de verdade para a persona:** as instructions da Lira na sessão Realtime devem ser montadas a partir da MESMA fonte que monta os prompts do canal texto (adaptadas ao formato da Realtime API, mas sem duplicar conteúdo de persona/regras pedagógicas em dois lugares). Nota: o projeto já usa OpenAI em todas as camadas de IA — mantenha esse padrão e reuse a infraestrutura de cliente/configuração existente.

6. **Handoff WhatsApp → voz:** o fluxo começa como hoje (template Meta/Cinndi). O template passa a oferecer/priorizar a conversa por voz via **link (CTA)** contendo um **token assinado de curta duração** que identifica aluno + sessão da aula. O link abre uma página web que valida o token e inicia a sessão de voz já contextualizada. Sem login adicional, sem o aluno digitar nada. O plano deve especificar: formato do token, expiração, validação, e o que acontece se o token expirar ou for reusado.

7. **Voz é prioritária, WhatsApp continua vivo:** o canal texto/áudio via Cinndi permanece funcionando como fallback e como opção. Se a sessão de voz falhar (browser incompatível, sem microfone, rede ruim), o aluno continua a conversa pelo WhatsApp normalmente, na mesma sessão, com contexto completo (princípio 4). O plano deve definir como os dois canais coexistem numa mesma sessão de aula sem duplicar ou conflitar o material de score.

8. **Mudanças aditivas:** solução mais simples primeiro, seguir os padrões existentes do projeto, não refatorar o que já funciona. Nada de reescrever o fluxo Cinndi.

---

## FASE 2 — O que o plano final deve conter

Entregue o plano em markdown, com estas seções obrigatórias:

1. **Visão da arquitetura** — diagrama textual do fluxo completo: template → link → página web → ephemeral token → sessão WebRTC com a OpenAI → eventos no data channel → relay para o backend → persistência → score.
2. **Modelo de dados** — entidades novas/alteradas, com o discriminador de canal e a amarração com a sessão de aula. Migrations necessárias.
3. **Backend (FastAPI)** — endpoints novos: geração de ephemeral token, validação do link assinado, **ingestão de turnos (com idempotência), heartbeat**, encerramento de sessão. Contratos de request/response de cada um.
4. **Frontend (React)** — a página/rota da conversa por voz: captura de microfone, conexão Realtime, UI mínima da call (estado da conexão, indicador de fala, encerrar), tratamento de permissões negadas e browsers incompatíveis.
5. **Ciclo de vida da sessão de voz** — máquina de estados: criada → ativa → reconectando → encerrada (explícita/timeout). O que é persistido em cada transição e como o contexto é re-seedado na reconexão.
6. **Montagem de contexto da sessão de voz** — como o histórico da conversa (WhatsApp + calls anteriores) é injetado ao criar a sessão Realtime, mecanismo usado (instructions vs conversation items iniciais), estratégia de resumo/truncamento para históricos longos.
7. **Integração com o score** — como os turnos de voz alimentam o pipeline existente sem alterá-lo (ou alterações mínimas necessárias).
8. **Alteração do template WhatsApp** — novo texto do template com o CTA de voz mantendo a opção texto/áudio (lembrando das regras de aprovação de template da Meta).
9. **Fases de execução** — quebra em etapas incrementais, cada uma testável isoladamente, com critérios de pronto. Priorize: (a) endpoint de ephemeral token + página de voz funcionando ponta a ponta com sessão hardcoded; (b) amarração com sessão real via link assinado; (c) persistência dos turnos; (d) integração com score; (e) template.
10. **Riscos e pontos de atenção** — latência, custo da Realtime API, limites de sessão, qualidade da transcrição, comportamento em mobile (o aluno vem do WhatsApp, então o browser será majoritariamente mobile — isso é requisito, não detalhe).
11. **Perguntas abertas** — tudo que precisa de decisão humana antes de implementar.

---

## Regras de conduta

- Investigue antes de afirmar. Cite arquivos e trechos reais dos dois projetos na síntese.
- Não invente APIs: confirme na documentação atual da OpenAI Realtime API os nomes de eventos, formato de session config e mecanismo de ephemeral token.
- Se algo no helena-rails contradisser a doc atual da OpenAI, a doc vence — e você registra a divergência.
- Plano bom é plano que outro agente executa sem precisar me perguntar nada além das "perguntas abertas".
