import { useEffect, useState } from 'react';
import { Lock, Mail, Phone, Shield, ShieldCheck, ShieldOff, Smartphone } from 'lucide-react';
import toast from 'react-hot-toast';
import { accountsApi } from '../../../api/accounts';
import { ApiError } from '../../../api/client';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Input } from '../../../components/ui/Input';
import { useAccountStore } from '../../../store/accounts';

interface Props {
  accountId: string;
}

function YesNo({ value }: { value: boolean | null | undefined }) {
  if (value === null || value === undefined) {
    return <span className="text-[#5a6a90]">unknown</span>;
  }
  if (value) {
    return <span className="text-[#9ece6a]">enabled</span>;
  }
  return <span className="text-[#f7768e]">disabled</span>;
}

export function AccountSecurityCard({ accountId }: Props) {
  const info = useAccountStore((s) => s.securityInfo[accountId]);
  const pending = useAccountStore((s) => s.pendingConfirmations[accountId]);
  const setSecurityInfo = useAccountStore((s) => s.setSecurityInfo);
  const clearSecurityInfo = useAccountStore((s) => s.clearSecurityInfo);
  const markPending = useAccountStore((s) => s.markPendingConfirmation);
  const clearPending = useAccountStore((s) => s.clearPendingConfirmation);

  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState(pending?.email ?? '');
  const [phone, setPhone] = useState(pending?.phone ?? '');
  const [sendingEmail, setSendingEmail] = useState(false);
  const [sendingPhone, setSendingPhone] = useState(false);

  // Reset inputs when switching account; seed from persisted pending state.
  useEffect(() => {
    setEmail(pending?.email ?? '');
    setPhone(pending?.phone ?? '');
  }, [accountId]); // intentional: ignore `pending` to avoid stomping edits

  const load = async (showError: boolean) => {
    setLoading(true);
    try {
      const next = await accountsApi.getAccountSecurityInfo(accountId);
      setSecurityInfo(accountId, next);
    } catch (err) {
      if (showError) {
        const message = (err as ApiError).message || 'Failed to load security info';
        toast.error(message);
      }
      clearSecurityInfo(accountId);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId]);

  const sendEmailConfirm = async () => {
    const trimmed = email.trim();
    if (!trimmed) {
      toast.error('Enter an email first');
      return;
    }
    setSendingEmail(true);
    try {
      const result = await accountsApi.requestEmailConfirm(accountId, trimmed);
      markPending(accountId, 'email', result.target);
      toast.success(
        result.sent
          ? `Code sent to ${result.target}`
          : 'Instagram accepted the request but did not confirm delivery',
      );
    } catch (err) {
      toast.error((err as ApiError).message || 'Failed to send email code');
    } finally {
      setSendingEmail(false);
    }
  };

  const sendPhoneConfirm = async () => {
    const trimmed = phone.trim();
    if (!trimmed) {
      toast.error('Enter a phone number first');
      return;
    }
    setSendingPhone(true);
    try {
      const result = await accountsApi.requestPhoneConfirm(accountId, trimmed);
      markPending(accountId, 'phone', result.target);
      toast.success(
        result.sent
          ? `Code sent to ${result.target}`
          : 'Instagram accepted the request but did not confirm delivery',
      );
    } catch (err) {
      toast.error((err as ApiError).message || 'Failed to send phone code');
    } finally {
      setSendingPhone(false);
    }
  };

  const hasAnyMethod =
    info?.totpTwoFactorEnabled || info?.smsTwoFactorEnabled || info?.whatsappTwoFactorEnabled;

  return (
    <Card className="space-y-5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[1rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(125,207,255,0.06)]">
            {info?.twoFactorEnabled ? (
              <ShieldCheck className="h-5 w-5 text-[#9ece6a]" />
            ) : info ? (
              <ShieldOff className="h-5 w-5 text-[#f7768e]" />
            ) : (
              <Shield className="h-5 w-5 text-[#7dcfff]" />
            )}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[#eef4ff]">Security posture</p>
            <p className="text-[11px] text-[#7f8bb3]">2FA, trusted devices, and contact confirmation</p>
          </div>
        </div>
        <Button size="sm" variant="secondary" loading={loading} onClick={() => void load(true)}>
          Refresh
        </Button>
      </div>

      {/* 2FA grid */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-[1rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5">
          <p className="text-[10px] uppercase tracking-wider text-[#5a6a90]">2FA overall</p>
          <p className="mt-1 font-medium"><YesNo value={info?.twoFactorEnabled ?? null} /></p>
        </div>
        <div className="rounded-[1rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5">
          <p className="text-[10px] uppercase tracking-wider text-[#5a6a90]">Authenticator (TOTP)</p>
          <p className="mt-1 font-medium"><YesNo value={info?.totpTwoFactorEnabled ?? null} /></p>
        </div>
        <div className="rounded-[1rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5">
          <p className="text-[10px] uppercase tracking-wider text-[#5a6a90]">SMS</p>
          <p className="mt-1 font-medium"><YesNo value={info?.smsTwoFactorEnabled ?? null} /></p>
        </div>
        <div className="rounded-[1rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5">
          <p className="text-[10px] uppercase tracking-wider text-[#5a6a90]">WhatsApp</p>
          <p className="mt-1 font-medium"><YesNo value={info?.whatsappTwoFactorEnabled ?? null} /></p>
        </div>
      </div>

      {/* Device & backup info */}
      <div className="flex flex-wrap gap-3 text-xs">
        <div className="flex items-center gap-2 rounded-[0.9rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2">
          <Smartphone className="h-3.5 w-3.5 text-[#7dcfff]" />
          <span className="text-[#9aa7cf]">
            Trusted devices:&nbsp;
            <span className="font-mono text-[#eef4ff]">
              {info?.trustedDevicesCount ?? '—'}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-2 rounded-[0.9rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2">
          <Lock className="h-3.5 w-3.5 text-[#7dcfff]" />
          <span className="text-[#9aa7cf]">
            Backup codes:&nbsp;<YesNo value={info?.backupCodesAvailable ?? null} />
          </span>
        </div>
        {info?.isPhoneConfirmed !== null && info?.isPhoneConfirmed !== undefined && (
          <div className="flex items-center gap-2 rounded-[0.9rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.03)] px-3 py-2">
            <Phone className="h-3.5 w-3.5 text-[#7dcfff]" />
            <span className="text-[#9aa7cf]">
              Phone confirmed:&nbsp;<YesNo value={info.isPhoneConfirmed} />
            </span>
          </div>
        )}
      </div>

      {hasAnyMethod === false && info && (
        <p className="rounded-[0.75rem] bg-[rgba(247,118,142,0.08)] px-3 py-2 text-xs text-[#ffbfd0]">
          No second factor is enabled. The account is one password leak away from takeover.
        </p>
      )}

      {/* Confirmation requests */}
      <div className="space-y-3 border-t border-[rgba(162,179,229,0.10)] pt-4">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[#5a6a90]">
          Contact confirmation
        </p>
        <p className="text-[11px] text-[#7f8bb3]">
          After editing the email or phone on the profile, Instagram requires a confirmation code. Trigger delivery here; submit the code on Instagram until the second-step wiring ships.
        </p>

        {/* Email row */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-[11px] text-[#9aa7cf]">
            <Mail className="h-3.5 w-3.5" />
            <span>New email</span>
            {pending?.email && (
              <span className="ml-auto rounded-[0.5rem] bg-[rgba(224,175,104,0.12)] px-2 py-0.5 font-mono text-[10px] text-[#e0af68]">
                pending: {pending.email}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="new@example.com"
              className="flex-1"
            />
            <Button size="sm" onClick={sendEmailConfirm} loading={sendingEmail}>
              Send code
            </Button>
            {pending?.email && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => clearPending(accountId, 'email')}
              >
                Clear
              </Button>
            )}
          </div>
        </div>

        {/* Phone row */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-[11px] text-[#9aa7cf]">
            <Phone className="h-3.5 w-3.5" />
            <span>New phone</span>
            {pending?.phone && (
              <span className="ml-auto rounded-[0.5rem] bg-[rgba(224,175,104,0.12)] px-2 py-0.5 font-mono text-[10px] text-[#e0af68]">
                pending: {pending.phone}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+15551234567"
              className="flex-1"
            />
            <Button size="sm" onClick={sendPhoneConfirm} loading={sendingPhone}>
              Send code
            </Button>
            {pending?.phone && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => clearPending(accountId, 'phone')}
              >
                Clear
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
