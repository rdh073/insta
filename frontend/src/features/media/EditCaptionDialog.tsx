import { useEffect, useState } from 'react';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';

const MAX_CAPTION_LEN = 2200;

interface Props {
  open: boolean;
  initialCaption: string;
  saving: boolean;
  onClose: () => void;
  onSave: (caption: string) => void;
}

export function EditCaptionDialog({ open, initialCaption, saving, onClose, onSave }: Props) {
  const [draft, setDraft] = useState(initialCaption);

  useEffect(() => {
    if (open) setDraft(initialCaption);
  }, [open, initialCaption]);

  const remaining = MAX_CAPTION_LEN - draft.length;
  const overLimit = remaining < 0;
  const dirty = draft !== initialCaption;

  return (
    <Modal open={open} onClose={onClose} title="Edit caption">
      <div className="space-y-4">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Write a new caption…"
          rows={6}
          autoFocus
          className="glass-textarea w-full resize-none text-sm leading-6"
        />
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-[#6a7aa0]">
            Updates the published post caption only — usertags, location, and media remain unchanged.
          </span>
          <span className={overLimit ? 'text-[#f7768e]' : 'text-[#6a7aa0]'}>
            {remaining}
          </span>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            size="sm"
            loading={saving}
            disabled={!dirty || overLimit}
            onClick={() => onSave(draft)}
          >
            Save caption
          </Button>
        </div>
      </div>
    </Modal>
  );
}
