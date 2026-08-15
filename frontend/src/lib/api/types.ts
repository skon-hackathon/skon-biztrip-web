export type UserRole = 'EMPLOYEE' | 'MANAGER' | 'ADMIN';

export interface User {
	id: number;
	email: string;
	name: string;
	employee_no: string;
	position_code: string;
	role: UserRole;
	department_id: number;
	department_name: string;
	manager_id: number | null;
}

export interface LoginResponse {
	access_token: string;
	token_type: string;
	user: User;
}
