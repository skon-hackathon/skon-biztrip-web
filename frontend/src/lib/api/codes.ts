import { authRequest } from '$lib/stores/auth.svelte';
import type { CodeGroup } from './types';

export function listCodeGroups(): Promise<CodeGroup[]> {
	return authRequest<CodeGroup[]>('/api/v1/codes');
}

export function getCodeGroup(groupCode: string): Promise<CodeGroup> {
	return authRequest<CodeGroup>(`/api/v1/codes/${groupCode}`);
}

/** 폼이 쓰기 좋게 group_code를 키로 하는 맵으로 접는다. */
export function byGroupCode(groups: CodeGroup[]): Record<string, CodeGroup> {
	return Object.fromEntries(groups.map((group) => [group.group_code, group]));
}
