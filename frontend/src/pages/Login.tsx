import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { normalizedEmail } from "../lib/validation";

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
      await login(normalizedEmail(email), password);
      navigate("/");
    } catch {
      setError("E-mail ou senha incorretos. Tente novamente.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <aside className="login-hero" aria-label="CertAI">
        <span className="login-hero__brand">CertAI</span>
        <div className="login-hero__copy">
          <h1>Acompanhe o que a turma de fato aprendeu.</h1>
          <p>
            Trilhas, turmas e registro aula a aula, com evidência clara de absorção.
          </p>
        </div>
        <p className="login-hero__tagline">
          Trilhas, turmas e registro aula a aula.
        </p>
        <span className="login-hero__foot">certai.app</span>
      </aside>

      <main className="login-panel">
        <form className="login-form" onSubmit={onSubmit}>
          <div className="login-form__intro">
            <h2>Entrar</h2>
            <p className="muted">Use o e-mail e a senha fornecidos pela instituição.</p>
          </div>

          <div className="field">
            <label htmlFor="email">E-mail</label>
            <input
              id="email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="senha">Senha</label>
            <input
              id="senha"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error && <div className="login-form__error">{error}</div>}

          <button
            className="btn btn-primary login-form__submit"
            type="submit"
            disabled={busy}
          >
            {busy ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </main>
    </div>
  );
}
