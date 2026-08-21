import { describe, expect, it } from 'vitest';
import { isPublicPath, loginPathFor, safeRedirect } from './nav';

describe('isPublicPath', () => {
	it('가입 화면은 로그인 없이 열린다', () => {
		expect(isPublicPath('/signup')).toBe(true);
	});

	it('matches the public route itself', () => {
		expect(isPublicPath('/login')).toBe(true);
	});

	it('matches children of a public route', () => {
		expect(isPublicPath('/login/reset')).toBe(true);
	});

	it('does not match a route that merely shares a prefix', () => {
		expect(isPublicPath('/login-help')).toBe(false);
	});

	it('rejects protected routes', () => {
		expect(isPublicPath('/trips/42')).toBe(false);
	});
});

describe('safeRedirect', () => {
	it('keeps an internal path', () => {
		expect(safeRedirect('/trips/42?tab=timeline')).toBe('/trips/42?tab=timeline');
	});

	it('falls back to root when absent', () => {
		expect(safeRedirect(null)).toBe('/');
	});

	it('rejects protocol-relative URLs that would leave the site', () => {
		expect(safeRedirect('//evil.example/phish')).toBe('/');
	});

	it('rejects absolute URLs', () => {
		expect(safeRedirect('https://evil.example')).toBe('/');
	});

	it('rejects an empty string', () => {
		expect(safeRedirect('')).toBe('/');
	});
});

describe('loginPathFor', () => {
	it('encodes the target so query strings survive', () => {
		expect(loginPathFor('/trips', '?status=SUBMITTED')).toBe(
			'/login?redirect=%2Ftrips%3Fstatus%3DSUBMITTED'
		);
	});

	it('does not add a redirect for the root path', () => {
		expect(loginPathFor('/', '')).toBe('/login');
	});

	it('round-trips through safeRedirect', () => {
		const path = loginPathFor('/trips/42', '?x=1');
		const target = new URLSearchParams(path.split('?')[1]).get('redirect');

		expect(safeRedirect(target)).toBe('/trips/42?x=1');
	});
});
