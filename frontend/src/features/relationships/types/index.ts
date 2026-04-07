export type RelationshipTab = 'follow' | 'unfollow' | 'cross-follow';

export interface JobResult {
  account: string;
  target: string;
  action: 'follow' | 'unfollow';
  success: boolean;
  error?: string;
}

export interface CrossFollowPair {
  a: string;
  b: string;
  aFollowsB: boolean | null;
  bFollowsA: boolean | null;
}
