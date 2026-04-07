export interface PublicUserProfile {
  pk: number;
  username: string;
  fullName: string | null;
  biography: string | null;
  profilePicUrl: string | null;
  followerCount: number | null;
  followingCount: number | null;
  mediaCount: number | null;
  isPrivate: boolean | null;
  isVerified: boolean | null;
  isBusiness: boolean | null;
}

export interface AuthenticatedAccountProfile extends PublicUserProfile {
  email: string | null;
  phoneNumber: string | null;
}

export interface DirectParticipantSummary {
  userId: number;
  username: string;
  fullName: string | null;
  profilePicUrl: string | null;
  isPrivate: boolean | null;
}
