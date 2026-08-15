import { request } from '$lib/api/client';
import type { LoginResponse, User } from '$lib/api/types';

const TOKEN_KEY = 'skon.token';

class AuthStore {
	token = $state<string | null>(null);
	user = $state<User | null>(null);
	loading = $state(true);

	async restore(): Promise<void> {
		this.loading = true;
		const stored = localStorage.getItem(TOKEN_KEY);
		if (!stored) {
			this.loading = false;
			return;
		}
		this.token = stored;
		try {
			this.user = await request<User>('/api/v1/auth/me', { token: stored });
		} catch {
			this.clear();
		}
		this.loading = false;
	}

	async login(email: string, password: string): Promise<void> {
		this.loading = true;
		try {
			const result = await request<LoginResponse>('/api/v1/auth/login', {
				method: 'POST',
				body: { email, password }
			});
			this.token = result.access_token;
			this.user = result.user;
			localStorage.setItem(TOKEN_KEY, result.access_token);
		} finally {
			this.loading = false;
		}
	}

	clear(): void {
		this.token = null;
		this.user = null;
		localStorage.removeItem(TOKEN_KEY);
	}
}

export const auth = new AuthStore();
