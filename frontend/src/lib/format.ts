/**
 * 날짜 문자열(YYYY-MM-DD)은 Date로 파싱하지 않는다. `new Date('2026-08-17')`은 UTC
 * 자정으로 해석돼 음수 오프셋 타임존에서 하루 밀린다. 문자열을 그대로 자른다.
 */
function parts(isoDate: string): [string, string, string] | null {
	const [year, month, day] = isoDate.split('-');
	return year && month && day ? [year, month, day] : null;
}

/** 시각은 KST로 고정 렌더한다 — 실행 머신의 TZ에 따라 값이 달라지면 안 된다. */
const KST_DATETIME = new Intl.DateTimeFormat('sv-SE', {
	timeZone: 'Asia/Seoul',
	year: 'numeric',
	month: '2-digit',
	day: '2-digit',
	hour: '2-digit',
	minute: '2-digit',
	hour12: false
});

export function formatDate(isoDate: string): string {
	const value = parts(isoDate);
	return value ? value.join('.') : '';
}

export function formatDateRange(startDate: string, endDate: string): string {
	const start = parts(startDate);
	const end = parts(endDate);
	if (!start || !end) return '';
	const [sy, sm, sd] = start;
	const [ey, em, ed] = end;
	if (sy === ey && sm === em) return `${sy}.${sm}.${sd} – ${ed}`;
	if (sy === ey) return `${sy}.${sm}.${sd} – ${em}.${ed}`;
	return `${sy}.${sm}.${sd} – ${ey}.${em}.${ed}`;
}

export function formatDateTime(iso: string): string {
	const parsed = new Date(iso);
	if (Number.isNaN(parsed.getTime())) return '';
	return KST_DATETIME.format(parsed).replaceAll('-', '.');
}

/** 금액은 API가 Decimal을 문자열로 보낸다 ("450000.00"). */
export function formatKrw(amount: string | number): string {
	const value = typeof amount === 'string' ? Number(amount) : amount;
	if (!Number.isFinite(value)) return '-';
	return `${new Intl.NumberFormat('ko-KR').format(Math.round(value))}원`;
}

export function tripLength(startDate: string, endDate: string): string {
	const nights = Math.round(
		(Date.parse(`${endDate}T00:00:00Z`) - Date.parse(`${startDate}T00:00:00Z`)) / 86_400_000
	);
	if (!Number.isFinite(nights) || nights <= 0) return '당일';
	return `${nights}박 ${nights + 1}일`;
}
