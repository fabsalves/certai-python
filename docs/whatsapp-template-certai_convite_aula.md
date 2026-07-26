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

- `NUMERO` = `CINNDI_SENDER_PHONE` (ex.: `5511999999999`)
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

---

## Variante voz — certai_convite_aula_voz_v2 (recomendado)

Template com botão URL (CTA) para chamada de voz em tempo real. **Use este** em produção após aprovação Meta.

### Erro do v1 (`certai_convite_aula_voz`)

O v1 foi criado com `botoesURL.url` terminando em `/voz/`. A Cinndi/Meta registrou:

`https://app.certai.com.br/voz//{{1}}`

No envio, a URL final fica `/voz//{token}` — **não casa** com a rota frontend `/voz/:token` e o app redireciona para login. O v1 permanece APPROVED como fallback legado; **não use** em `WHATSAPP_INVITE_VOICE_TEMPLATE` se puder evitar.

**Correção no v2:** prefixo **sem** barra final → `https://app.certai.com.br/voz` → Meta registra `https://app.certai.com.br/voz/{{1}}` → example `https://app.certai.com.br/voz/joao123`.

### Texto (pt_BR, 4 variáveis no corpo + botão URL dinâmico)

```
Oi {{1}}! 👋 Aqui é a {{4}}, sua parceira de estudos no CertAI.
Quero conversar com você sobre a aula "{{2}}" da trilha "{{3}}".

🎙️ Prefere falar comigo ao vivo? Toque no botão abaixo.
Ou responda por aqui, texto ou áudio, como preferir. 🙂
```

| Variável (corpo) | Conteúdo |
|---|---|
| `{{1}}` | Primeiro nome do aluno |
| `{{2}}` | Título da aula encerrada |
| `{{3}}` | Título da trilha |
| `{{4}}` | Nome da assistente (`ASSISTANT_NAME`, padrão: Lira) |

### Botão URL (CTA)

Formato Cinndi ([`doc-template-cinndi.md`](./doc-template-cinndi.md) — Variante 4):

| Campo | Valor |
|---|---|
| `botoesURL.texto` | `Falar com a Lira` |
| `botoesURL.url` | `https://app.certai.com.br/voz` (prefixo, **sem** barra final) |
| `botoesURL.dinamico` | `true` |

No disparo (`enviar-template`), o backend envia o handoff token JWT no campo **`buttons`** (string, sufixo). URL final: `https://app.certai.com.br/voz/{token}`.

### curl (Cinndi) — submissão do v2

Use **`--data-raw '...'`** (aspas simples) e URL https **literal**, **sem** `/` no fim de `/voz`.

```bash
curl -X POST "https://api.cinndi.com/v2/novo-template/NUMERO/TOKEN" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer BEARER_TOKEN" \
  --data-raw '{
    "nome": "certai_convite_aula_voz_v2",
    "idioma": "pt_BR",
    "tipo": "MARKETING",
    "mensagem": "Oi {{1}}! 👋 Aqui é a {{4}}, sua parceira de estudos no CertAI.\nQuero conversar com você sobre a aula \"{{2}}\" da trilha \"{{3}}\".\n\n🎙️ Prefere falar comigo ao vivo? Toque no botão abaixo.\nOu responda por aqui, texto ou áudio, como preferir. 🙂",
    "botoesURL": {
      "texto": "Falar com a Lira",
      "url": "https://app.certai.com.br/voz",
      "dinamico": true
    }
  }'
```

Após `APPROVED`, no `.env`:

```
WHATSAPP_INVITE_VOICE_TEMPLATE=certai_convite_aula_voz_v2
```

---

## Variante voz — certai_convite_aula_voz (v1, legado)

**Deprecated** — barra dupla na URL do botão. Mantido apenas como fallback aprovado. Ver seção v2 acima.

<details>
<summary>Detalhes v1 (não usar em produção)</summary>

Enquanto v2 não aprovado, `WHATSAPP_INVITE_USE_VOICE_TEMPLATE=false` continua com `certai_convite_aula` (sem CTA de voz).

O v1 usava `"url": "https://app.certai.com.br/voz/"` (com barra final) → Meta registrou `.../voz//{{1}}`.

</details>

---

## ENV relacionadas

```
WHATSAPP_INVITE_TEMPLATE=certai_convite_aula
WHATSAPP_INVITE_VOICE_TEMPLATE=certai_convite_aula_voz_v2
WHATSAPP_INVITE_USE_VOICE_TEMPLATE=true
WHATSAPP_TEMPLATE_LANG=pt_BR
ASSISTANT_NAME=Lira
FRONTEND_BASE_URL=https://app.certai.com.br
VOICE_HANDOFF_EXPIRE_HOURS=48
```

Enquanto v2 estiver PENDING, use `WHATSAPP_INVITE_USE_VOICE_TEMPLATE=false` ou temporariamente `certai_convite_aula_voz` (v1 legado — URL com barra dupla).

Templates Cinndi (formato API): [`doc-template-cinndi.md`](./doc-template-cinndi.md).

## Webhook inbound

Configure na Cinndi o endpoint público:

```
POST https://<seu-dominio>/webhooks/cinndi
```

Opcional: defina `CINNDI_WEBHOOK_TOKEN` e envie no header `X-Webhook-Token` ou `X-Cinndi-Token`.
