import type { Department, UserRole, UserStatus } from '$lib/api/types';

/** Admin 서브탭. `/admin` 레이아웃이 그린다. */
export const ADMIN_TABS = [
	{ href: '/admin/codes', label: '공통코드' },
	{ href: '/admin/centers', label: '센터' },
	{ href: '/admin/departments', label: '부서' },
	{ href: '/admin/users', label: '사용자' },
	{ href: '/admin/cards', label: '법인카드' }
] as const;

export const ROLE_LABELS: Record<UserRole, string> = {
	EMPLOYEE: '사원',
	MANAGER: '결재자',
	ADMIN: '관리자'
};

export const STATUS_LABELS: Record<UserStatus, string> = {
	PENDING: '승인 대기',
	ACTIVE: '활성',
	REJECTED: '거절됨'
};

export function activeLabel(isActive: boolean): string {
	return isActive ? '사용' : '중지';
}

/** Select는 문자열 value만 다루므로 id를 문자열로 낮춘다. */
export function departmentOptions(
	departments: Department[],
	options: { noneLabel?: string } = {}
): { value: string; label: string }[] {
	const rows = departments.map((department) => ({
		value: String(department.id),
		label: `${department.code} · ${department.name}`
	}));
	return options.noneLabel ? [{ value: '', label: options.noneLabel }, ...rows] : rows;
}

/** 목록 표의 부서 칸. 알 수 없는 id를 조용히 빈칸으로 만들지 않는다 — 데이터 이상을 드러낸다. */
export function departmentNameById(departments: Department[], id: number | null): string {
	if (id === null) return '—';
	return departments.find((department) => department.id === id)?.name ?? `#${id}`;
}
