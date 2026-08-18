import { describe, expect, it } from 'vitest';
import { ROLE_LABELS, activeLabel, departmentNameById, departmentOptions } from './admin';
import type { Department } from '$lib/api/types';

const departments: Department[] = [
	{ id: 1, code: 'D100', name: '연구소', parent_id: null },
	{ id: 2, code: 'D110', name: '배터리연구팀', parent_id: 1 }
];

describe('departmentOptions', () => {
	it('labels options with code and name', () => {
		expect(departmentOptions(departments)).toEqual([
			{ value: '1', label: 'D100 · 연구소' },
			{ value: '2', label: 'D110 · 배터리연구팀' }
		]);
	});

	it('can prepend a none option for nullable fields', () => {
		expect(departmentOptions(departments, { noneLabel: '상위 없음' })[0]).toEqual({
			value: '',
			label: '상위 없음'
		});
	});
});

describe('departmentNameById', () => {
	it('resolves a name', () => {
		expect(departmentNameById(departments, 2)).toBe('배터리연구팀');
	});

	it('shows a dash for null', () => {
		expect(departmentNameById(departments, null)).toBe('—');
	});

	it('shows the raw id when the department is unknown', () => {
		expect(departmentNameById(departments, 99)).toBe('#99');
	});
});

describe('labels', () => {
	it('translates roles', () => {
		expect(ROLE_LABELS.MANAGER).toBe('결재자');
	});

	it('translates the active flag', () => {
		expect(activeLabel(true)).toBe('사용');
		expect(activeLabel(false)).toBe('중지');
	});
});
