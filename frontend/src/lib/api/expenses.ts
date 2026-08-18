import { authRequest } from '$lib/stores/auth.svelte';
import { toQueryString } from './query';
import type {
	ExpenseItemInput,
	ExpenseItemPatch,
	ExpenseReportDetail,
	ExpenseReportListItem,
	ExpenseStatus,
	MatchCandidate,
	Page,
	TimelineEntry
} from './types';

export interface ExpenseQuery {
	scope?: 'mine' | 'approvals' | 'all';
	status?: ExpenseStatus[];
	q?: string;
	page?: number;
	size?: number;
}

export function listExpenses(query: ExpenseQuery = {}): Promise<Page<ExpenseReportListItem>> {
	return authRequest<Page<ExpenseReportListItem>>(
		`/api/v1/expenses${toQueryString(query as Record<string, unknown>)}`
	);
}

export function getExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}`);
}

export function createExpense(tripId: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>('/api/v1/expenses', {
		method: 'POST',
		body: { trip_id: tripId }
	});
}

export function updateExpense(
	id: number,
	body: { fund_center_code?: string | null; cost_center_code?: string | null }
): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}`, { method: 'PATCH', body });
}

export function getMatchCandidates(id: number): Promise<MatchCandidate[]> {
	return authRequest<MatchCandidate[]>(`/api/v1/expenses/${id}/match-candidates`);
}

export function getExpenseTimeline(id: number): Promise<TimelineEntry[]> {
	return authRequest<TimelineEntry[]>(`/api/v1/expenses/${id}/timeline`);
}

export function addExpenseItem(id: number, body: ExpenseItemInput): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/items`, {
		method: 'POST',
		body
	});
}

export function updateExpenseItem(
	itemId: number,
	body: ExpenseItemPatch
): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expense-items/${itemId}`, {
		method: 'PATCH',
		body
	});
}

export function deleteExpenseItem(itemId: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expense-items/${itemId}`, {
		method: 'DELETE'
	});
}

export function submitExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/submit`, { method: 'POST' });
}

export function approveExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/approve`, { method: 'POST' });
}

export function rejectExpense(id: number, reason: string): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/reject`, {
		method: 'POST',
		body: { reason }
	});
}

export function reopenExpense(id: number): Promise<ExpenseReportDetail> {
	return authRequest<ExpenseReportDetail>(`/api/v1/expenses/${id}/reopen`, { method: 'POST' });
}
