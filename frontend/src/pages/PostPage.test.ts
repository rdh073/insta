import { describe, expect, it, vi } from 'vitest';
import { reconcileFileObjectUrls, revokeFileObjectUrls } from './PostPage';

describe('PostPage object URL lifecycle helpers', () => {
  it('reuses existing URLs, creates new URLs, and revokes removed file URLs', () => {
    const fileA = { name: 'a.jpg' } as File;
    const fileB = { name: 'b.jpg' } as File;
    const fileC = { name: 'c.jpg' } as File;

    const previous = new Map<File, string>([
      [fileA, 'blob:a'],
      [fileB, 'blob:b'],
    ]);
    const createObjectURL = vi.fn((file: File) => `blob:${file.name}`);
    const revokeObjectURL = vi.fn();

    const next = reconcileFileObjectUrls([fileA, fileC], previous, createObjectURL, revokeObjectURL);

    expect(next.get(fileA)).toBe('blob:a');
    expect(next.get(fileC)).toBe('blob:c.jpg');
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(createObjectURL).toHaveBeenCalledWith(fileC);
    expect(revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:b');
  });

  it('revokes all URLs during teardown cleanup', () => {
    const fileA = { name: 'a.jpg' } as File;
    const fileB = { name: 'b.jpg' } as File;
    const revokeObjectURL = vi.fn();

    revokeFileObjectUrls(
      new Map<File, string>([
        [fileA, 'blob:a'],
        [fileB, 'blob:b'],
      ]),
      revokeObjectURL,
    );

    expect(revokeObjectURL).toHaveBeenCalledTimes(2);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:a');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:b');
  });
});
