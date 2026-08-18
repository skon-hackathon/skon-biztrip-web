/**
 * 목록 API의 쿼리스트링 빌더. 배열은 반복 파라미터로 펴고(`?status=A&status=B`),
 * undefined·null·빈 문자열은 버린다. `false`는 버리지 않는다 — 불린 필터를 명시적으로
 * 끄는 요청과 "안 보냄"은 다르다.
 */
export function toQueryString(query: Record<string, unknown>): string {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(query)) {
		if (value === undefined || value === null || value === '') continue;
		if (Array.isArray(value)) value.forEach((item) => params.append(key, String(item)));
		else params.set(key, String(value));
	}
	const search = params.toString();
	return search ? `?${search}` : '';
}
