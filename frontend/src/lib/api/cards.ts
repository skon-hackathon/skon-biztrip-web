import { authRequest } from '$lib/stores/auth.svelte';
import { toQueryString } from './query';
import type { CardItem, CardTransactionItem, Page } from './types';

export interface CardTxnQuery {
	card_id?: number;
	approved_from?: string;
	approved_to?: string;
	merchant_category_code?: string;
	q?: string;
	include_cancelled?: boolean;
	page?: number;
	size?: number;
}

export function listCards(): Promise<CardItem[]> {
	return authRequest<CardItem[]>('/api/v1/cards');
}

export function listCardTransactions(
	query: CardTxnQuery = {}
): Promise<Page<CardTransactionItem>> {
	return authRequest<Page<CardTransactionItem>>(
		`/api/v1/card-transactions${toQueryString(query as Record<string, unknown>)}`
	);
}
