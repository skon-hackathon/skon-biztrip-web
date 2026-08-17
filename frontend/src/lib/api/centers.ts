import { authRequest } from '$lib/stores/auth.svelte';
import type { Center } from './types';

export function listCostCenters(): Promise<Center[]> {
	return authRequest<Center[]>('/api/v1/cost-centers');
}

export function listFundCenters(): Promise<Center[]> {
	return authRequest<Center[]>('/api/v1/fund-centers');
}
