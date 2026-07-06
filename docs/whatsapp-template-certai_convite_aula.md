# Template WhatsApp — certai_convite_aula

Template de convite enviado após o professor encerrar a aula. Crie na Cinndi/Meta **antes** de testar o disparo.

## Texto (pt_BR, 4 variáveis, sem botões)

```
Oi {{1}}! 👋 Aqui é a {{4}}, sua parceira de estudos no CertAI.
Quero conversar com você sobre a aula "{{2}}" da trilha "{{3}}".
Bora um papo rápido pra fixar o conteúdo? Pode me responder por aqui, texto ou áudio. 🙂
```

| Variável | Conteúdo |
|---|---|
| `{{1}}` | Primeiro nome do aluno |
| `{{2}}` | Título da aula encerrada |
| `{{3}}` | Título da trilha |
| `{{4}}` | Nome da assistente (`ASSISTANT_NAME`, padrão: Lira) |

## curl (Cinndi)

Substitua `NUMERO`, `TOKEN` e `BEARER_TOKEN`:

- `NUMERO` = `CINNDI_SENDER_PHONE` (ex.: `5519982863180`)
- `TOKEN` = `CINNDI_API_KEY` (vai no path da URL)
- `BEARER_TOKEN` = JWT do painel Cinndi (**obrigatório** neste endpoint)

> **401 "Autorização inválida"?** O `novo-template` **não** basta com a key no path.
> Diferente de `enviar-template` / `enviar-mensagem-texto`, aqui a Cinndi exige também
> `Authorization: Bearer <JWT>` **ou** Basic Auth (`email:senha` da conta Cinndi).
> Pegue o Bearer no painel Cinndi (mesmo fluxo do `cert-ai/docs/template-inicial-curl.md`).

```bash
curl -X POST "https://api.cinndi.com/v2/novo-template/NUMERO/TOKEN" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer BEARER_TOKEN" \
  --data-raw '{
    "nome": "certai_convite_aula",
    "idioma": "pt_BR",
    "tipo": "MARKETING",
    "mensagem": "Oi {{1}}! 👋 Aqui é a {{4}}, sua parceira de estudos no CertAI.\nQuero conversar com você sobre a aula \"{{2}}\" da trilha \"{{3}}\".\nBora um papo rápido pra fixar o conteúdo? Pode me responder por aqui, texto ou áudio. 🙂"
  }'
```

Alternativa com Basic Auth (e-mail e senha da conta Cinndi):

```bash
curl -X POST "https://api.cinndi.com/v2/novo-template/NUMERO/TOKEN" \
  -H "Content-Type: application/json" \
  -u "seu-email@cinndi.com:sua-senha" \
  --data-raw '{ ... mesmo body ... }'
```

## ENV relacionadas

```
WHATSAPP_INVITE_TEMPLATE=certai_convite_aula
WHATSAPP_TEMPLATE_LANG=pt_BR
ASSISTANT_NAME=Lira
```

## Webhook inbound

Configure na Cinndi o endpoint público:

```
POST https://<seu-dominio>/webhooks/cinndi
```

Opcional: defina `CINNDI_WEBHOOK_TOKEN` e envie no header `X-Webhook-Token` ou `X-Cinndi-Token`.
