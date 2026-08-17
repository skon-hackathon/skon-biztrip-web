import { authRequest } from '$lib/stores/auth.svelte';
import type { NotificationItem, NotificationPage } from './types';

export function listNotifications(
	options: { unread_only?: boolean; page?: number; size?: number } = {}
): Promise<NotificationPage> {
	const params = new URLSearchParams();
	if (options.unread_only) params.set('unread_only', 'true');
	if (options.page) params.set('page', String(options.page));
	if (options.size) params.set('size', String(options.size));
	const search = params.toString();
	return authRequest<NotificationPage>(`/api/v1/notifications${search ? `?${search}` : ''}`);
}

export function markNotificationRead(id: number): Promise<NotificationItem> {
	return authRequest<NotificationItem>(`/api/v1/notifications/${id}/read`, { method: 'POST' });
}
