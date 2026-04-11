import { AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { Badge } from '../../../components/ui/Badge';
import { formatRelativeTime } from './account-helpers';
import type { Account } from '../../../types';

export function statusBadge(account: Account, compact = false) {
  const { status, lastVerifiedAt } = account;
  const verifiedAgo = formatRelativeTime(lastVerifiedAt);

  switch (status) {
    case 'active':
      return (
        <Badge variant="green" title={lastVerifiedAt ? `Last verified: ${new Date(lastVerifiedAt).toLocaleString()}` : 'Not verified yet'}>
          <CheckCircle className="h-3 w-3" />
          {compact ? (verifiedAgo ?? 'Active') : (verifiedAgo ? `Verified ${verifiedAgo}` : 'Active')}
        </Badge>
      );
    case 'logging_in':
      return <Badge variant="blue"><Loader className="h-3 w-3 animate-spin" />{compact ? 'Login...' : 'Logging in'}</Badge>;
    case 'error':
      return <Badge variant="red"><AlertCircle className="h-3 w-3" />Error</Badge>;
    case 'challenge':
      return <Badge variant="yellow"><AlertCircle className="h-3 w-3" />Challenge</Badge>;
    case '2fa_required':
      return <Badge variant="yellow"><AlertCircle className="h-3 w-3" />2FA</Badge>;
    default:
      return (
        <Badge variant="gray" title={verifiedAgo ? `Last verified: ${verifiedAgo}` : 'Never verified'}>
          {verifiedAgo ? `Idle (${verifiedAgo})` : 'Idle'}
        </Badge>
      );
  }
}
