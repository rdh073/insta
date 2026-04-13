import { useEffect, useState } from 'react';
import { CheckCircle, Copy, Eye, EyeOff, Loader } from 'lucide-react';
import { accountsApi } from '../../../api/accounts';
import { Modal } from '../../../components/ui/Modal';

async function copyToClipboard(value: string): Promise<boolean> {
  // Modern API — only available in secure contexts (HTTPS/localhost)
  if (typeof navigator !== 'undefined' && navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // fall through to legacy path
    }
  }
  // Legacy fallback for plain-HTTP deployments
  try {
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    textarea.style.pointerEvents = 'none';
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, value.length);
    const ok = document.execCommand('copy');
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

function CredentialField({ label, value }: { label: string; value: string }) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const display = visible ? value : '•'.repeat(Math.min(value.length || 8, 24));

  async function handleCopy() {
    if (!value) return;
    const ok = await copyToClipboard(value);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[#5a6a90]">{label}</p>
      <div className="flex items-center gap-2 rounded-[0.9rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] px-3 py-2.5">
        <span className="flex-1 break-all font-mono text-sm text-[#c0caf5]">
          {value ? display : <span className="text-[#4a5578]">—</span>}
        </span>
        {value && (
          <>
            <button
              type="button"
              onClick={() => setVisible((v) => !v)}
              className="cursor-pointer shrink-0 text-[#5a6a90] transition-colors hover:text-[#c0caf5]"
              title={visible ? 'Hide' : 'Show'}
            >
              {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
            <button
              type="button"
              onClick={() => void handleCopy()}
              className="cursor-pointer shrink-0 text-[#5a6a90] transition-colors hover:text-[#7aa2f7]"
              title="Copy"
            >
              {copied ? <CheckCircle className="h-3.5 w-3.5 text-[#9ece6a]" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export function CredentialsModal({
  open,
  onClose,
  accountId,
  username,
}: {
  open: boolean;
  onClose: () => void;
  accountId: string;
  username: string;
}) {
  const [loading, setLoading] = useState(false);
  const [creds, setCreds] = useState<{ username: string; password: string; totpSecret: string } | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    accountsApi.getCredentials(accountId)
      .then(setCreds)
      .catch(() => setCreds(null))
      .finally(() => setLoading(false));
  }, [open, accountId]);

  function handleClose() {
    setCreds(null);
    onClose();
  }

  return (
    <Modal open={open} onClose={handleClose} title={`Credentials — @${username}`}>
      {loading ? (
        <div className="flex h-24 items-center justify-center">
          <Loader className="h-5 w-5 animate-spin text-[#7dcfff]" />
        </div>
      ) : creds ? (
        <div className="space-y-4">
          <CredentialField label="Username" value={creds.username} />
          <CredentialField label="Password" value={creds.password} />
          {creds.totpSecret && (
            <CredentialField label="TOTP Secret" value={creds.totpSecret} />
          )}
          <p className="rounded-[0.9rem] bg-[rgba(247,118,142,0.08)] px-3 py-2 text-[11px] text-[#f7768e]">
            Keep these credentials private. Do not share or expose them.
          </p>
        </div>
      ) : (
        <p className="text-sm text-[#f7768e]">Failed to load credentials.</p>
      )}
    </Modal>
  );
}
