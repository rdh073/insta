import { useState } from 'react';
import { Lock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { dashboardLogin } from '../api/dashboard-oauth';
import { useSettingsStore } from '../store/settings';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';

export function LoginPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setDashboardToken = useSettingsStore((s) => s.setDashboardToken);
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password) return;
    setError('');
    setLoading(true);
    try {
      const res = await dashboardLogin(password, backendUrl);
      setDashboardToken(res.token);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--tokyo-bg)]">
      <div className="glass-panel glass-panel-strong w-full max-w-sm rounded-[1.75rem] p-8">
        <div className="mb-6 flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--tokyo-violet)]/20">
            <Lock className="h-6 w-6 text-[var(--tokyo-violet)]" />
          </div>
          <h1 className="text-kicker text-lg text-[var(--tokyo-fg)]">InstaManager</h1>
          <p className="text-sm text-[var(--tokyo-comment)]">Enter the admin password to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            type="password"
            placeholder="Admin password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
          />

          {error && (
            <p className="text-xs text-[var(--tokyo-rose)]">{error}</p>
          )}

          <Button type="submit" loading={loading} disabled={!password}>
            Unlock
          </Button>
        </form>
      </div>
    </div>
  );
}
