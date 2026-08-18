import { authRequest } from '$lib/stores/auth.svelte';
import type { ApiKeyCreated, ApiKeyScope, ApiKeySummary } from './types';

export interface ApiKeyCreateInput {
	name: string;
	scopes: ApiKeyScope[];
	expires_in_days?: number | null;
}

export function listApiKeys(): Promise<ApiKeySummary[]> {
	return authRequest<ApiKeySummary[]>('/api/v1/api-keys');
}

export function createApiKey(input: ApiKeyCreateInput): Promise<ApiKeyCreated> {
	return authRequest<ApiKeyCreated>('/api/v1/api-keys', { method: 'POST', body: input });
}

export function revokeApiKey(id: number): Promise<ApiKeySummary> {
	return authRequest<ApiKeySummary>(`/api/v1/api-keys/${id}/revoke`, { method: 'POST' });
}
