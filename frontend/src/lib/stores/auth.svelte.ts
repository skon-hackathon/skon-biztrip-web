import { ApiError, request, type RequestOptions } from '$lib/api/client';
import type { LoginResponse, User } from '$lib/api/types';

const TOKEN_KEY = 'skon.token';

class AuthStore {
	token = $state<string | null>(null);
	user = $state<User | null>(null);
	loading = $state(true);

	/**
	 * 세션이 끊겼을 때 화면을 정리할 콜백. +layout.svelte가 마운트 시 주입한다.
	 * 여기서 $app/navigation을 직접 import하면 vitest가 이 모듈을 못 불러온다.
	 */
	onUnauthorized: (() => void) | null = null;

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

/**
 * 인증이 필요한 모든 호출은 이걸 쓴다. raw `request`는 미인증 호출(login)과
 * 토큰을 명시적으로 넘기는 곳(restore)에서만 쓴다.
 *
 * 호출부마다 `{ token: auth.token }`를 손으로 붙이면 하나만 빠뜨려도 조용히 미인증
 * 요청이 나가고, 그 401은 진짜 인증 실패와 구분되지 않는다. 컴파일 타임 신호도 없다.
 *
 * JWT는 8시간 만료이고 refresh 토큰이 없다. 세션 중간에 만료되면 여기서 정리하지
 * 않는 한 헤더에 이름이 계속 보이고, SPA 내비게이션은 onMount를 다시 태우지 않아
 * 전체 새로고침 전까지 자가 복구가 안 된다.
 */
export async function authRequest<T>(
	path: string,
	options: Omit<RequestOptions, 'token'> = {}
): Promise<T> {
	try {
		return await request<T>(path, { ...options, token: auth.token });
	} catch (error) {
		if (error instanceof ApiError && error.status === 401) {
			auth.clear();
			auth.onUnauthorized?.();
		}
		throw error;
	}
}
