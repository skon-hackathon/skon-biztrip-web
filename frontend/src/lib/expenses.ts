import type { ExpenseStatus } from '$lib/api/types';

export const EXPENSE_STATUS_LABELS: Record<ExpenseStatus, string> = {
	DRAFT: '임시저장',
	SUBMITTED: '승인대기',
	APPROVED: '승인완료',
	REJECTED: '반려'
};

/** Badge.svelte의 tone과 그대로 맞춘다. */
export const EXPENSE_STATUS_TONES: Record<
	ExpenseStatus,
	'neutral' | 'primary' | 'success' | 'danger'
> = {
	DRAFT: 'neutral',
	SUBMITTED: 'primary',
	APPROVED: 'success',
	REJECTED: 'danger'
};

export const EXPENSE_STATUS_ORDER: ExpenseStatus[] = ['DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED'];

/**
 * FC/CC 상속 규칙(spec 5.5)의 화면 표현. 항목 값이 없으면 리포트 값을 쓰고, 그 사실을
 * `inherited`로 알려 "상속" 표시를 붙일 수 있게 한다. 백엔드도 같은 규칙을
 * `effective_*_code`로 내려주므로 두 값이 어긋나면 둘 중 하나가 틀린 것이다.
 */
export function resolveCenter(
	itemCode: string | null,
	reportCode: string | null
): { code: string | null; inherited: boolean } {
	if (itemCode !== null) return { code: itemCode, inherited: false };
	return { code: reportCode, inherited: true };
}

/** 금액은 API가 Decimal을 문자열로 보낸다 ("450000.00"). */
export function sumIncluded(items: { amount_krw: string; is_excluded: boolean }[]): number {
	return items
		.filter((item) => !item.is_excluded)
		.reduce((total, item) => total + Number(item.amount_krw), 0);
}
