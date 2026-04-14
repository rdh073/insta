import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { ChevronDown, ChevronUp, FileText, ImagePlus, MapPin, Search, Send, Tag, Upload, X } from 'lucide-react';
import { JobRow } from '../../../components/JobRow';
import { HashtagTextarea } from '../../../components/instagram/HashtagTextarea';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { HeaderStat, PageHeader } from '../../../components/ui/PageHeader';
import { Modal } from '../../../components/ui/Modal';
import { useTemplateStore } from '../../../store/templates';
import { useFileObjectUrls } from '../hooks/useFileObjectUrls';
import { usePostComposer, type PostMediaType } from '../hooks/usePostComposer';

const MEDIA_TYPE_OPTIONS: readonly PostMediaType[] = ['', 'photo', 'reels', 'video', 'album', 'igtv'];

function MediaDropzone({ files, onChange }: { files: File[]; onChange: (nextFiles: File[]) => void }) {
  const previewUrls = useFileObjectUrls(files);

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
                  <img src={previewUrls.get(file)} alt={file.name} className="h-full w-full object-cover" />
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
      !search
      || template.name.toLowerCase().includes(search.toLowerCase())
      || template.caption.toLowerCase().includes(search.toLowerCase())
      || template.tags.some((tag) => tag.toLowerCase().includes(search.toLowerCase())),
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

export function PostWorkspace() {
  const composer = usePostComposer();

  return (
    <div className="page-shell max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Broadcast Control"
        title="Publishing Queue"
        description="Compose one media pack, target the active accounts you trust, and launch synchronized posting jobs with reusable caption templates."
        icon={<Send className="h-6 w-6 text-[#7dcfff]" />}
      >
        <div className="metric-grid">
          <HeaderStat label="Active Accounts" value={composer.activeAccounts.length} tone="green" />
          <HeaderStat label="Queued Jobs" value={composer.jobs.length} tone="violet" />
        </div>
      </PageHeader>

      {composer.streamError && (
        <div
          role="alert"
          className="rounded-[1rem] border border-[rgba(247,118,142,0.24)] bg-[rgba(247,118,142,0.08)] px-4 py-3 text-sm text-[#ffbfd0]"
        >
          {composer.streamError}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_360px]">
        <div className="space-y-6">
          <Card className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-kicker">Media Pack</p>
                <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Upload assets</h2>
              </div>
              {composer.resolvedType && (
                <span
                  className={`glass-chip mt-2 uppercase tracking-wide !text-[11px] font-semibold ${
                    composer.resolvedType === 'reels'
                      ? 'text-[#7dcfff]'
                      : composer.resolvedType === 'igtv'
                        ? 'text-[#bb9af7]'
                        : composer.resolvedType === 'album'
                          ? 'text-[#7aa2f7]'
                          : 'text-[#9ece6a]'
                  }`}
                >
                  {composer.resolvedType}
                </span>
              )}
            </div>

            <MediaDropzone files={composer.files} onChange={composer.setFiles} />

            {composer.files.length > 0 && (
              <div className="space-y-3">
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">Post type</p>
                  <div className="flex flex-wrap gap-2">
                    {MEDIA_TYPE_OPTIONS.map((type) => {
                      const label = type === '' ? 'Auto' : type === 'video' ? 'Feed Video' : type.charAt(0).toUpperCase() + type.slice(1);
                      const disabled = type === 'album' && composer.files.length < 2;
                      return (
                        <button
                          key={type}
                          type="button"
                          disabled={disabled}
                          onClick={() => composer.applyMediaType(type)}
                          className={`cursor-pointer rounded-xl border px-3 py-1.5 text-[12px] font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
                            composer.mediaType === type
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

                {(composer.resolvedType === 'reels' || composer.resolvedType === 'video') && (
                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">Thumbnail (optional)</p>
                    {composer.thumbnail ? (
                      <div className="flex items-center gap-3 rounded-xl border border-[rgba(162,179,229,0.14)] bg-[rgba(255,255,255,0.04)] px-3 py-2">
                        <img src={composer.thumbnailPreviewUrl} alt="thumbnail" className="h-10 w-10 rounded-lg object-cover" />
                        <span className="min-w-0 flex-1 truncate text-xs text-[#c0caf5]">{composer.thumbnail.name}</span>
                        <button
                          type="button"
                          onClick={() => composer.setThumbnail(null)}
                          className="shrink-0 cursor-pointer text-[#f7768e] transition-opacity hover:opacity-70"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-[rgba(162,179,229,0.2)] bg-[rgba(255,255,255,0.03)] px-3 py-2.5 text-xs text-[#7f8bb3] transition-colors hover:border-[rgba(125,207,255,0.3)] hover:text-[#c0caf5]">
                        <Upload className="h-3.5 w-3.5" />
                        Upload thumbnail image
                        <input
                          type="file"
                          accept="image/*"
                          className="sr-only"
                          onChange={(e) => composer.setThumbnail(e.target.files?.[0] ?? null)}
                        />
                      </label>
                    )}
                  </div>
                )}

                {composer.resolvedType === 'igtv' && (
                  <div>
                    <label className="field-label">
                      IGTV Title <span className="text-[#f7768e]">*</span>
                    </label>
                    <input
                      value={composer.igtvTitle}
                      onChange={(e) => composer.setIgtvTitle(e.target.value)}
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
              <Button variant="secondary" size="sm" onClick={() => composer.setShowTemplates(true)}>
                <FileText className="h-4 w-4" />
                Templates
              </Button>
            </div>

            <HashtagTextarea
              value={composer.caption}
              onChange={composer.setCaption}
              placeholder="Write your caption… Use hooks, CTA, hashtags, and mentions."
              rows={6}
              className="text-sm"
              accountId={composer.selected[0] ?? composer.activeAccounts[0]?.id}
            />
            <p className="field-hint text-right">{composer.caption.length} / 2200</p>
          </Card>

          <Card className="space-y-4">
            <button
              type="button"
              onClick={() => composer.setShowAdvanced((v) => !v)}
              className="flex w-full cursor-pointer items-center justify-between gap-3"
            >
              <div>
                <p className="text-kicker">Optional</p>
                <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Advanced options</h2>
              </div>
              {composer.showAdvanced ? <ChevronUp className="h-5 w-5 text-[#7f8bb3]" /> : <ChevronDown className="h-5 w-5 text-[#7f8bb3]" />}
            </button>

            {composer.showAdvanced && (
              <div className="space-y-5 pt-1">
                <div className="space-y-2">
                  <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">
                    <MapPin className="h-3.5 w-3.5" /> Location
                  </p>
                  <input
                    value={composer.locationName}
                    onChange={(e) => composer.setLocationName(e.target.value)}
                    placeholder="Location name (e.g. Paris, France)"
                    className="glass-field w-full text-sm"
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      value={composer.locationLat}
                      onChange={(e) => composer.setLocationLat(e.target.value)}
                      placeholder="Latitude (optional)"
                      type="number"
                      step="any"
                      className="glass-field text-sm"
                    />
                    <input
                      value={composer.locationLng}
                      onChange={(e) => composer.setLocationLng(e.target.value)}
                      placeholder="Longitude (optional)"
                      type="number"
                      step="any"
                      className="glass-field text-sm"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-widest text-[#4a5578]">
                    <Tag className="h-3.5 w-3.5" /> User tags (JSON)
                  </p>
                  <textarea
                    value={composer.usertagsJson}
                    onChange={(e) => composer.setUsertagsJson(e.target.value)}
                    placeholder={'[{"user_id":"123","username":"john","x":0.5,"y":0.5}]'}
                    rows={3}
                    className="glass-field w-full font-mono text-xs"
                    spellCheck={false}
                  />
                  <p className="field-hint">Array of &#123;user_id, username, x, y&#125; objects. x/y are 0–1 normalized coords.</p>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-widest text-[#4a5578]">Extra data (JSON)</p>
                  <textarea
                    value={composer.extraDataJson}
                    onChange={(e) => composer.setExtraDataJson(e.target.value)}
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

          <Button
            className="w-full"
            loading={composer.loading}
            onClick={composer.handlePost}
            disabled={composer.loading || !composer.selected.length || !composer.files.length}
          >
            <Send className="h-4 w-4" />
            Post to {composer.selected.length} account{composer.selected.length !== 1 ? 's' : ''}
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
                <button type="button" onClick={composer.selectAll} className="glass-chip cursor-pointer">
                  All
                </button>
                <button type="button" onClick={composer.clearAll} className="glass-chip cursor-pointer">
                  None
                </button>
              </div>
            </div>

            {composer.activeAccounts.length === 0 ? (
              <div className="rounded-[1.35rem] border border-[rgba(162,179,229,0.12)] bg-[rgba(255,255,255,0.04)] p-5 text-sm text-[#8e9ac0]">
                No active accounts. Log in first to create a broadcast job.
              </div>
            ) : (
              <div className="space-y-3">
                {composer.activeAccounts.map((account) => {
                  const checked = composer.selected.includes(account.id);
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
                        onChange={() => composer.toggleAccount(account.id)}
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

      {composer.jobs.length > 0 && (
        <div className="space-y-4">
          <div>
            <p className="text-kicker">Queue History</p>
            <h2 className="mt-2 text-xl font-semibold text-[#eef4ff]">Recent jobs</h2>
          </div>
          <div className="space-y-3">
            {composer.jobs.map((job) => (
              <JobRow key={job.id} job={job} />
            ))}
          </div>
        </div>
      )}

      <TemplatePickerModal
        open={composer.showTemplates}
        onClose={() => composer.setShowTemplates(false)}
        onSelect={(nextCaption) => composer.setCaption(nextCaption)}
      />
    </div>
  );
}
