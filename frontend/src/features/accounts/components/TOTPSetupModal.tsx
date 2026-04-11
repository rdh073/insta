import { useState } from 'react';
import toast from 'react-hot-toast';
import { accountsApi } from '../../../api/accounts';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Modal } from '../../../components/ui/Modal';
import { useAccountStore } from '../../../store/accounts';

export function TOTPSetupModal({
  open,
  onClose,
  accountId,
}: {
  open: boolean;
  onClose: () => void;
  accountId?: string;
}) {
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState('');
  const [secret, setSecret] = useState('');
  const [qrUri, setQrUri] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [step, setStep] = useState<'setup' | 'verify'>('setup');
  const patchAccount = useAccountStore((s) => s.patchAccount);

  const handleGenerateSecret = async () => {
    if (!accountId) return;
    setLoading(true);
    setError('');
    try {
      const result = await accountsApi.setupTotp(accountId);
      setSecret(result.secret);
      setQrUri(result.provisioning_uri);
      setStep('verify');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyTotp = async () => {
    if (!accountId || !verificationCode.trim()) {
      setError('Verification code is required');
      return;
    }

    setVerifying(true);
    setError('');
    try {
      await accountsApi.verifyTotp(accountId, secret, verificationCode.trim());
      patchAccount(accountId, { totpEnabled: true });
      toast.success('TOTP enabled successfully');
      handleClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setVerifying(false);
    }
  };

  const handleClose = () => {
    setSecret('');
    setQrUri('');
    setVerificationCode('');
    setError('');
    setStep('setup');
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Setup 2FA with TOTP">
      {step === 'setup' ? (
        <div className="space-y-4">
          <p className="text-sm text-[#8e9ac0]">
            Generate a TOTP secret, scan the QR code in your authenticator, then verify the first code to enable 2FA.
          </p>
          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          <div className="flex gap-3">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleClose}>
              Cancel
            </Button>
            <Button className="flex-1" loading={loading} onClick={handleGenerateSecret}>
              Generate TOTP Secret
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col items-center rounded-[1.35rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-4 py-5">
            <p className="text-sm text-[#8e9ac0]">Scan with an authenticator app</p>
            {qrUri && (
              <div className="mt-4 rounded-[1.2rem] bg-white p-3">
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(qrUri)}`}
                  alt="QR code for TOTP setup"
                  className="h-40 w-40"
                />
              </div>
            )}
            <p className="mt-4 text-xs text-[#8e9ac0]">Manual secret</p>
            <p className="mt-2 rounded-[1rem] bg-[rgba(125,207,255,0.12)] px-3 py-2 font-mono text-sm text-[#d2f3ff]">{secret}</p>
          </div>

          <Input
            label="Verification Code"
            value={verificationCode}
            onChange={(event) => setVerificationCode(event.target.value)}
            placeholder="000000"
            maxLength={6}
          />

          {error && <p className="text-sm text-[#ff9db0]">{error}</p>}
          <div className="flex gap-3">
            <Button type="button" variant="secondary" className="flex-1" onClick={handleClose}>
              Cancel
            </Button>
            <Button className="flex-1" loading={verifying} onClick={handleVerifyTotp}>
              Verify &amp; Enable
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
