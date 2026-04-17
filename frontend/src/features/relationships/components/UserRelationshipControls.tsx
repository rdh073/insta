import { BellOff, BellRing, EyeOff, Eye, Film, Image, MessageSquare, Video } from 'lucide-react';
import { Card } from '../../../components/ui/Card';
import { useRelationshipControls } from '../hooks/useRelationshipControls';
import type { NotificationKind } from '../../../api/instagram/relationships';

interface Props {
  accountId: string;
  targetUsername: string;
}

type ToggleButtonProps = {
  label: string;
  enabled: boolean;
  pending: boolean;
  disabled?: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  activeColor?: string;
};

function ToggleButton({
  label,
  enabled,
  pending,
  disabled,
  onClick,
  icon,
  activeColor = '#7dcfff',
}: ToggleButtonProps) {
  const border = enabled ? activeColor : 'rgba(162,179,229,0.18)';
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending || disabled}
      className="glass-panel-soft group flex items-center justify-between gap-3 rounded-[1rem] border px-4 py-3 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60"
      style={{ borderColor: border }}
    >
      <span className="flex items-center gap-2 text-[#c0caf5]">
        <span style={{ color: enabled ? activeColor : '#7f8bb3' }}>{icon}</span>
        {label}
      </span>
      <span
        className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${
          enabled ? 'bg-[rgba(125,207,255,0.35)]' : 'bg-[rgba(255,255,255,0.06)]'
        }`}
      >
        <span
          className="absolute h-3.5 w-3.5 rounded-full bg-white transition-transform"
          style={{ transform: enabled ? 'translateX(22px)' : 'translateX(4px)' }}
        />
      </span>
      {pending && <span className="sr-only">Saving…</span>}
    </button>
  );
}

const NOTIFICATION_META: Record<
  NotificationKind,
  { label: string; icon: React.ReactNode }
> = {
  posts: { label: 'Post notifications', icon: <Image className="h-4 w-4" /> },
  videos: { label: 'Video notifications', icon: <Video className="h-4 w-4" /> },
  reels: { label: 'Reel notifications', icon: <Film className="h-4 w-4" /> },
  stories: { label: 'Story notifications', icon: <MessageSquare className="h-4 w-4" /> },
};

export function UserRelationshipControls({ accountId, targetUsername }: Props) {
  const {
    control,
    pending,
    toggleMutePosts,
    toggleMuteStories,
    toggleNotification,
  } = useRelationshipControls(accountId, targetUsername);

  if (!accountId || !targetUsername) return null;

  const notificationKinds: NotificationKind[] = ['posts', 'videos', 'reels', 'stories'];

  return (
    <Card className="space-y-5">
      <div>
        <p className="field-label mb-1">Feed visibility for @{targetUsername}</p>
        <p className="field-hint mb-3">
          Quiet this user without unfollowing. Applies to the authenticated account only.
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <ToggleButton
            label={control.mutedPosts ? 'Posts muted' : 'Mute posts'}
            enabled={control.mutedPosts}
            pending={pending.has('mute_posts')}
            onClick={toggleMutePosts}
            icon={control.mutedPosts ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            activeColor="#bb9af7"
          />
          <ToggleButton
            label={control.mutedStories ? 'Stories muted' : 'Mute stories'}
            enabled={control.mutedStories}
            pending={pending.has('mute_stories')}
            onClick={toggleMuteStories}
            icon={control.mutedStories ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            activeColor="#bb9af7"
          />
        </div>
      </div>

      <div>
        <p className="field-label mb-1">Push notifications</p>
        <p className="field-hint mb-3">
          Toggle per-user alerts for new content published by this account.
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {notificationKinds.map((kind) => {
            const enabled = control.notifications[kind];
            const meta = NOTIFICATION_META[kind];
            return (
              <ToggleButton
                key={kind}
                label={meta.label}
                enabled={enabled}
                pending={pending.has(`notify_${kind}`)}
                onClick={() => toggleNotification(kind)}
                icon={
                  enabled ? (
                    <BellRing className="h-4 w-4" />
                  ) : (
                    <BellOff className="h-4 w-4" />
                  )
                }
                activeColor="#7dcfff"
              />
            );
          })}
        </div>
      </div>
    </Card>
  );
}
