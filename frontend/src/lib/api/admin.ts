import { authRequest } from '$lib/stores/auth.svelte';
import { toQueryString } from './query';
import type {
	AdminCard,
	AdminCenter,
	AdminCode,
	AdminCodeGroup,
	AdminUser,
	AdminUserInput,
	AdminUserPatch,
	CenterKind,
	Department,
	DepartmentInput,
	Page
} from './types';

// --- 부서 -------------------------------------------------------------------

export function listDepartments(): Promise<Department[]> {
	return authRequest<Department[]>('/api/v1/admin/departments');
}

export function createDepartment(input: DepartmentInput): Promise<Department> {
	return authRequest<Department>('/api/v1/admin/departments', { method: 'POST', body: input });
}

export function updateDepartment(
	id: number,
	patch: Partial<DepartmentInput>
): Promise<Department> {
	return authRequest<Department>(`/api/v1/admin/departments/${id}`, {
		method: 'PATCH',
		body: patch
	});
}

export function deleteDepartment(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/departments/${id}`, { method: 'DELETE' });
}

// --- 공통코드 ---------------------------------------------------------------

export function listCodeGroups(): Promise<AdminCodeGroup[]> {
	return authRequest<AdminCodeGroup[]>('/api/v1/admin/code-groups');
}

export function createCodeGroup(input: {
	group_code: string;
	name: string;
	description?: string | null;
}): Promise<AdminCodeGroup> {
	return authRequest<AdminCodeGroup>('/api/v1/admin/code-groups', {
		method: 'POST',
		body: input
	});
}

export function updateCodeGroup(
	id: number,
	patch: { name?: string; description?: string | null; is_active?: boolean }
): Promise<AdminCodeGroup> {
	return authRequest<AdminCodeGroup>(`/api/v1/admin/code-groups/${id}`, {
		method: 'PATCH',
		body: patch
	});
}

export function deleteCodeGroup(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/code-groups/${id}`, { method: 'DELETE' });
}

export function createCode(
	groupId: number,
	input: { code: string; name: string; sort_order?: number }
): Promise<AdminCode> {
	return authRequest<AdminCode>(`/api/v1/admin/code-groups/${groupId}/codes`, {
		method: 'POST',
		body: input
	});
}

export function updateCode(
	id: number,
	patch: { name?: string; sort_order?: number; is_active?: boolean }
): Promise<AdminCode> {
	return authRequest<AdminCode>(`/api/v1/admin/codes/${id}`, { method: 'PATCH', body: patch });
}

export function deleteCode(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/codes/${id}`, { method: 'DELETE' });
}

// --- FC / CC ----------------------------------------------------------------

export function listCenters(kind: CenterKind): Promise<AdminCenter[]> {
	return authRequest<AdminCenter[]>(`/api/v1/admin/${kind}`);
}

export function createCenter(
	kind: CenterKind,
	input: { code: string; name: string; department_id?: number | null }
): Promise<AdminCenter> {
	return authRequest<AdminCenter>(`/api/v1/admin/${kind}`, { method: 'POST', body: input });
}

export function updateCenter(
	kind: CenterKind,
	id: number,
	patch: { name?: string; department_id?: number | null; is_active?: boolean }
): Promise<AdminCenter> {
	return authRequest<AdminCenter>(`/api/v1/admin/${kind}/${id}`, {
		method: 'PATCH',
		body: patch
	});
}

export function deleteCenter(kind: CenterKind, id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/${kind}/${id}`, { method: 'DELETE' });
}

// --- 사용자 -----------------------------------------------------------------

export function listUsers(
	query: { q?: string; page?: number; size?: number } = {}
): Promise<Page<AdminUser>> {
	return authRequest<Page<AdminUser>>(`/api/v1/admin/users${toQueryString(query)}`);
}

export function createUser(input: AdminUserInput): Promise<AdminUser> {
	return authRequest<AdminUser>('/api/v1/admin/users', { method: 'POST', body: input });
}

export function updateUser(id: number, patch: AdminUserPatch): Promise<AdminUser> {
	return authRequest<AdminUser>(`/api/v1/admin/users/${id}`, { method: 'PATCH', body: patch });
}

export function setUserPassword(id: number, password: string): Promise<void> {
	return authRequest<void>(`/api/v1/admin/users/${id}/password`, {
		method: 'POST',
		body: { password }
	});
}

// --- 법인카드 ---------------------------------------------------------------

export function listAdminCards(): Promise<AdminCard[]> {
	return authRequest<AdminCard[]>('/api/v1/admin/cards');
}

export function createAdminCard(input: {
	user_id: number;
	card_no_masked: string;
	brand: string;
}): Promise<AdminCard> {
	return authRequest<AdminCard>('/api/v1/admin/cards', { method: 'POST', body: input });
}

export function updateAdminCard(
	id: number,
	patch: { card_no_masked?: string; brand?: string; is_active?: boolean }
): Promise<AdminCard> {
	return authRequest<AdminCard>(`/api/v1/admin/cards/${id}`, { method: 'PATCH', body: patch });
}

export function deleteAdminCard(id: number): Promise<void> {
	return authRequest<void>(`/api/v1/admin/cards/${id}`, { method: 'DELETE' });
}
