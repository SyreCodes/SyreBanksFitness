export type Role = 'SUPER_ADMIN' | 'ADMIN' | 'COACH' | 'CLIENT' | 'LEAD';
export type AttentionStatus = 'ON_TRACK' | 'WATCH' | 'NEEDS_ATTENTION';
export type LeadStage = 'NEW' | 'CONTACTED' | 'QUALIFIED' | 'CONSULTATION_BOOKED' | 'OFFER_SENT' | 'PAYMENT_PENDING' | 'WON' | 'LOST';
export type Paginated<T> = { items: T[]; total: number };
export type ApiErrorBody = { error: { code: string; message: string; request_id: string } };
