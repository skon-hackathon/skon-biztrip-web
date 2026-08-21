import { request } from './client';
import type { PublicDepartment, SignupInput, SignupResult } from './types';

// 미인증 호출이므로 authRequest가 아니라 raw request를 쓴다. login과 같은 부류이며,
// 이 두 경로 외에 raw request를 늘리지 않는다 — 토큰을 손으로 붙이는 곳이 생기면
// 하나만 빠뜨려도 조용히 미인증 요청이 나가고 그 401은 진짜 인증 실패와 구분되지 않는다.
export function listPublicDepartments(): Promise<PublicDepartment[]> {
	return request<PublicDepartment[]>('/api/v1/auth/departments');
}

export function signup(input: SignupInput): Promise<SignupResult> {
	return request<SignupResult>('/api/v1/auth/signup', { method: 'POST', body: input });
}
