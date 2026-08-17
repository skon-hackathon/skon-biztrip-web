import type { TripStatus } from '$lib/api/types';

export const TRIP_STATUS_LABELS: Record<TripStatus, string> = {
	DRAFT: '임시저장',
	SUBMITTED: '승인대기',
	APPROVED: '승인',
	REJECTED: '반려',
	COMPLETED: '완료',
	SETTLED: '정산완료'
};

/** Badge.svelte의 tone과 그대로 맞춘다. */
export const TRIP_STATUS_TONES: Record<TripStatus, 'neutral' | 'primary' | 'success' | 'danger'> = {
	DRAFT: 'neutral',
	SUBMITTED: 'primary',
	APPROVED: 'success',
	REJECTED: 'danger',
	COMPLETED: 'success',
	SETTLED: 'neutral'
};

/** 목록 필터의 상태 드롭다운 순서 — spec 5.4의 전이 순서를 따른다. */
export const TRIP_STATUS_ORDER: TripStatus[] = [
	'DRAFT',
	'SUBMITTED',
	'APPROVED',
	'REJECTED',
	'COMPLETED',
	'SETTLED'
];
