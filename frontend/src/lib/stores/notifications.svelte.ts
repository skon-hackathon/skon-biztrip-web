import { listNotifications } from '$lib/api/notifications';

class NotificationStore {
	unread = $state(0);

	/** 실패는 삼킨다 — 헤더 뱃지 때문에 화면 전체가 에러로 덮이면 안 된다. */
	async refresh(): Promise<void> {
		try {
			const page = await listNotifications({ size: 1 });
			this.unread = page.unread;
		} catch {
			this.unread = 0;
		}
	}

	reset(): void {
		this.unread = 0;
	}
}

export const notifications = new NotificationStore();
