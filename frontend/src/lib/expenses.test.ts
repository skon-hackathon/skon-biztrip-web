import { describe, expect, it } from 'vitest';
import { EXPENSE_STATUS_LABELS, resolveCenter, sumIncluded } from './expenses';

describe('resolveCenter', () => {
	it('uses the item override when present', () => {
		expect(resolveCenter('CC2040', 'CC2030')).toEqual({ code: 'CC2040', inherited: false });
	});

	it('falls back to the report value and marks it inherited', () => {
		expect(resolveCenter(null, 'CC2030')).toEqual({ code: 'CC2030', inherited: true });
	});

	it('reports nothing when neither level has a value', () => {
		expect(resolveCenter(null, null)).toEqual({ code: null, inherited: true });
	});
});

describe('sumIncluded', () => {
	it('skips excluded items', () => {
		expect(
			sumIncluded([
				{ amount_krw: '10000.00', is_excluded: false },
				{ amount_krw: '5000.00', is_excluded: true }
			])
		).toBe(10000);
	});

	it('returns 0 for an empty list', () => {
		expect(sumIncluded([])).toBe(0);
	});
});

describe('EXPENSE_STATUS_LABELS', () => {
	it('covers every status the API can return', () => {
		expect(Object.keys(EXPENSE_STATUS_LABELS).sort()).toEqual([
			'APPROVED',
			'DRAFT',
			'REJECTED',
			'SUBMITTED'
		]);
	});
});
