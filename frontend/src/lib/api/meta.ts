import { authRequest } from '$lib/stores/auth.svelte';
import type { ScopeInfo } from './types';

export function listScopes(): Promise<ScopeInfo[]> {
	return authRequest<ScopeInfo[]>('/api/v1/scopes');
}
