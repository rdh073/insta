import { useEffect, useState } from 'react';
import { FileText, Hash, Pencil, Plus, Sparkles, Trash2 } from 'lucide-react';
import { HashtagTextarea } from '../components/instagram/HashtagTextarea';
import toast from 'react-hot-toast';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { useTemplateStore } from '../store/templates';
import type { CaptionTemplate } from '../types';

function TemplateModal({
  onClose,
  initial,
}: {
  onClose: () => void;
  initial?: CaptionTemplate;
}) {
  const addTemplate = useTemplateStore((s) => s.addTemplate);
  const updateTemplate = useTemplateStore((s) => s.updateTemplate);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState(initial?.name ?? '');
  const [caption, setCaption] = useState(initial?.caption ?? '');
  const [tagsRaw, setTagsRaw] = useState(initial?.tags.join(', ') ?? '');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !caption.trim()) {
      toast.error('Name and caption are required');
      return;
    }

    const tags = tagsRaw
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);

    setSaving(true);
    try {
      if (initial) {
        await updateTemplate(initial.id, { name: name.trim(), caption: caption.trim(), tags });
        toast.success('Template updated');
      } else {
        await addTemplate({ name: name.trim(), caption: caption.trim(), tags });
        toast.success('Template created');
      }
      onClose();
    } catch {
      toast.error('Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={initial ? 'Edit Template' : 'New Template'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Tokyo launch / spring feature / creator batch"
          autoFocus
        />

        <div className="space-y-2">
          <label className="field-label">Caption</label>
          <HashtagTextarea
            value={caption}
            onChange={setCaption}
            placeholder="Write the reusable caption with hooks, CTA, hashtags, and mentions…"
            rows={6}
            className="text-sm"
          />
          <p className="field-hint text-right">{caption.length} / 2200</p>
        </div>

        <Input
          label="Tags"
          value={tagsRaw}
          onChange={(event) => setTagsRaw(event.target.value)}
          placeholder="campaign, creator, product-launch"
          hint="Comma-separated tags help operators retrieve templates faster."
        />

        <div className="flex gap-3 pt-1">
          <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" className="flex-1" loading={saving}>
            {initial ? 'Save Changes' : 'Create Template'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function TemplatesPage() {
  const templates = useTemplateStore((s) => s.templates);
  const removeTemplate = useTemplateStore((s) => s.removeTemplate);
  const fetchTemplates = useTemplateStore((s) => s.fetchTemplates);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<CaptionTemplate | undefined>();

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const sortedTemplates = [...templates].sort((left, right) => right.usageCount - left.usageCount);
  const mostUsed = sortedTemplates[0];

  return (
    <div className="page-shell max-w-6xl space-y-6">
      <PageHeader
        eyebrow="Content System"
        title="Caption Templates"
        description="Reusable narrative blocks for launches, creator cycles, and evergreen posting. Keep voice consistent while speeding up operator flow."
        icon={<FileText className="h-6 w-6 text-[#7dcfff]" />}
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            New Template
          </Button>
        }
      >
        <div className="metric-grid">
          <HeaderStat label="Templates" value={templates.length} tone="cyan" />
          <HeaderStat label="Hot Template" value={mostUsed?.name ?? 'None'} tone="violet" />
        </div>
      </PageHeader>

      {sortedTemplates.length === 0 ? (
        <Card className="py-18 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.05)]">
            <Sparkles className="h-7 w-7 text-[#7dcfff]" />
          </div>
          <p className="mt-5 text-lg font-semibold text-[#eef4ff]">No templates stored</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-[#8e9ac0]">
            Start a reusable caption library for seasonal pushes, creator approvals, or campaign-specific voice.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4" />
              Create first template
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {sortedTemplates.map((template) => (
            <Card key={template.id} glow className="flex h-full flex-col gap-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-semibold text-[#eef4ff]">{template.name}</h2>
                    {template.usageCount > 0 && (
                      <span className="glass-chip !text-[11px]">used {template.usageCount}x</span>
                    )}
                  </div>
                  {template.tags.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[#9aa7cf]">
                      <Hash className="h-3.5 w-3.5 text-[#7aa2f7]" />
                      {template.tags.map((tag) => (
                        <span key={tag} className="rounded-full border border-[rgba(122,162,247,0.18)] bg-[rgba(122,162,247,0.12)] px-2 py-1 text-[#cfe3ff]">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setEditing(template)}
                    className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-2xl border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] text-[#95a3cb] transition-colors duration-200 hover:border-[rgba(125,207,255,0.28)] hover:text-[#eef4ff]"
                    aria-label={`Edit ${template.name}`}
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      await removeTemplate(template.id);
                      toast.success('Template deleted');
                    }}
                    className="inline-flex h-10 w-10 cursor-pointer items-center justify-center rounded-2xl border border-[rgba(247,118,142,0.18)] bg-[rgba(247,118,142,0.08)] text-[#ffc4d0] transition-colors duration-200 hover:bg-[rgba(247,118,142,0.14)]"
                    aria-label={`Delete ${template.name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <pre className="code-block min-h-[11rem] whitespace-pre-wrap break-words font-sans text-sm text-[#d6e0ff]">
                {template.caption}
              </pre>

              <div className="mt-auto flex items-center justify-between gap-3 text-xs text-[#7381aa]">
                <span>Created {new Date(template.createdAt).toLocaleDateString()}</span>
                <span>{template.caption.length} chars</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {showCreate && <TemplateModal onClose={() => setShowCreate(false)} />}
      {editing && <TemplateModal key={editing.id} onClose={() => setEditing(undefined)} initial={editing} />}
    </div>
  );
}
