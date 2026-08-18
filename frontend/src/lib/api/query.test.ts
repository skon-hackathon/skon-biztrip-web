import { describe, expect, it } from 'vitest';
import { toQueryString } from './query';

describe('toQueryString', () => {
	it('returns an empty string for an empty query', () => {
		expect(toQueryString({})).toBe('');
	});

	it('repeats array values so the backend reads them as a list', () => {
		expect(toQueryString({ status: ['SUBMITTED', 'APPROVED'] })).toBe(
			'?status=SUBMITTED&status=APPROVED'
		);
	});

	it('drops undefined, null and empty string values', () => {
		expect(toQueryString({ q: '', card_id: undefined, page: 2 })).toBe('?page=2');
	});

	it('keeps false so a boolean filter can be turned off explicitly', () => {
		expect(toQueryString({ include_cancelled: false })).toBe('?include_cancelled=false');
	});
});
