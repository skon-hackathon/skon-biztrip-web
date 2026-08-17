import { describe, expect, it } from 'vitest';
import { tripQueryString } from './trips';

describe('tripQueryString', () => {
	it('returns an empty string for an empty query', () => {
		expect(tripQueryString({})).toBe('');
	});

	it('repeats the status parameter so the backend reads it as a list', () => {
		expect(tripQueryString({ status: ['SUBMITTED', 'APPROVED'] })).toBe(
			'?status=SUBMITTED&status=APPROVED'
		);
	});

	it('drops undefined and empty values instead of sending blanks', () => {
		expect(tripQueryString({ q: '', country_code: undefined, page: 2 })).toBe('?page=2');
	});

	it('keeps a zero-ish but meaningful value', () => {
		expect(tripQueryString({ scope: 'approvals', size: 12 })).toBe('?scope=approvals&size=12');
	});

	it('encodes values that need it', () => {
		expect(tripQueryString({ q: '울산 공장' })).toBe('?q=%EC%9A%B8%EC%82%B0+%EA%B3%B5%EC%9E%A5');
	});
});
