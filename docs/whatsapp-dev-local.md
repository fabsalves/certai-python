# WhatsApp — testes locais (sem celular no inbound)

Simula mensagens **do aluno** batendo no webhook local, no mesmo formato que a Cinndi enviaria.
A resposta da Lira **continua saindo de verdade** via Cinndi pro WhatsApp do aluno.

Inspirado no fluxo do `sam-python` (`bin/send-message` / `bin/send-audio`).

## Pré-requisitos

1. Stack rodando: `bin/dev`
2. Seed carregado: `bin/db-seed` (ou `bin/db-reset`)
3. `.env` com `CINNDI_API_KEY`, `CINNDI_SENDER_PHONE`, `GROQ_API_KEY` (para áudio)
4. **Encerrar a aula uma vez** (professor na turma) — cria a `Conversation` WhatsApp e dispara o template de convite

Sem encerrar a aula, o inbound simulado retorna `no_conversation`.

## ENV — convite e voz

| Variável | Dev local | Prod/staging |
|---|---|---|
| `WHATSAPP_INVITE_USE_VOICE_TEMPLATE` | `true` após v2 APPROVED | `true` |
| `WHATSAPP_INVITE_VOICE_TEMPLATE` | `certai_convite_aula_voz_v2` | idem |
| `FRONTEND_BASE_URL` | `http://localhost:5173` (só `./bin/voice-link`) | `https://app.certai.com.br` (botão WhatsApp) |

O botão do template v2 aponta para `https://app.certai.com.br/voz/{token}`. Em dev, use `./bin/voice-link` ou copie o token manualmente para `localhost:5173`.

Ver: [whatsapp-template-certai_convite_aula.md](./whatsapp-template-certai_convite_aula.md) · [doc-template-cinndi.md](./doc-template-cinndi.md)

## O que você precisa vs o que pode pular

| Etapa | Tunnel Cloudflare | Celular (inbound) | Cinndi API |
|---|---|---|---|
| Encerrar aula (convite) | Não | Recebe 1 msg | Sim |
| Botão "Falar com a Lira" → call | Não* | Sim | Sim (template v2) |
| Simular texto/áudio do aluno | **Não** | **Não** | Não |
| Resposta da Lira | Não | Recebe no WhatsApp | Sim |
| Call de voz (`voice-link`) | Não | Não | Não |

\* Botão abre `app.certai.com.br`; em dev puro use `voice-link` ou cole o token em localhost.

## Simular texto

```bash
./bin/send-message 'Achei difícil a parte sobre tom formal'
```

Variáveis opcionais:

```bash
SEED_STUDENT_PHONE=5585987385666 ./bin/send-message 'outra mensagem'
API_PORT=8001 ./bin/send-message '...'   # se o bin/dev subiu em outra porta
```

Default `SEED_STUDENT_PHONE=5585987385666` → aluno `eriko@certai.app` no seed.

## Simular áudio

```bash
./bin/send-audio fixtures/audio/audio-teste.ogg
```

Outros caminhos também funcionam:

```bash
./bin/send-audio fixtures/audio/minha-nota.mp3
./bin/send-audio /mnt/c/Users/.../nota.m4a
```

- Formatos comuns: `.ogg`, `.mp3`, `.m4a`, `.wav`
- Requer `GROQ_API_KEY` no `.env` (Whisper transcreve antes do turno da IA)
- Debounce igual ao texto (`INBOUND_DEBOUNCE_SECONDS`, padrão 5s)

Áudios de exemplo ficam em `fixtures/audio/` (no repo: `audio-teste.ogg`).

## Voz ao vivo (sem depender do botão WhatsApp)

```bash
./bin/voice-link --student eriko@certai.app
```

Abre `FRONTEND_BASE_URL/voz/{token}` em aba anônima. Requer `OPENAI_API_KEY` e Realtime configurado.

## Fluxo completo sugerido

```
1. bin/dev
2. .env: WHATSAPP_INVITE_USE_VOICE_TEMPLATE=true (após v2 APPROVED)
3. Login professor → encerrar aula da turma seed
4. Aluno recebe WhatsApp com botão OU ./bin/voice-link para testar call local
5. ./bin/send-message '...'     # cross-channel pós-voz
6. Aguardar ~5s (debounce) + tempo da IA
7. Logs no terminal do worker (fila whatsapp)
```

**Re-disparo de convite:** dispatch pula se já existe msg agent na conversation — use `bin/db-reset` ou encerre outra aula.

## Respostas do webhook

| `detail` | Significado |
|---|---|
| `ok` | Mensagem aceita; worker vai processar |
| `no_conversation` | Encerre a aula antes |
| `unknown_student` | Telefone não bate com `users.whatsapp` |
| `duplicate` | Mesmo `message_id` já recebido |
| `empty_message` | Texto vazio (áudio não transcrito?) |

## Teste end-to-end com WhatsApp real (inbound)

Se quiser testar **digitando/gravando no celular**:

1. Tunnel: `cloudflared tunnel --url http://localhost:8000`
2. Cadastrar URL na Cinndi: `POST https://<tunnel>/webhooks/cinndi`
3. Não precisa por a URL do tunnel no `.env`

Ver também: [whatsapp-template-certai_convite_aula.md](./whatsapp-template-certai_convite_aula.md)
