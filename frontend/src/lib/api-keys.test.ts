import { describe, expect, it } from 'vitest';
import { KEY_STATE_LABELS, KEY_STATE_TONES, SCOPE_LABELS, curlSnippet } from './api-keys';

describe('SCOPE_LABELS', () => {
	it('covers every scope the backend can return', () => {
		expect(Object.keys(SCOPE_LABELS).sort()).toEqual(
			['admin', 'cards:read', 'expenses:read', 'expenses:write', 'trips:read', 'trips:write'].sort()
		);
	});
});

describe('KEY_STATE_*', () => {
	it('covers every state', () => {
		expect(Object.keys(KEY_STATE_LABELS).sort()).toEqual(['ACTIVE', 'EXPIRED', 'REVOKED']);
		expect(Object.keys(KEY_STATE_TONES).sort()).toEqual(['ACTIVE', 'EXPIRED', 'REVOKED']);
	});
});

describe('curlSnippet', () => {
	it('builds a GET snippet with the key header', () => {
		expect(curlSnippet({ method: 'GET', path: '/api/v1/trips?scope=mine' })).toBe(
			[
				'curl -s "$SKON_BASE_URL/api/v1/trips?scope=mine" \\',
				'  -H "X-API-Key: $SKON_API_KEY"'
			].join('\n')
		);
	});

	it('adds the method, content type and body for writes', () => {
		expect(
			curlSnippet({ method: 'POST', path: '/api/v1/trips', body: { title: '울산 공장 점검' } })
		).toBe(
			[
				'curl -s -X POST "$SKON_BASE_URL/api/v1/trips" \\',
				'  -H "X-API-Key: $SKON_API_KEY" \\',
				'  -H "Content-Type: application/json" \\',
				`  -d '${JSON.stringify({ title: '울산 공장 점검' })}'`
			].join('\n')
		);
	});

	it('omits -X for GET so the snippet reads like the docs', () => {
		expect(curlSnippet({ method: 'GET', path: '/api/v1/cards' })).not.toContain('-X GET');
	});
});
