import { afterEach, describe, expect, it, vi } from 'vitest';
import { auth, authRequest } from './auth.svelte';

const TOKEN_KEY = 'skon.token';

function createLocalStorageStub(initial: Record<string, string> = {}) {
	const store = new Map(Object.entries(initial));
	return {
		getItem: vi.fn((key: string) => (store.has(key) ? (store.get(key) as string) : null)),
		setItem: vi.fn((key: string, value: string) => {
			store.set(key, value);
		}),
		removeItem: vi.fn((key: string) => {
			store.delete(key);
		}),
		clear: vi.fn(() => store.clear())
	};
}

describe('auth.restore', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('clears token, user and stored token when /auth/me rejects', async () => {
		const storage = createLocalStorageStub({ [TOKEN_KEY]: 'stale-token' });
		vi.stubGlobal('localStorage', storage);
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(new Response('unauthorized', { status: 401 }))
		);

		await auth.restore();

		expect(auth.token).toBeNull();
		expect(auth.user).toBeNull();
		expect(storage.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
	});
});

function jsonResponse(body: unknown, status: number): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('authRequest', () => {
	afterEach(() => {
		auth.token = null;
		auth.user = null;
		auth.onUnauthorized = null;
		vi.unstubAllGlobals();
	});

	it('sends the stored token without the caller passing it', async () => {
		vi.stubGlobal('localStorage', createLocalStorageStub());
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }, 200));
		auth.token = 'live-token';

		await authRequest('/api/v1/trips', { fetchImpl: fetchMock });

		const [, init] = fetchMock.mock.calls[0];
		expect(init.headers.Authorization).toBe('Bearer live-token');
	});

	it('clears the session and calls onUnauthorized on 401', async () => {
		const storage = createLocalStorageStub({ [TOKEN_KEY]: 'expired' });
		vi.stubGlobal('localStorage', storage);
		const fetchMock = vi
			.fn()
			.mockResolvedValue(
				jsonResponse({ error: { code: 'TOKEN_EXPIRED', message: '만료' } }, 401)
			);
		const onUnauthorized = vi.fn();
		auth.token = 'expired';
		auth.user = { id: 1 } as never;
		auth.onUnauthorized = onUnauthorized;

		await expect(authRequest('/api/v1/trips', { fetchImpl: fetchMock })).rejects.toMatchObject({
			status: 401
		});

		expect(auth.token).toBeNull();
		expect(auth.user).toBeNull();
		expect(storage.removeItem).toHaveBeenCalledWith(TOKEN_KEY);
		expect(onUnauthorized).toHaveBeenCalledTimes(1);
	});

	it('leaves the session alone for non-401 failures', async () => {
		vi.stubGlobal('localStorage', createLocalStorageStub());
		const fetchMock = vi
			.fn()
			.mockResolvedValue(
				jsonResponse({ error: { code: 'TRIP_NOT_FOUND', message: '없음' } }, 404)
			);
		const onUnauthorized = vi.fn();
		auth.token = 'live-token';
		auth.onUnauthorized = onUnauthorized;

		await expect(authRequest('/api/v1/trips/1', { fetchImpl: fetchMock })).rejects.toMatchObject({
			status: 404
		});

		expect(auth.token).toBe('live-token');
		expect(onUnauthorized).not.toHaveBeenCalled();
	});

	it('survives a missing onUnauthorized callback', async () => {
		vi.stubGlobal('localStorage', createLocalStorageStub());
		const fetchMock = vi
			.fn()
			.mockResolvedValue(jsonResponse({ error: { code: 'TOKEN_EXPIRED', message: '만료' } }, 401));
		auth.token = 'expired';

		await expect(authRequest('/api/v1/trips', { fetchImpl: fetchMock })).rejects.toMatchObject({
			status: 401
		});

		expect(auth.token).toBeNull();
	});
});
