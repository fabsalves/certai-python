import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch {
      setError("E-mail ou senha incorretos. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", minHeight: "100%" }}>
      <div
        style={{
          background: "var(--ink)",
          color: "var(--on-brand)",
          padding: "64px 56px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <span style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 600, color: "#fff" }}>
          CertAI
        </span>
        <div>
          <h1 style={{ color: "#fff", fontSize: 38, lineHeight: 1.2, maxWidth: 420 }}>
            Acompanhe o que a turma de fato aprendeu.
          </h1>
          <p style={{ color: "rgba(243,247,246,0.72)", maxWidth: 420, marginTop: 16 }}>
            Trilhas, turmas e registro aula a aula — com evidência clara de absorção.
          </p>
        </div>
        <span style={{ fontSize: 13, color: "rgba(243,247,246,0.45)" }}>
          certai.app
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 48 }}>
        <form onSubmit={onSubmit} style={{ width: "100%", maxWidth: 360, display: "flex", flexDirection: "column", gap: 18 }}>
          <div>
            <h2>Entrar</h2>
            <p className="muted" style={{ marginTop: 4 }}>Use o e-mail e a senha fornecidos pela instituição.</p>
          </div>

          <div className="field">
            <label htmlFor="email">E-mail</label>
            <input id="email" className="input" type="email" value={email}
                   onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </div>

          <div className="field">
            <label htmlFor="senha">Senha</label>
            <input id="senha" className="input" type="password" value={password}
                   onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </div>

          {error && (
            <div style={{ color: "var(--danger)", background: "var(--danger-50)", padding: "8px 12px", borderRadius: 6, fontSize: 14 }}>
              {error}
            </div>
          )}

          <button className="btn btn-primary" type="submit" disabled={busy} style={{ justifyContent: "center" }}>
            {busy ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
