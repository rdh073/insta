import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { CaptionTemplate } from '../types';

interface TemplateStore {
  templates: CaptionTemplate[];
  addTemplate: (t: Omit<CaptionTemplate, 'id' | 'createdAt' | 'usageCount'>) => void;
  updateTemplate: (id: string, patch: Partial<Pick<CaptionTemplate, 'name' | 'caption' | 'tags'>>) => void;
  removeTemplate: (id: string) => void;
  incrementUsage: (id: string) => void;
}

export const useTemplateStore = create<TemplateStore>()(
  persist(
    (set) => ({
      templates: [],

      addTemplate: ({ name, caption, tags }) =>
        set((s) => ({
          templates: [
            ...s.templates,
            {
              id: crypto.randomUUID(),
              name,
              caption,
              tags,
              createdAt: new Date().toISOString(),
              usageCount: 0,
            },
          ],
        })),

      updateTemplate: (id, patch) =>
        set((s) => ({
          templates: s.templates.map((t) => (t.id === id ? { ...t, ...patch } : t)),
        })),

      removeTemplate: (id) =>
        set((s) => ({ templates: s.templates.filter((t) => t.id !== id) })),

      incrementUsage: (id) =>
        set((s) => ({
          templates: s.templates.map((t) =>
            t.id === id ? { ...t, usageCount: t.usageCount + 1 } : t
          ),
        })),
    }),
    { name: 'insta-templates', partialize: (s) => ({ templates: s.templates }) }
  )
);
