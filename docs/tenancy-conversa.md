# Conversa, org e Cinndi

A conversa (WhatsApp e voz) acha **aluno, aula e chat** pelo aluno, não pelo slug da org.

## O que vale hoje

- Um usuário pertence a **uma** organização.
- O WhatsApp do aluno é **único** no banco.
- Não dá para matricular aluno de uma org na turma de outra.
- O chat é `(turma, aluno, aula)`. A turma já é da org do aluno.
- Inbound: número → esse aluno → aula `ativa` ou a `disparada` mais recente → aquele chat.
- Voz: o token já traz aluno, turma e aula.
- Webhook do bot: `POST /webhooks/cinndi` (produção). `/{slug}` é opcional.
- Envio Cinndi: **um** bot — `CINNDI_API_URL`, `CINNDI_API_KEY`, `CINNDI_SENDER_PHONE` no `.env`. Não usamos `CINNDI_WEBHOOK_TOKEN`.

Com várias orgs no **mesmo** bot, o chat não mistura: o número decide a pessoa.

## Se um dia a regra mudar

Dificilmente vamos fazer os dois. Só estes casos pedem código.

### Mesmo usuário ou número em várias orgs

Aí o WhatsApp deixa de apontar para uma pessoa só. O inbound (`persist_inbound`, `resolve_routable_route`) precisaria de outro recorte — slug na URL, número do bot, ou escolha de aula.

### Cada org com bot ou número próprio

O chat **continua** certo (aluno único). O que muda é o **disparo**: hoje `outbound.py` lê o `.env`. Passar a usar o `OrgConfig` da org do aluno (já gravado em Integrações), com fallback no `.env`. Call sites: `dispatch_service`, `voice_link_service`, worker de inbound.

Não é reescrever conversa. É só de qual número a mensagem **sai**.
