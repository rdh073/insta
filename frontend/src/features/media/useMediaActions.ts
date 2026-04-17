import { useCallback } from 'react';
import toast from 'react-hot-toast';
import { mediaApi } from '../../api/instagram/media';
import type { MediaActionReceipt } from '../../types/instagram/media';
import { useMediaStore } from '../../store/media';
import type { MediaAction } from './types';

interface UseMediaActionsArgs {
  accountId: string;
  mediaId: string;
}

interface UseMediaActionsResult {
  isMutating: (action: MediaAction) => boolean;
  isAnyMutating: boolean;
  editCaption: (caption: string) => Promise<MediaActionReceipt | null>;
  deleteMedia: () => Promise<MediaActionReceipt | null>;
  pin: () => Promise<MediaActionReceipt | null>;
  unpin: () => Promise<MediaActionReceipt | null>;
  archive: () => Promise<MediaActionReceipt | null>;
  unarchive: () => Promise<MediaActionReceipt | null>;
  save: (collectionPk?: number | null) => Promise<MediaActionReceipt | null>;
  unsave: (collectionPk?: number | null) => Promise<MediaActionReceipt | null>;
}

function reportReceipt(receipt: MediaActionReceipt): boolean {
  if (receipt.success) {
    toast.success(receipt.reason);
    return true;
  }
  toast.error(receipt.reason);
  return false;
}

export function useMediaActions({ accountId, mediaId }: UseMediaActionsArgs): UseMediaActionsResult {
  const beginMutation = useMediaStore((s) => s.beginMutation);
  const endMutation = useMediaStore((s) => s.endMutation);
  const applyCaptionEdit = useMediaStore((s) => s.applyCaptionEdit);
  const removeMedia = useMediaStore((s) => s.removeMedia);
  const inFlight = useMediaStore((s) => s.mutating[mediaId] ?? []);

  const isMutating = useCallback((action: MediaAction) => inFlight.includes(action), [inFlight]);

  const guard = useCallback(
    async <T,>(action: MediaAction, body: () => Promise<T>): Promise<T | null> => {
      if (!accountId || !mediaId) {
        toast.error('Account or media not selected');
        return null;
      }
      if (inFlight.includes(action)) return null;
      beginMutation(mediaId, action);
      try {
        return await body();
      } catch (e) {
        toast.error((e as Error).message || 'Request failed');
        return null;
      } finally {
        endMutation(mediaId, action);
      }
    },
    [accountId, mediaId, inFlight, beginMutation, endMutation],
  );

  const editCaption = useCallback(
    (caption: string) =>
      guard('edit', async () => {
        const receipt = await mediaApi.editCaption(accountId, mediaId, caption);
        if (reportReceipt(receipt)) applyCaptionEdit(mediaId, caption);
        return receipt;
      }),
    [accountId, mediaId, guard, applyCaptionEdit],
  );

  const deleteMedia = useCallback(
    () =>
      guard('delete', async () => {
        const receipt = await mediaApi.delete(accountId, mediaId);
        if (reportReceipt(receipt)) removeMedia(mediaId);
        return receipt;
      }),
    [accountId, mediaId, guard, removeMedia],
  );

  const pin = useCallback(
    () =>
      guard('pin', async () => {
        const receipt = await mediaApi.pin(accountId, mediaId);
        reportReceipt(receipt);
        return receipt;
      }),
    [accountId, mediaId, guard],
  );

  const unpin = useCallback(
    () =>
      guard('unpin', async () => {
        const receipt = await mediaApi.unpin(accountId, mediaId);
        reportReceipt(receipt);
        return receipt;
      }),
    [accountId, mediaId, guard],
  );

  const archive = useCallback(
    () =>
      guard('archive', async () => {
        const receipt = await mediaApi.archive(accountId, mediaId);
        if (reportReceipt(receipt)) removeMedia(mediaId);
        return receipt;
      }),
    [accountId, mediaId, guard, removeMedia],
  );

  const unarchive = useCallback(
    () =>
      guard('unarchive', async () => {
        const receipt = await mediaApi.unarchive(accountId, mediaId);
        reportReceipt(receipt);
        return receipt;
      }),
    [accountId, mediaId, guard],
  );

  const save = useCallback(
    (collectionPk?: number | null) =>
      guard('save', async () => {
        const receipt = await mediaApi.save(accountId, mediaId, collectionPk);
        reportReceipt(receipt);
        return receipt;
      }),
    [accountId, mediaId, guard],
  );

  const unsave = useCallback(
    (collectionPk?: number | null) =>
      guard('unsave', async () => {
        const receipt = await mediaApi.unsave(accountId, mediaId, collectionPk);
        reportReceipt(receipt);
        return receipt;
      }),
    [accountId, mediaId, guard],
  );

  return {
    isMutating,
    isAnyMutating: inFlight.length > 0,
    editCaption,
    deleteMedia,
    pin,
    unpin,
    archive,
    unarchive,
    save,
    unsave,
  };
}
