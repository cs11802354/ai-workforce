import { useState } from "react";
import { api, auth } from "../api/client";
import { IconArrowUp } from "../components/Icon";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password || busy) return;
    setBusy(true);
    setError(null);
    try {
      const { token } = await api.login(password);
      auth.set(token);
      onSuccess();
    } catch {
      // Deliberately vague — don't confirm whether a guess was close.
      setError("Incorrect password.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <div className="brand-mark">M</div>
          <div className="brand-text">
            <span className="brand-name">MK Labs</span>
            <span className="brand-sub">Agent platform</span>
          </div>
        </div>

        <p className="login-hint">This workspace is private. Enter the password to continue.</p>

        <div className="login-field">
          <input
            className={"input" + (error ? " invalid" : "")}
            type="password"
            autoFocus
            autoComplete="current-password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-label="Password"
            aria-invalid={Boolean(error)}
          />
          <button
            type="submit"
            className="hero-search-submit"
            disabled={!password || busy}
            aria-label="Sign in"
          >
            <IconArrowUp size={16} />
          </button>
        </div>

        {error && <p className="field-error">{error}</p>}
      </form>
    </div>
  );
}
