import { describe, expect, it } from 'vitest';
import { formatDate, formatDateRange, formatDateTime, formatKrw, tripLength } from './format';

describe('formatDate', () => {
	it('renders an ISO date as dotted numbers', () => {
		expect(formatDate('2026-08-17')).toBe('2026.08.17');
	});

	it('returns an empty string for junk', () => {
		expect(formatDate('')).toBe('');
	});

	it('does not shift the day regardless of the host timezone', () => {
		// new Date('2026-01-01')로 파싱하면 UTC 자정이라 음수 오프셋에서 2025.12.31이 된다.
		expect(formatDate('2026-01-01')).toBe('2026.01.01');
	});
});

describe('formatDateRange', () => {
	it('collapses the shared year and month', () => {
		expect(formatDateRange('2026-08-17', '2026-08-19')).toBe('2026.08.17 – 19');
	});

	it('collapses only the year when months differ', () => {
		expect(formatDateRange('2026-08-30', '2026-09-02')).toBe('2026.08.30 – 09.02');
	});

	it('keeps both years when they differ', () => {
		expect(formatDateRange('2026-12-30', '2027-01-02')).toBe('2026.12.30 – 2027.01.02');
	});
});

describe('formatDateTime', () => {
	// 타임존을 Asia/Seoul로 고정했으므로 실행 머신의 TZ와 무관하게 같은 값이 나온다.
	it('renders an instant in KST', () => {
		expect(formatDateTime('2026-08-17T05:30:00Z')).toBe('2026.08.17 14:30');
	});

	it('crosses the date boundary into KST', () => {
		expect(formatDateTime('2026-08-16T16:00:00Z')).toBe('2026.08.17 01:00');
	});

	it('returns an empty string for an unparsable value', () => {
		expect(formatDateTime('nope')).toBe('');
	});
});

describe('formatKrw', () => {
	it('accepts the decimal string the API sends', () => {
		expect(formatKrw('1200000.00')).toBe('1,200,000원');
	});

	it('accepts a number', () => {
		expect(formatKrw(4500)).toBe('4,500원');
	});

	it('falls back for non-numeric input', () => {
		expect(formatKrw('abc')).toBe('-');
	});

	it('renders zero rather than falling back', () => {
		expect(formatKrw('0')).toBe('0원');
	});
});

describe('tripLength', () => {
	it('labels a same-day trip', () => {
		expect(tripLength('2026-08-17', '2026-08-17')).toBe('당일');
	});

	it('counts nights and days', () => {
		expect(tripLength('2026-08-17', '2026-08-19')).toBe('2박 3일');
	});

	it('counts across a month boundary', () => {
		expect(tripLength('2026-08-30', '2026-09-02')).toBe('3박 4일');
	});
});
