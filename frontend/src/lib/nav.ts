/** 로그인 없이 볼 수 있는 라우트. 자식 경로까지 공개로 취급한다. */
const PUBLIC_PREFIXES = ['/login', '/signup'];

export function isPublicPath(pathname: string): boolean {
	return PUBLIC_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/**
 * 로그인 후 돌아갈 경로를 검증한다.
 * `//host` 형태는 브라우저가 프로토콜 상대 URL로 해석해 외부 사이트로 나가므로 막는다.
 */
export function safeRedirect(target: string | null): string {
	if (!target || !target.startsWith('/') || target.startsWith('//')) return '/';
	return target;
}

/** 가드가 보낼 로그인 경로. 원래 가려던 곳을 redirect 쿼리에 보존한다. */
export function loginPathFor(pathname: string, search: string): string {
	const target = `${pathname}${search}`;
	if (target === '/') return '/login';
	return `/login?redirect=${encodeURIComponent(target)}`;
}
