import { describe, expect, it, vi } from 'vitest';
import { ApiError, request } from './client';

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('request', () => {
	it('attaches bearer token when provided', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));

		await request('/api/v1/auth/me', { token: 'abc', fetchImpl: fetchMock });

		const [, init] = fetchMock.mock.calls[0];
		expect(init.headers.Authorization).toBe('Bearer abc');
	});

	it('omits authorization header without token', async () => {
		const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));

		await request('/api/v1/health', { fetchImpl: fetchMock });

		const [, init] = fetchMock.mock.calls[0];
		expect(init.headers.Authorization).toBeUndefined();
	});

	it('throws ApiError carrying the unified error body', async () => {
		const fetchMock = vi.fn().mockResolvedValue(
			jsonResponse(
				{ error: { code: 'INVALID_CREDENTIALS', message: '이메일 또는 비밀번호가 올바르지 않습니다', field: null } },
				401
			)
		);

		await expect(request('/api/v1/auth/login', { fetchImpl: fetchMock })).rejects.toMatchObject({
			status: 401,
			code: 'INVALID_CREDENTIALS',
			message: '이메일 또는 비밀번호가 올바르지 않습니다'
		});
	});

	it('falls back to a generic ApiError when body is not our shape', async () => {
		const fetchMock = vi.fn().mockResolvedValue(new Response('gateway down', { status: 502 }));

		const error = await request<never>('/api/v1/health', { fetchImpl: fetchMock }).catch((e) => e);

		expect(error).toBeInstanceOf(ApiError);
		expect(error.status).toBe(502);
		expect(error.code).toBe('UNKNOWN');
	});
});
