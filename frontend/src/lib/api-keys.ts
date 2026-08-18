import type { ApiKeyScope, ApiKeyState } from '$lib/api/types';

export const SCOPE_LABELS: Record<ApiKeyScope, string> = {
	'trips:read': '출장 조회',
	'trips:write': '출장 쓰기',
	'expenses:read': '정산 조회',
	'expenses:write': '정산 쓰기',
	'cards:read': '법인카드 조회',
	admin: '관리자 (Phase 5)'
};

/** 발급 폼의 표시 순서. 백엔드 ApiKeyScope 선언 순서와 같게 유지한다. */
export const SCOPE_ORDER: ApiKeyScope[] = [
	'trips:read',
	'trips:write',
	'expenses:read',
	'expenses:write',
	'cards:read',
	'admin'
];

export const KEY_STATE_LABELS: Record<ApiKeyState, string> = {
	ACTIVE: '사용중',
	REVOKED: '폐기됨',
	EXPIRED: '만료됨'
};

/** Badge.svelte의 tone과 그대로 맞춘다. */
export const KEY_STATE_TONES: Record<ApiKeyState, 'neutral' | 'primary' | 'success' | 'danger'> = {
	ACTIVE: 'success',
	REVOKED: 'danger',
	EXPIRED: 'neutral'
};

export const EXPIRY_OPTIONS: { value: string; label: string }[] = [
	{ value: '', label: '만료 없음' },
	{ value: '30', label: '30일' },
	{ value: '90', label: '90일' },
	{ value: '365', label: '365일' }
];

/**
 * `/developers` 가이드의 curl 예제. 셸 변수 두 개(`$SKON_BASE_URL`·`$SKON_API_KEY`)를
 * 쓰므로 사용자가 키를 문서에 붙여넣을 일이 없다.
 */
export function curlSnippet(input: {
	method: 'GET' | 'POST' | 'PATCH' | 'DELETE';
	path: string;
	body?: unknown;
}): string {
	const verb = input.method === 'GET' ? 'curl -s' : `curl -s -X ${input.method}`;
	const lines = [`${verb} "$SKON_BASE_URL${input.path}" \\`, '  -H "X-API-Key: $SKON_API_KEY"'];
	if (input.body !== undefined) {
		lines[lines.length - 1] += ' \\';
		lines.push('  -H "Content-Type: application/json" \\');
		lines.push(`  -d '${JSON.stringify(input.body)}'`);
	}
	return lines.join('\n');
}
