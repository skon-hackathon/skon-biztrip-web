import { afterEach, describe, expect, it, vi } from 'vitest';
import { auth } from './auth.svelte';

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
