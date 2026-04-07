export interface HashtagSummary {
  id: number;
  name: string;
  mediaCount: number | null;
  profilePicUrl: string | null;
}

export interface LocationSummary {
  pk: number;
  name: string;
  address: string | null;
  city: string | null;
  lat: number | null;
  lng: number | null;
  externalId: number | null;
  externalIdSource: string | null;
}
