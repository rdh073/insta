import { useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Modal } from '../../../components/ui/Modal';

export function BulkProxyModal({
  open,
  onClose,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (proxy: string) => void;
}) {
  const [proxy, setProxy] = useState('');

  return (
    <Modal open={open} onClose={onClose} title="Set Proxy for Selected">
      <div className="space-y-4">
        <Input
          id="bulk-proxy-url"
          name="proxy_url"
          label="Proxy URL"
          value={proxy}
          onChange={(event) => setProxy(event.target.value)}
          placeholder="http://user:pass@host:port or socks5://host:port"
          autoFocus
        />
        <div className="flex gap-3">
          <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button className="flex-1" onClick={() => { onConfirm(proxy); onClose(); }} disabled={!proxy.trim()}>
            Apply
          </Button>
        </div>
      </div>
    </Modal>
  );
}
