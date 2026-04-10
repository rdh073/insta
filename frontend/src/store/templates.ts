import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { templatesApi } from '../api/templates';
import type { CaptionTemplate } from '../types';

interface TemplateStore {
  templates: CaptionTemplate[];
  /** Load templates from the backend (called on app mount). */
  fetchTemplates: () => Promise<void>;
  addTemplate: (t: Omit<CaptionTemplate, 'id' | 'createdAt' | 'usageCount'>) => Promise<void>;
  updateTemplate: (id: string, patch: Partial<Pick<CaptionTemplate, 'name' | 'caption' | 'tags'>>) => Promise<void>;
  removeTemplate: (id: string) => Promise<void>;
  incrementUsage: (id: string) => Promise<void>;
}

export const useTemplateStore = create<TemplateStore>()(
  persist(
    (set, get) => ({
      templates: [],

      fetchTemplates: async () => {
        try {
          const templates = await templatesApi.list();
          set({ templates });
        } catch {
          // Backend unreachable — keep local state as fallback
        }
      },

      addTemplate: async ({ name, caption, tags }) => {
        try {
          const created = await templatesApi.create(name, caption, tags);
          set((s) => ({ templates: [...s.templates, created] }));
        } catch {
          // Offline fallback: create locally with a temp UUID
          const local: CaptionTemplate = {
            id: crypto.randomUUID(),
            name,
            caption,
            tags,
            createdAt: new Date().toISOString(),
            usageCount: 0,
          };
          set((s) => ({ templates: [...s.templates, local] }));
        }
      },

      updateTemplate: async (id, patch) => {
        // Optimistic update
        set((s) => ({
          templates: s.templates.map((t) => (t.id === id ? { ...t, ...patch } : t)),
        }));
        try {
          const updated = await templatesApi.update(id, patch);
          set((s) => ({
            templates: s.templates.map((t) => (t.id === id ? updated : t)),
          }));
        } catch {
          // Keep optimistic state on failure
        }
      },

      removeTemplate: async (id) => {
        set((s) => ({ templates: s.templates.filter((t) => t.id !== id) }));
        try {
          await templatesApi.delete(id);
        } catch {
          // Deletion failed — re-fetch to restore truth
          get().fetchTemplates();
        }
      },

      incrementUsage: async (id) => {
        set((s) => ({
          templates: s.templates.map((t) =>
            t.id === id ? { ...t, usageCount: t.usageCount + 1 } : t
          ),
        }));
        try {
          await templatesApi.incrementUsage(id);
        } catch {
          // Non-critical — optimistic increment is fine
        }
      },
    }),
    { name: 'insta-templates', partialize: (s) => ({ templates: s.templates }) }
  )
);
