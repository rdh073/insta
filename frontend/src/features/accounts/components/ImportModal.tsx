import { useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { Upload } from 'lucide-react';
import { accountsApi } from '../../../api/accounts';
import { Button } from '../../../components/ui/Button';
import { Modal } from '../../../components/ui/Modal';
import { useAccountStore } from '../../../store/accounts';

export function ImportModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fileName, setFileName] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const upsertAccount = useAccountStore((s) => s.upsertAccount);

  const loadFileText = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setText(content);
      setFileName(file.name);
      setError('');
    };
    reader.readAsText(file);
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) loadFileText(file);
    event.target.value = '';
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files[0];
    if (file) loadFileText(file);
  };

  const handleImport = async () => {
    setError('');
    const lines = text.trim().split('\n').filter((line) => line.includes(':'));
    if (!lines.length) {
      setError('No valid lines found. Format: username:password');
      return;
    }

    setLoading(true);
    try {
      const importedAccounts = await accountsApi.importFile(text.trim());
      importedAccounts.forEach((account) => upsertAccount(account));
      toast.success(`Imported ${importedAccounts.length} account(s)`);
      setText('');
      setFileName('');
      onClose();
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setText('');
    setFileName('');
    setError('');
    onClose();
  };

  return (
    <Modal open={open} onClose={handleClose} title="Import Accounts">
      <div className="space-y-4">
        <p className="text-sm text-[#8e9ac0]">
          One account per line: <code className="rounded bg-[rgba(125,207,255,0.12)] px-1.5 py-0.5 text-[#d2f3ff]">username:password[:proxy][|totp_secret]</code>
        </p>

        {/* File drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex cursor-pointer flex-col items-center gap-2 rounded-[1.25rem] border px-4 py-5 text-center transition-all duration-200 ${
            dragOver
              ? 'border-[rgba(125,207,255,0.4)] bg-[rgba(125,207,255,0.12)]'
              : 'border-dashed border-[rgba(162,179,229,0.2)] bg-[rgba(255,255,255,0.03)] hover:border-[rgba(125,207,255,0.3)] hover:bg-[rgba(255,255,255,0.05)]'
          }`}
        >
          <Upload className={`h-5 w-5 ${dragOver ? 'text-[#7dcfff]' : 'text-[#5a6a90]'}`} />
          {fileName ? (
            <p className="text-sm font-medium text-[#9ece6a]">{fileName}</p>
          ) : (
            <p className="text-sm text-[#7f8bb3]">Drop a .txt / .csv file here, or click to browse</p>
          )}
          <input
            id="import-accounts-file"
            name="accounts_file"
            ref={fileInputRef}
            type="file"
            accept=".txt,.csv,text/plain,text/csv"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-[rgba(162,179,229,0.12)]" />
          <span className="text-[11px] text-[#4a5578]">or paste below</span>
          <div className="h-px flex-1 bg-[rgba(162,179,229,0.12)]" />
        </div>

        <textarea
          id="import-accounts-list"
          name="accounts_list"
          value={text}
          onChange={(event) => { setText(event.target.value); setFileName(''); }}
          placeholder={"user1:pass1\nuser2:pass2:http://proxy:3128\nuser3:pass3|BASE32TOTPSECRET"}
          rows={6}
          className="glass-textarea font-mono text-sm"
          aria-label="Accounts list"
        />

        {error && <p className="text-sm text-[#ff9db0]">{error}</p>}

        <div className="flex gap-3">
          <Button type="button" variant="secondary" className="flex-1" onClick={handleClose}>
            Cancel
          </Button>
          <Button className="flex-1" loading={loading} onClick={handleImport} disabled={!text.trim()}>
            <Upload className="h-4 w-4" />
            Import
          </Button>
        </div>
      </div>
    </Modal>
  );
}
