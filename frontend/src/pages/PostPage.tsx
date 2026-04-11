import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { ChevronDown, ChevronUp, FileText, ImagePlus, MapPin, Search, Send, Tag, Upload, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { postsApi } from '../api/posts';
import { JobRow } from '../components/JobRow';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { HeaderStat, PageHeader } from '../components/ui/PageHeader';
import { Modal } from '../components/ui/Modal';
import { usePostJobStream } from '../features/posts/hooks/usePostJobStream';
import { useAccountStore } from '../store/accounts';
import { usePostStore } from '../store/posts';
import { useTemplateStore } from '../store/templates';
import { HashtagTextarea } from '../components/instagram/HashtagTextarea';

function MediaDropzone({ files, onChange }: { files: File[]; onChange: (nextFiles: File[]) => void }) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      onChange([...files, ...accepted].slice(0, 10));
    },
    [files, onChange],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpg', '.jpeg', '.png', '.webp'], 'video/*': ['.mp4', '.mov'] },
    maxFiles: 10,
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`cursor-pointer rounded-[1.5rem] border p-8 text-center transition-all duration-200 ${
          isDragActive
            ? 'border-[rgba(125,207,255,0.4)] bg-[rgba(125,207,255,0.12)] shadow-[0_24px_54px_rgba(8,12,22,0.34)]'
            : 'border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] hover:border-[rgba(125,207,255,0.24)] hover:bg-[rgba(255,255,255,0.06)]'
        }`}
      >
        <input {...getInputProps()} aria-label="Upload media files" />
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-[1.35rem] border border-[rgba(125,207,255,0.16)] bg-[rgba(255,255,255,0.06)]">
          <ImagePlus className={`h-6 w-6 ${isDragActive ? 'text-[#7dcfff]' : 'text-[#9aa7cf]'}`} />
        </div>
        <p className="text-sm text-[#dbe5ff]">
          {isDragActive ? 'Drop files here…' : 'Drag photos or videos here, or click to browse'}
        </p>
        <p className="mt-2 text-xs text-[#7f8bb3]">JPG, PNG, WEBP, MP4, MOV. Up to 10 files per job.</p>
      </div>

      {files.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {files.map((file, index) => (
            <div key={`${file.name}-${index}`} className="group relative">
              <div className="h-24 w-24 overflow-hidden rounded-[1.2rem] border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.05)]">
                {file.type.startsWith('image/') ? (
                  <img src={URL.createObjectURL(file)} alt={file.name} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-[#9aa7cf]">Video</div>
                )}
              </div>
              <button
                type="button"
                onClick={() => onChange(files.filter((_, currentIndex) => currentIndex !== index))}
                className="absolute -right-1.5 -top-1.5 inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded-full border border-[rgba(247,118,142,0.24)] bg-[rgba(247,118,142,0.9)] text-white opacity-0 transition-opacity duration-150 group-hover:opacity-100"
                aria-label={`Remove ${file.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TemplatePickerModal({
  open,
  onClose,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (caption: string) => void;
}) {
  const templates = useTemplateStore((s) => s.templates);
  const incrementUsage = useTemplateStore((s) => s.incrementUsage);
  const [search, setSearch] = useState('');

  const filtered = templates
    .filter((template) =>
      !search ||
      template.name.toLowerCase().includes(search.toLowerCase()) ||
      template.caption.toLowerCase().includes(search.toLowerCase()) ||
      template.tags.some((tag) => tag.toLowerCase().includes(search.toLowerCase())),
    )
    .sort((left, right) => right.usageCount - left.usageCount);

  const handlePick = (id: string, caption: string) => {
    incrementUsage(id);
    onSelect(caption);
    onClose();
  };

  return (
    <Modal open={open} onClose={onClose} title="Pick a Template">
      <div className="space-y-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7f8bb3]" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search templates…"
            className="glass-field pl-10 text-sm"
            aria-label="Search templates"
          />
        </div>

        {filtered.length === 0 ? (
          <p className="py-6 text-center text-sm text-[#8e9ac0]">
            {templates.length === 0 ? 'No templates yet. Create one in the Templates page.' : 'No matching templates.'}
          </p>
        ) : (
          <div className="max-h-96 space-y-3 overflow-y-auto pr-1">
            {filtered.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => handlePick(template.id, template.caption)}
                className="w-full cursor-pointer rounded-[1.25rem] border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] p-4 text-left transition-all duration-200 hover:border-[rgba(125,207,255,0.24)] hover:bg-[rgba(255,255,255,0.06)]"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-[#eef4ff]">{template.name}</span>
                  {template.usageCount > 0 && <span className="glass-chip !text-[11px]">used {template.usageCount}x</span>}
                </div>
                <p className="mt-3 line-clamp-3 text-sm text-[#8e9ac0]">{template.caption}</p>
                {template.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {template.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-[rgba(125,207,255,0.16)] bg-[rgba(125,207,255,0.12)] px-2 py-1 text-[11px] text-[#d2f3ff]"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}

export function PostPage() {
  const accounts = useAccountStore((s) => s.accounts);
  const jobs = usePostStore((s) => s.jobs);
  const addJob = usePostStore((s) => s.addJob);
  const [caption, setCaption] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [mediaType, setMediaType] = useState('');        // '' = auto-infer
  const [thumbnail, setThumbnail] = useState<File | null>(null);
  const [igtvTitle, setIgtvTitle] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [locationName, setLocationName] = useState('');
  const [locationLat, setLocationLat] = useState('');
  const [locationLng, setLocationLng] = useState('');
  const [usertagsJson, setUsertagsJson] = useState('');
  const [extraDataJson, setExtraDataJson] = useState('');

  const activeAccounts = accounts.filter((account) => account.status === 'active');

  const resolvedType = (() => {
    if (mediaType) return mediaType;
    const hasVideo = files.some((f) => /\.(mp4|mov)$/i.test(f.name));
    if (hasVideo) return 'reels';
    if (files.length > 1) return 'album';
    if (files.length === 1) return 'photo';
    return '';
  })();

  // Real-time updates via SSE — replaces polling
  usePostJobStream();

  const toggleAccount = (id: string) => {
    setSelected((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  };

  const selectAll = () => setSelected(activeAccounts.map((account) => account.id));
  const clearAll = () => setSelected([]);

  const handlePost = async () => {
    if (!files.length) {
      toast.error('Add at least one photo or video');
      return;
    }
    if (!selected.length) {
      toast.error('Select at least one account');
      return;
    }
    if (resolvedType === 'igtv' && !igtvTitle.trim()) {
      toast.error('IGTV title is required');
      return;
    }

    // Parse advanced JSON fields
    let parsedUsertags: Array<{ user_id: string; username?: string; x?: number; y?: number }> | undefined;
    let parsedExtraData: Record<string, unknown> | undefined;
    if (usertagsJson.trim()) {
      try {
        parsedUsertags = JSON.parse(usertagsJson);
      } catch {
        toast.error('User tags: invalid JSON');
        return;
      }
    }
    if (extraDataJson.trim()) {
      try {
        parsedExtraData = JSON.parse(extraDataJson);
      } catch {
        toast.error('Extra data: invalid JSON');
        return;
      }
    }

    const location = locationName.trim()
      ? {
          name: locationName.trim(),
          lat: locationLat ? parseFloat(locationLat) : null,
          lng: locationLng ? parseFloat(locationLng) : null,
        }
      : undefined;

    setLoading(true);
    try {
      const job = await postsApi.create({
        caption,
        mediaFiles: files,
        accountIds: selected,
        mediaType: mediaType || undefined,
        thumbnail: thumbnail ?? undefined,
        igtvTitle: igtvTitle || undefined,
        usertags: parsedUsertags,
        location,
        extraData: parsedExtraData,
      });
      addJob(job);
      toast.success('Post job queued');
      setCaption('');
      setFiles([]);
      setSelected([]);
      setMediaType('');
      setThumbnail(null);
      setIgtvTitle('');
      setLocationName('');
      setLocationLat('');
      setLocationLng('');
      setUsertagsJson('');
      setExtraDataJson('');
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Broadcast Control"
        title="Publishing Queue"
        description="Compose one media pack, target the active accounts you trust, and launch synchronized posting jobs with reusable caption templates."
        icon={<Send className="h-6 w-6 text-[#7dcfff]" />}
      >
        <div className="metric-grid">
          <HeaderStat label="Active Accounts" value={activeAccounts.length} tone="green" />
          <HeaderStat label="Queued Jobs" value={jobs.length} tone="violet" />
        </div>
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_360px]">
        <div className="space-y-6">
          <Card className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-kicker">Media Pack</p>
                <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Upload assets</h2>
              </div>
              {resolvedType && (
                <span className={`glass-chip mt-2 uppercase tracking-wide !text-[11px] font-semibold ${
                  resolvedType === 'reels' ? 'text-[#7dcfff]' :
                  resolvedType === 'igtv'  ? 'text-[#bb9af7]' :
                  resolvedType === 'album' ? 'text-[#7aa2f7]' :
                  'text-[#9ece6a]'
                }`}>
                  {resolvedType}
                </span>
              )}
            </div>

            <MediaDropzone files={files} onChange={setFiles} />

            {files.length > 0 && (
              <div className="space-y-3">
                {/* Media type selector */}
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">Post type</p>
                  <div className="flex flex-wrap gap-2">
                    {(['', 'photo', 'reels', 'video', 'album', 'igtv'] as const).map((type) => {
                      const label = type === '' ? 'Auto' : type === 'video' ? 'Feed Video' : type.charAt(0).toUpperCase() + type.slice(1);
                      const disabled = type === 'album' && files.length < 2;
                      return (
                        <button
                          key={type}
                          type="button"
                          disabled={disabled}
                          onClick={() => { setMediaType(type); if (type !== 'reels' && type !== 'video') setThumbnail(null); if (type !== 'igtv') setIgtvTitle(''); }}
                          className={`cursor-pointer rounded-xl border px-3 py-1.5 text-[12px] font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
                            mediaType === type
                              ? 'border-[rgba(125,207,255,0.4)] bg-[rgba(125,207,255,0.14)] text-[#eef4ff]'
                              : 'border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] text-[#8e9ac0] hover:border-[rgba(162,179,229,0.28)] hover:text-[#c0caf5]'
                          }`}
                        >
                          {label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Thumbnail upload — Reels / Feed Video only */}
                {(resolvedType === 'reels' || resolvedType === 'video') && (
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">Thumbnail (optional)</p>
                    {thumbnail ? (
                      <div className="flex items-center gap-3 rounded-xl border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] px-3 py-2">
                        <img src={URL.createObjectURL(thumbnail)} alt="thumbnail" className="h-10 w-10 rounded-lg object-cover" />
                        <span className="min-w-0 flex-1 truncate text-xs text-[#c0caf5]">{thumbnail.name}</span>
                        <button type="button" onClick={() => setThumbnail(null)} className="shrink-0 cursor-pointer text-[#f7768e] transition-opacity hover:opacity-70">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-[rgba(162,179,229,0.2)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5 text-xs text-[#7f8bb3] transition-colors hover:border-[rgba(125,207,255,0.3)] hover:text-[#c0caf5]">
                        <Upload className="h-3.5 w-3.5" />
                        Upload thumbnail image
                        <input type="file" accept="image/*" className="sr-only" onChange={(e) => setThumbnail(e.target.files?.[0] ?? null)} />
                      </label>
                    )}
                  </div>
                )}

                {/* IGTV title — IGTV only */}
                {resolvedType === 'igtv' && (
                  <div>
                    <label className="field-label">IGTV Title <span className="text-[#f7768e]">*</span></label>
                    <input
                      value={igtvTitle}
                      onChange={(e) => setIgtvTitle(e.target.value)}
                      placeholder="Enter a title for your IGTV video…"
                      className="glass-field mt-1 w-full text-sm"
                    />
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-kicker">Narrative</p>
                <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Caption builder</h2>
              </div>
              <Button variant="secondary" size="sm" onClick={() => setShowTemplates(true)}>
                <FileText className="h-4 w-4" />
                Templates
              </Button>
            </div>

            <HashtagTextarea
              value={caption}
              onChange={setCaption}
              placeholder="Write your caption… Use hooks, CTA, hashtags, and mentions."
              rows={6}
              className="text-sm"
              accountId={selected[0] ?? activeAccounts[0]?.id}
            />
            <p className="field-hint text-right">{caption.length} / 2200</p>
          </Card>

          {/* Advanced Options */}
          <Card className="space-y-4">
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="flex w-full cursor-pointer items-center justify-between gap-3"
            >
              <div>
                <p className="text-kicker">Optional</p>
                <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Advanced options</h2>
              </div>
              {showAdvanced
                ? <ChevronUp className="h-5 w-5 text-[#7f8bb3]" />
                : <ChevronDown className="h-5 w-5 text-[#7f8bb3]" />}
            </button>

            {showAdvanced && (
              <div className="space-y-5 pt-1">
                {/* Location */}
                <div className="space-y-2">
                  <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">
                    <MapPin className="h-3.5 w-3.5" /> Location
                  </p>
                  <input
                    value={locationName}
                    onChange={(e) => setLocationName(e.target.value)}
                    placeholder="Location name (e.g. Paris, France)"
                    className="glass-field w-full text-sm"
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      value={locationLat}
                      onChange={(e) => setLocationLat(e.target.value)}
                      placeholder="Latitude (optional)"
                      type="number"
                      step="any"
                      className="glass-field text-sm"
                    />
                    <input
                      value={locationLng}
                      onChange={(e) => setLocationLng(e.target.value)}
                      placeholder="Longitude (optional)"
                      type="number"
                      step="any"
                      className="glass-field text-sm"
                    />
                  </div>
                </div>

                {/* User Tags */}
                <div className="space-y-2">
                  <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">
                    <Tag className="h-3.5 w-3.5" /> User tags (JSON)
                  </p>
                  <textarea
                    value={usertagsJson}
                    onChange={(e) => setUsertagsJson(e.target.value)}
                    placeholder={'[{"user_id":"123","username":"john","x":0.5,"y":0.5}]'}
                    rows={3}
                    className="glass-field w-full font-mono text-xs"
                    spellCheck={false}
                  />
                  <p className="field-hint">Array of &#123;user_id, username, x, y&#125; objects. x/y are 0–1 normalized coords.</p>
                </div>

                {/* Extra Data */}
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-widest text-[#4a5578]">Extra data (JSON)</p>
                  <textarea
                    value={extraDataJson}
                    onChange={(e) => setExtraDataJson(e.target.value)}
                    placeholder='{"audience": "all"}'
                    rows={2}
                    className="glass-field w-full font-mono text-xs"
                    spellCheck={false}
                  />
                  <p className="field-hint">Arbitrary key/value pairs forwarded to the instagrapi upload call.</p>
                </div>
              </div>
            )}
          </Card>

          <Button className="w-full" loading={loading} onClick={handlePost} disabled={loading || !selected.length || !files.length}>
            <Send className="h-4 w-4" />
            Post to {selected.length} account{selected.length !== 1 ? 's' : ''}
          </Button>
        </div>

        <div className="space-y-6">
          <Card className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-kicker">Targeting</p>
                <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Account selection</h2>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={selectAll} className="glass-chip cursor-pointer">
                  All
                </button>
                <button type="button" onClick={clearAll} className="glass-chip cursor-pointer">
                  None
                </button>
              </div>
            </div>

            {activeAccounts.length === 0 ? (
              <div className="rounded-[1.35rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-5 text-sm text-[#8e9ac0]">
                No active accounts. Log in first to create a broadcast job.
              </div>
            ) : (
              <div className="space-y-3">
                {activeAccounts.map((account) => {
                  const checked = selected.includes(account.id);
                  return (
                    <label
                      key={account.id}
                      className={`flex cursor-pointer items-center gap-3 rounded-[1.25rem] border p-3 transition-all duration-200 ${
                        checked
                          ? 'border-[rgba(125,207,255,0.28)] bg-[rgba(125,207,255,0.12)]'
                          : 'border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] hover:border-[rgba(162,179,229,0.2)]'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleAccount(account.id)}
                        className="h-4 w-4 cursor-pointer accent-[#7dcfff]"
                        aria-label={`Select @${account.username}`}
                      />
                      <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[rgba(125,207,255,0.16)] bg-[linear-gradient(135deg,rgba(122,162,247,0.22),rgba(125,207,255,0.12)_60%,rgba(187,154,247,0.18))] text-sm font-semibold uppercase text-[#eef4ff]">
                        {account.username[0]}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-[#eef4ff]">@{account.username}</p>
                        <p className="mt-1 text-xs text-[#8e9ac0]">{account.followers?.toLocaleString() ?? '—'} followers</p>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>

      {jobs.length > 0 && (
        <div className="space-y-4">
          <div>
            <p className="text-kicker">Queue History</p>
            <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Recent jobs</h2>
          </div>
          <div className="space-y-3">
            {jobs.map((job) => (
              <JobRow key={job.id} job={job} />
            ))}
          </div>
        </div>
      )}

      <TemplatePickerModal open={showTemplates} onClose={() => setShowTemplates(false)} onSelect={(nextCaption) => setCaption(nextCaption)} />
    </div>
  );
}
