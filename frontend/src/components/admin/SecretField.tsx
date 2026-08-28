import { useEffect, useState } from "react";

interface Props {
  label: string;
  provider: string;
  configured: boolean;
  available: boolean;
  maskedValue: string;
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
  onTest: () => Promise<{ ok: boolean; message: string }>;
}

function IconKey() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="8" cy="15" r="4" stroke="currentColor" strokeWidth="1.5" />
      <path d="M11.5 12.5 20 4v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M16 5h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconZap() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function IconEye({ off }: { off?: boolean }) {
  return off ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 3l18 18" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M10.6 10.7a3 3 0 0 0 4.1 4.2M9.9 5.5A11 11 0 0 1 12 5c6 0 10 7 10 7a18 18 0 0 1-3.2 3.8M6.1 6.4A18 18 0 0 0 2 12s4 7 10 7c1.5 0 2.9-.3 4.2-.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function IconUndo() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M3 10h10a6 6 0 1 1 0 12H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M7 6 3 10l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconSpin() {
  return (
    <svg className="secret-field__spin" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M12 3a9 9 0 1 1-9 9" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

export function SecretField({
  label,
  provider,
  configured,
  available,
  maskedValue,
  value,
  onChange,
  onClear,
  onTest,
}: Props) {
  const [editing, setEditing] = useState(!configured);
  const [visible, setVisible] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  useEffect(() => {
    if (configured && !value.trim()) {
      setEditing(false);
      setVisible(false);
    }
  }, [configured, value]);

  function startEdit() {
    setEditing(true);
    setVisible(false);
    onChange("");
    setTestMessage(null);
    setTestError(null);
  }

  function cancelEdit() {
    setEditing(false);
    setVisible(false);
    onChange("");
    setTestMessage(null);
    setTestError(null);
  }

  async function handleTest() {
    setTesting(true);
    setTestMessage(null);
    setTestError(null);
    try {
      const result = await onTest();
      if (result.ok) setTestMessage(result.message);
      else setTestError(result.message);
    } catch (err) {
      setTestError(err instanceof Error ? err.message : "Não foi possível testar a chave.");
    } finally {
      setTesting(false);
    }
  }

  const canTest = configured || available || Boolean(value.trim());
  const showMasked = !editing && (configured || available);

  return (
    <div className="secret-field">
      <div className="secret-field__head">
        <span className="secret-field__label">{label}</span>
        <span className={`provider-pill provider-pill--${provider}`}>{provider}</span>
      </div>

      {showMasked ? (
        <div className="secret-field__masked">
          <div className="secret-field__masked-main">
            <span className="secret-field__icon" aria-hidden>
              <IconKey />
            </span>
            <code className="secret-field__value">
              {configured ? maskedValue : "Chave da plataforma"}
            </code>
          </div>
          <div className="secret-field__actions">
            <button type="button" className="secret-field__action" onClick={() => void handleTest()} disabled={testing || !canTest}>
              {testing ? <IconSpin /> : <IconZap />}
              {testing ? "Testando…" : "Testar chave"}
            </button>
            <button type="button" className="secret-field__action" onClick={startEdit}>
              Substituir
            </button>
            {configured && (
              <button type="button" className="secret-field__action secret-field__action--danger" onClick={onClear}>
                Remover
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="secret-field__edit">
          <div className="secret-field__input-wrap">
            <input
              className="input"
              type={visible ? "text" : "password"}
              autoComplete="off"
              placeholder={configured ? "Cole a nova chave" : "Informe para configurar"}
              value={value}
              onChange={(event) => {
                onChange(event.target.value);
                setTestMessage(null);
                setTestError(null);
              }}
            />
            <button
              type="button"
              className="secret-field__toggle"
              aria-label={visible ? "Ocultar chave" : "Mostrar chave"}
              onClick={() => setVisible((current) => !current)}
            >
              <IconEye off={visible} />
            </button>
          </div>
          <div className="secret-field__actions">
            <button type="button" className="secret-field__action" onClick={() => void handleTest()} disabled={testing || !canTest}>
              {testing ? <IconSpin /> : <IconZap />}
              {testing ? "Testando…" : "Testar chave"}
            </button>
            {(configured || available) && (
              <button type="button" className="secret-field__action" onClick={cancelEdit}>
                <IconUndo />
                Cancelar
              </button>
            )}
          </div>
        </div>
      )}

      {testMessage && <p className="secret-field__result secret-field__result--ok">{testMessage}</p>}
      {testError && <p className="secret-field__result secret-field__result--error">{testError}</p>}
    </div>
  );
}
