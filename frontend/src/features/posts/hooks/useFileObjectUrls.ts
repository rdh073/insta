import { useEffect, useRef, useState } from 'react';

export function reconcileFileObjectUrls(
  files: readonly File[],
  previous: ReadonlyMap<File, string>,
  createObjectURL: (file: File) => string = URL.createObjectURL,
  revokeObjectURL: (url: string) => void = URL.revokeObjectURL,
): Map<File, string> {
  const next = new Map<File, string>();

  for (const file of files) {
    const existingUrl = previous.get(file);
    next.set(file, existingUrl ?? createObjectURL(file));
  }

  for (const [file, objectUrl] of previous.entries()) {
    if (!next.has(file)) {
      revokeObjectURL(objectUrl);
    }
  }

  return next;
}

export function revokeFileObjectUrls(
  fileObjectUrls: ReadonlyMap<File, string>,
  revokeObjectURL: (url: string) => void = URL.revokeObjectURL,
): void {
  for (const objectUrl of fileObjectUrls.values()) {
    revokeObjectURL(objectUrl);
  }
}

export function useFileObjectUrls(files: readonly File[]): ReadonlyMap<File, string> {
  const objectUrlRef = useRef<Map<File, string>>(new Map());
  const [objectUrls, setObjectUrls] = useState<ReadonlyMap<File, string>>(() => new Map());

  useEffect(() => {
    const next = reconcileFileObjectUrls(files, objectUrlRef.current);
    objectUrlRef.current = next;
    setObjectUrls(next);
  }, [files]);

  useEffect(
    () => () => {
      revokeFileObjectUrls(objectUrlRef.current);
      objectUrlRef.current = new Map();
    },
    [],
  );

  return objectUrls;
}
