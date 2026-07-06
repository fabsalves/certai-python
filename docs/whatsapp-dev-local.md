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

## O que você precisa vs o que pode pular

| Etapa | Tunnel Cloudflare | Celular (inbound) | Cinndi API |
|---|---|---|---|
| Encerrar aula (convite) | Não | Recebe 1 msg | Sim |
| Simular texto/áudio do aluno | **Não** | **Não** | Não |
| Resposta da Lira | Não | Recebe no WhatsApp | Sim |

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

Áudios de exemplo ficam em `fixtures/audio/` (no repo: `audio-teste.ogg`; no sam: `nota-2.ogg`, `sua-nota.ogg`).

## Fluxo completo sugerido

```
1. bin/dev
2. Login professor → encerrar aula da turma seed
3. ./bin/send-message '...'     # ou: ./bin/send-audio fixtures/audio/audio-teste.ogg
4. Aguardar ~5s (debounce) + tempo da IA
5. Conferir resposta no WhatsApp real do aluno
6. Logs no terminal do worker (fila whatsapp)
```

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
