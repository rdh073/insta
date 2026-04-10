import { api } from './client';
import type { CaptionTemplate } from '../types';

interface ApiTemplate {
  id: string;
  name: string;
  caption: string;
  tags: string[];
  usageCount: number;
  createdAt: string;
}

function fromApi(t: ApiTemplate): CaptionTemplate {
  return {
    id: t.id,
    name: t.name,
    caption: t.caption,
    tags: t.tags,
    usageCount: t.usageCount,
    createdAt: t.createdAt,
  };
}

export const templatesApi = {
  list: () =>
    api.get<ApiTemplate[]>('/templates').then((r) => r.data.map(fromApi)),

  create: (name: string, caption: string, tags: string[]) =>
    api.post<ApiTemplate>('/templates', { name, caption, tags }).then((r) => fromApi(r.data)),

  update: (id: string, patch: Partial<Pick<CaptionTemplate, 'name' | 'caption' | 'tags'>>) =>
    api.patch<ApiTemplate>(`/templates/${id}`, patch).then((r) => fromApi(r.data)),

  delete: (id: string) => api.delete(`/templates/${id}`),

  incrementUsage: (id: string) => api.post(`/templates/${id}/usage`),
};
