import { type FormEvent, useEffect, useState } from "react";
import type { OrgSettings, SettingsCatalog } from "../../lib/admin";
import { MODEL_SELECTS, SECRET_FIELDS } from "../../lib/admin";
import { api, apiErrorMessage } from "../../lib/api";
import { useApiAction } from "../../lib/useApiAction";
import { ModelSelect } from "./ModelSelect";
import { SecretField } from "./SecretField";

interface Props {
  settings: OrgSettings;
  settingsPath: string;
  onSaved: (settings: OrgSettings) => void;
}

export function IntegrationsForm({ settings, settingsPath, onSaved }: Props) {
  const runAction = useApiAction();
  const [catalog, setCatalog] = useState<SettingsCatalog | null>(null);
  const [models, setModels] = useState<Record<string, string>>({});
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [clearSecrets, setClearSecrets] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get<SettingsCatalog>("/settings/catalog")
      .then(({ data }) => setCatalog(data))
      .catch(() => setCatalog(null));
  }, []);

  useEffect(() => {
    const next: Record<string, string> = {};
    for (const field of MODEL_SELECTS) {
      next[field.key] = String(settings[field.key] ?? "");
    }
    setModels(next);
    setSecrets({});
    setClearSecrets(new Set());
  }, [settings]);

  async function testCredential(field: (typeof SECRET_FIELDS)[number]["key"]) {
    try {
      const { data } = await api.post<{ ok: boolean; message: string }>(`${settingsPath}/test-credential`, {
        field,
        value: secrets[field]?.trim() || undefined,
      });
      return { ok: true, message: data.message };
    } catch (err) {
      return { ok: false, message: apiErrorMessage(err, "Não foi possível testar a chave.") };
    }
  }

  function handleSecretChange(key: string, value: string) {
    setSecrets((current) => ({ ...current, [key]: value }));
    if (value.trim()) {
      setClearSecrets((current) => {
        const next = new Set(current);
        next.delete(key);
        return next;
      });
    }
  }

  function handleSecretClear(key: string) {
    setSecrets((current) => ({ ...current, [key]: "" }));
    setClearSecrets((current) => new Set(current).add(key));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    const payload: Record<string, unknown> = { ...models };
    for (const field of SECRET_FIELDS) {
      const value = (secrets[field.key] || "").trim();
      if (value) payload[field.key] = value;
    }
    if (clearSecrets.size) payload.clear_secrets = [...clearSecrets];
    await runAction({
      run: () => api.patch<OrgSettings>(settingsPath, payload),
      successMessage: "Configurações salvas.",
      errorMessage: "Não foi possível salvar as configurações.",
      onSuccess: ({ data }) => onSaved(data),
    });
    setSaving(false);
  }

  return (
    <form className="integrations-form" onSubmit={onSubmit}>
      <p className="muted" style={{ margin: 0 }}>
        Sem override, vale o ambiente da plataforma. Salvar o padrão não grava cópia na org.
      </p>

      <section className="settings-section">
        <div className="settings-section-head">
          <h3>Modelos</h3>
          <span className="muted">OpenAI para texto, Groq Whisper para transcrição, Realtime para voz ao vivo. O valor marcado como padrão é o da plataforma.</span>
        </div>
        {catalog ? (
          <div className="settings-grid">
            {MODEL_SELECTS.map((field) => (
              <ModelSelect
                key={field.key}
                label={field.label}
                icon={field.icon}
                value={models[field.key] ?? ""}
                options={catalog[field.catalog]}
                platformDefault={catalog.defaults[field.key]}
                onChange={(value) => setModels((current) => ({ ...current, [field.key]: value }))}
              />
            ))}
          </div>
        ) : (
          <p className="muted">Carregando modelos…</p>
        )}
      </section>

      <section className="settings-section">
        <div className="settings-section-head">
          <h3>Chaves de API</h3>
          <span className="muted">Criptografadas na org. Em branco, usa a chave da plataforma. Teste consulta o provedor sem salvar.</span>
        </div>
        <div className="settings-grid settings-grid--2">
          {SECRET_FIELDS.map((field) => (
            <SecretField
              key={field.key}
              label={field.label}
              provider={field.provider}
              configured={Boolean(settings.configured[field.key]) && !clearSecrets.has(field.key)}
              available={Boolean(settings.available?.[field.key])}
              maskedValue={settings.masked_secrets[field.key] ?? ""}
              value={secrets[field.key] ?? ""}
              onChange={(value) => handleSecretChange(field.key, value)}
              onClear={() => handleSecretClear(field.key)}
              onTest={() => testCredential(field.key)}
            />
          ))}
        </div>
      </section>

      <button type="submit" className="btn btn-primary integrations-form__save" disabled={saving || !catalog}>
        {saving ? "Salvando…" : "Salvar configurações"}
      </button>
    </form>
  );
}
