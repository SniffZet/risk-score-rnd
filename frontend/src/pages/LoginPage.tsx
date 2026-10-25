import React, { useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Providers, User } from '../api/types';

export const LoginPage: React.FC<{ onLogin: (user: User) => void }> = ({ onLogin }) => {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [retryUntil, setRetryUntil] = useState(0);
  const [retrySeconds, setRetrySeconds] = useState(0);
  const [providers, setProviders] = useState<Providers | null>(null);

  useEffect(() => {
    api.providers().then(setProviders).catch(() => setProviders(null));
  }, []);

  useEffect(() => {
    if (!retryUntil) return;
    const update = () => {
      const remaining = Math.max(0, Math.ceil((retryUntil - Date.now()) / 1000));
      setRetrySeconds(remaining);
      if (!remaining) setRetryUntil(0);
    };
    update();
    const timer = window.setInterval(update, 250);
    return () => window.clearInterval(timer);
  }, [retryUntil]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || Date.now() < retryUntil) return;
    setBusy(true);
    setError(null);
    try {
      onLogin(await api.login(login, password));
    } catch (err) {
      if (err instanceof ApiError && err.status === 429 && err.retryAfter) {
        setRetrySeconds(Math.ceil(err.retryAfter));
        setRetryUntil(Date.now() + err.retryAfter * 1000);
      }
      setError(err instanceof ApiError && err.status === 401 ? 'Неверный логин или пароль' : (err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <div className="modal-content">
        <div className="modal-header">
          <span className="brand-mark" aria-hidden="true" />
          <h2>Вход в панель</h2>
          <div className="muted">Анализатор рисков оттока</div>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="login">Логин</label>
            <input id="login" type="text" autoFocus value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" required />
          </div>
          <div className="form-group">
            <label htmlFor="password">Пароль</label>
            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" className="submit-btn" disabled={busy || retrySeconds > 0}>
            {busy ? 'Входим…' : retrySeconds > 0 ? `Повторить через ${retrySeconds} с` : 'Войти'}
          </button>
        </form>
        {providers?.oidc && providers.oidcLoginUrl && (
          <div className="sso">
            <div className="muted">или</div>
            <a className="submit-btn sso-btn" href={providers.oidcLoginUrl}>Войти через {providers.oidcName ?? 'SSO'}</a>
          </div>
        )}
      </div>
    </div>
  );
};
