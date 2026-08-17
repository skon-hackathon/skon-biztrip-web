import { authRequest } from '$lib/stores/auth.svelte';
import type { Page, TimelineEntry, TripDetail, TripInput, TripListItem, TripStatus } from './types';

export interface TripQuery {
	scope?: 'mine' | 'approvals' | 'all';
	status?: TripStatus[];
	destination_type_code?: string;
	country_code?: string;
	q?: string;
	start_date_from?: string;
	start_date_to?: string;
	page?: number;
	size?: number;
}

export function tripQueryString(query: TripQuery): string {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(query)) {
		if (value === undefined || value === null || value === '') continue;
		// status는 반복 파라미터다 (?status=A&status=B). 백엔드가 list로 받는다.
		if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
		else params.set(key, String(value));
	}
	const search = params.toString();
	return search ? `?${search}` : '';
}

export function listTrips(query: TripQuery = {}): Promise<Page<TripListItem>> {
	return authRequest<Page<TripListItem>>(`/api/v1/trips${tripQueryString(query)}`);
}

export function getTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}`);
}

export function createTrip(body: TripInput): Promise<TripDetail> {
	return authRequest<TripDetail>('/api/v1/trips', { method: 'POST', body });
}

export function updateTrip(id: number, body: Partial<TripInput>): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}`, { method: 'PATCH', body });
}

export function deleteTrip(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/trips/${id}`, { method: 'DELETE' });
}

export function submitTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/submit`, { method: 'POST' });
}

export function approveTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/approve`, { method: 'POST' });
}

export function rejectTrip(id: number, reason: string): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/reject`, {
		method: 'POST',
		body: { reason }
	});
}

export function reopenTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/reopen`, { method: 'POST' });
}

export function completeTrip(id: number): Promise<TripDetail> {
	return authRequest<TripDetail>(`/api/v1/trips/${id}/complete`, { method: 'POST' });
}

export function getTimeline(id: number): Promise<TimelineEntry[]> {
	return authRequest<TimelineEntry[]>(`/api/v1/trips/${id}/timeline`);
}
