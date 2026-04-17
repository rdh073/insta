import { useState } from 'react';
import toast from 'react-hot-toast';
import { accountsApi } from '../../../api/accounts';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Modal } from '../../../components/ui/Modal';
import { useAccountStore } from '../../../store/accounts';

export function AddAccountModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [proxy, setProxy] = useState('');
  const [totpSecret, setTotpSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState<'credentials' | '2fa'>('credentials');
  const [pendingAccountId, setPendingAccountId] = useState<string | null>(null);
  const [twoFACode, setTwoFACode] = useState('');
  const upsertAccount = useAccountStore((s) => s.upsertAccount);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError('Username and password are required');
      return;
    }

    setLoading(true);
    try {
      const cleanTotpSecret = totpSecret.trim().replace(/\s+/g, '') || undefined;
      const account = await accountsApi.login(username.trim(), password.trim(), proxy.trim() || undefined, cleanTotpSecret);
      if (account.status === '2fa_required') {
        setPendingAccountId(account.id);
        setStep('2fa');
        setLoading(false);
        return;
      }
      upsertAccount(account);
      toast.success(`@${account.username} logged in`);
      setUsername('');
      setPassword('');
      setProxy('');
      setTotpSecret('');
      setLoading(false);
      onClose();
    } catch (error) {
      setError((error as Error).message);
      setLoading(false);
    }
  };

  const handle2FASubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!twoFACode.trim()) {
      setError('2FA code is required');
      return;
    }

    setLoading(true);
    try {
      const account = await accountsApi.verify2fa(pendingAccountId!, twoFACode.trim(), false);
      upsertAccount(account);
      toast.success(`@${account.username} logged in`);
      setUsername('');
      setPassword('');
      setProxy('');
      setStep('credentials');
      setPendingAccountId(null);
      setTwoFACode('');
      onClose();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleModalClose = () => {
    setStep('credentials');
    setPendingAccountId(null);
    setTwoFACode('');
    setError('');
    setTotpSecret('');
    setLoading(false);
    onClose();
  };

  return (
    <Modal open={open} onClose={handleModalClose} title={step === 'credentials' ? 'Add Account' : 'Enter 2FA Code'}>
      {step === 'credentials' ? (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input id="add-account-username" name="username" autoComplete="username" label="Username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="your_instagram" autoFocus />
          <Input id="add-account-password" name="password" autoComplete="new-password" label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" />
          <Input
            id="add-account-totp-secret"
            name="totp_secret"
            label="2FA Secret / TOTP"
            value={totpSecret}
            onChange={(event) => setTotpSecret(event.target.value)}
            placeholder="2OWR 5YTV ZHAN 66UJ YOCT RZC2 7DCS WTDQ"
            hint="Optional base32 TOTP secret. Spaces are removed automatically."
          />
          <Input id="add-account-proxy" name="proxy" label="Proxy" value={proxy} onChange={(event) => setProxy(event.target.value)} placeholder="http://user:pass@host:port" hint="Optional. Leave empty to use direct connection." />
          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          {loading && <p className="text-xs text-[#8e9ac0]">Connecting to Instagram — this can take up to 30 seconds…</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleModalClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" loading={loading}>
              {loading ? 'Logging in…' : 'Login'}
            </Button>
          </div>
        </form>
      ) : (
        <form onSubmit={handle2FASubmit} className="space-y-4">
          <p className="text-sm text-[#8e9ac0]">Enter the 6-digit code from your authenticator app or SMS.</p>
          <Input
            id="add-account-2fa-code"
            name="two_factor_code"
            autoComplete="one-time-code"
            inputMode="numeric"
            label="2FA Code"
            value={twoFACode}
            onChange={(event) => setTwoFACode(event.target.value)}
            placeholder="000000"
            autoFocus
            maxLength={6}
          />
          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          <div className="flex gap-3 pt-1">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleModalClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" loading={loading}>
              {loading ? 'Verifying…' : 'Verify'}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
