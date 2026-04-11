import { useState } from 'react';
import { useSettingsStore } from '../../../store/settings';
import { buildProxyImageUrl } from '../../../lib/api-base';

export function AccountAvatar({ username, avatar, size = 'md' }: { username: string; avatar?: string; size?: 'sm' | 'md' }) {
  const [imgFailed, setImgFailed] = useState(false);
  const backendUrl = useSettingsStore((s) => s.backendUrl);
  const backendApiKey = useSettingsStore((s) => s.backendApiKey);
  const dim = size === 'sm' ? 'h-8 w-8' : 'h-12 w-12';
  const radius = size === 'sm' ? 'rounded-[0.8rem]' : 'rounded-[1.2rem]';
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm';

  if (avatar && !imgFailed) {
    const src = buildProxyImageUrl(avatar, backendUrl, backendApiKey);
    return (
      <img
        src={src}
        alt={username}
        className={`${dim} shrink-0 ${radius} border border-[rgba(125,207,255,0.16)] object-cover`}
        onError={() => setImgFailed(true)}
      />
    );
  }
  return (
    <div className={`flex ${dim} shrink-0 items-center justify-center ${radius} border border-[rgba(125,207,255,0.16)] bg-[linear-gradient(135deg,rgba(122,162,247,0.22),rgba(125,207,255,0.12)_60%,rgba(187,154,247,0.18))] ${textSize} font-semibold uppercase text-[#eef4ff]`}>
      {username[0]}
    </div>
  );
}
