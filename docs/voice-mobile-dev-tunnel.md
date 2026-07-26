# Teste mobile da página `/voz` (cloudflared + Vite)

Guia para abrir a chamada de voz no celular (iOS Safari) em dev local, expondo o frontend via `cloudflared tunnel`.

## Como o frontend alcança a API

A página `/voz` usa caminho **relativo** via **proxy do Vite** — o browser **não** chama `localhost:8000` diretamente.

- `frontend/src/lib/realtimeApi.ts` → `baseURL: "/api/v1/realtime"`
- `frontend/vite.config.ts` → proxy `/api` → `http://localhost:8000`

Fluxo no celular:

1. Página: `https://<tunnel>/voz/<token>`
2. API: `https://<tunnel>/api/v1/realtime/...` (mesma origem)
3. Vite (na máquina de dev) faz proxy → `http://localhost:8000`
4. WebRTC: browser → `https://api.openai.com` direto (fora do túnel)

## 1. Um túnel no 5173 basta?

**Sim.** Não precisa de segundo túnel para a API.

O celular só fala com o Vite; o Vite fala com a API em `localhost:8000` no PC.

**O que precisa estar rodando localmente:**

- Frontend Vite na porta 5173
- API na porta 8000 (`bin/dev` ou `uvicorn`)
- Postgres + Redis (validate, token, heartbeat)

## 2. `allowedHosts` no Vite

**Sim, precisa ajustar.** O `vite.config.ts` deve aceitar o host do cloudflared (`*.trycloudflare.com`). Sem isso, o Vite 6 costuma responder:

> Blocked request. This host is not allowed.

Exemplo em `frontend/vite.config.ts`:

```ts
server: {
  port: Number(process.env.FRONTEND_PORT || 5173),
  allowedHosts: true, // ou: [".trycloudflare.com"]
  proxy: {
    "/api": {
      target: `http://localhost:${process.env.API_PORT || 8000}`,
      changeOrigin: true,
    },
  },
},
```

Reinicie o `npm run dev` após a mudança.

## 3. Env / config necessários

| Variável | Mudar para o túnel? | Motivo |
|---|---|---|
| `CORS_ORIGINS` | **Não** | Com proxy, o browser vê mesma origem (`tunnel` → `tunnel/api`). |
| `FRONTEND_BASE_URL` | **Opcional** | Só afeta links gerados (`./bin/voice-link`, dispatch). Para teste manual, troque o host na URL. |
| `OPENAI_API_KEY` | **Sim, deve estar setada** | Sem isso, `POST /realtime/token` falha. |
| `ENV` | Manter `dev` | Em `prod`, `TrustedHostMiddleware` bloqueia hosts desconhecidos na API. |

`FRONTEND_BASE_URL` **não** impede a página de abrir se a URL for montada manualmente com o host do túnel.

## Checklist antes de abrir no celular

### 1. Subir stack local

```bash
cd certai-python
./bin/dev
# ou: API :8000 + frontend npm run dev :5173
```

### 2. Ajustar `vite.config.ts`

Adicionar `allowedHosts: true` (ou `[".trycloudflare.com"]`) e reiniciar o frontend.

### 3. Abrir túnel só no frontend

```bash
cloudflared tunnel --url http://localhost:5173
```

Copie a URL HTTPS, ex.: `https://abc-xyz.trycloudflare.com`

### 4. Gerar token de voz

```bash
./bin/voice-link
```

O script imprime algo como `http://localhost:5173/voz/<token>`.

### 5. Montar URL para o celular

Substitua o host:

```
https://abc-xyz.trycloudflare.com/voz/<token>
```

### 6. Smoke test no PC (antes do celular)

```bash
curl -s -X POST "https://abc-xyz.trycloudflare.com/api/v1/realtime/session/validate" \
  -H "Content-Type: application/json" \
  -d '{"handoff_token":"<token>"}'
```

Esperado: JSON com `student_first_name`, `lesson_title`, `whatsapp_support_url`, etc.

### 7. Abrir no iPhone (Safari)

Use a URL do passo 5. O HTTPS do cloudflared atende o requisito de contexto seguro para `getUserMedia` no mobile.

## O que não precisa configurar

- Segundo túnel na porta 8000
- `CORS_ORIGINS` com URL do cloudflared
- URL absoluta da API no frontend
- `FRONTEND_BASE_URL` (se a URL for montada manualmente)

## Notas

- O `Permissions-Policy: microphone=()` está no FastAPI (`main.py`), mas a página `/voz` é servida pelo **Vite** — não bloqueia microfone no teste mobile.
- Para teste de **inbound WhatsApp** (webhook Cinndi), o túnel vai na API (`:8000`), não no frontend. Ver [`whatsapp-dev-local.md`](./whatsapp-dev-local.md).
- Critérios da Etapa F (abandon 90s, iOS Safari): ver [`realtime_voice_channel_6e560811.plan.md`](./realtime_voice_channel_6e560811.plan.md).
