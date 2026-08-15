export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string,
		public field: string | null = null
	) {
		super(message);
		this.name = 'ApiError';
	}
}

interface RequestOptions {
	method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
	body?: unknown;
	token?: string | null;
	fetchImpl?: typeof fetch;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	const { method = 'GET', body, token, fetchImpl = fetch } = options;

	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (token) headers.Authorization = `Bearer ${token}`;

	const response = await fetchImpl(path, {
		method,
		headers,
		body: body === undefined ? undefined : JSON.stringify(body)
	});

	if (!response.ok) {
		let code = 'UNKNOWN';
		let message = `요청이 실패했습니다 (${response.status})`;
		let field: string | null = null;
		try {
			const parsed = await response.json();
			if (parsed?.error?.code) {
				code = parsed.error.code;
				message = parsed.error.message;
				field = parsed.error.field ?? null;
			}
		} catch {
			// 본문이 JSON이 아니면 기본 메시지를 유지한다
		}
		throw new ApiError(response.status, code, message, field);
	}

	if (response.status === 204) return undefined as T;
	return (await response.json()) as T;
}
