import { useCallback, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { postsApi } from '../../../api/posts';
import { useAccountStore } from '../../../store/accounts';
import { usePostStore } from '../../../store/posts';
import { usePostJobStream } from './usePostJobStream';
import { useFileObjectUrls } from './useFileObjectUrls';

const EMPTY_FILES: File[] = [];

export type PostMediaType = '' | 'photo' | 'reels' | 'video' | 'album' | 'igtv';

export function usePostComposer() {
  const accounts = useAccountStore((s) => s.accounts);
  const jobs = usePostStore((s) => s.jobs);
  const streamError = usePostStore((s) => s.streamError);
  const addJob = usePostStore((s) => s.addJob);

  const [caption, setCaption] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [mediaType, setMediaType] = useState<PostMediaType>('');
  const [thumbnail, setThumbnail] = useState<File | null>(null);
  const [igtvTitle, setIgtvTitle] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [locationName, setLocationName] = useState('');
  const [locationLat, setLocationLat] = useState('');
  const [locationLng, setLocationLng] = useState('');
  const [usertagsJson, setUsertagsJson] = useState('');
  const [extraDataJson, setExtraDataJson] = useState('');

  const thumbnailFiles = useMemo<readonly File[]>(() => (thumbnail ? [thumbnail] : EMPTY_FILES), [thumbnail]);
  const thumbnailPreviewUrls = useFileObjectUrls(thumbnailFiles);
  const thumbnailPreviewUrl = thumbnail ? thumbnailPreviewUrls.get(thumbnail) : undefined;

  const activeAccounts = useMemo(
    () => accounts.filter((account) => account.status === 'active'),
    [accounts],
  );

  const resolvedType = useMemo((): PostMediaType => {
    if (mediaType) return mediaType;
    const hasVideo = files.some((f) => /\.(mp4|mov)$/i.test(f.name));
    if (hasVideo) return 'reels';
    if (files.length > 1) return 'album';
    if (files.length === 1) return 'photo';
    return '';
  }, [mediaType, files]);

  usePostJobStream();

  const toggleAccount = useCallback((id: string) => {
    setSelected((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));
  }, []);

  const selectAll = useCallback(() => {
    setSelected(activeAccounts.map((account) => account.id));
  }, [activeAccounts]);

  const clearAll = useCallback(() => {
    setSelected([]);
  }, []);

  const applyMediaType = useCallback((type: PostMediaType) => {
    setMediaType(type);
    if (type !== 'reels' && type !== 'video') setThumbnail(null);
    if (type !== 'igtv') setIgtvTitle('');
  }, []);

  const handlePost = useCallback(async () => {
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
  }, [
    addJob,
    caption,
    extraDataJson,
    files,
    igtvTitle,
    locationLat,
    locationLng,
    locationName,
    mediaType,
    resolvedType,
    selected,
    thumbnail,
    usertagsJson,
  ]);

  return {
    jobs,
    streamError,
    caption,
    setCaption,
    files,
    setFiles,
    selected,
    loading,
    showTemplates,
    setShowTemplates,
    mediaType,
    resolvedType,
    thumbnail,
    setThumbnail,
    thumbnailPreviewUrl,
    igtvTitle,
    setIgtvTitle,
    showAdvanced,
    setShowAdvanced,
    locationName,
    setLocationName,
    locationLat,
    setLocationLat,
    locationLng,
    setLocationLng,
    usertagsJson,
    setUsertagsJson,
    extraDataJson,
    setExtraDataJson,
    activeAccounts,
    toggleAccount,
    selectAll,
    clearAll,
    applyMediaType,
    handlePost,
  };
}
