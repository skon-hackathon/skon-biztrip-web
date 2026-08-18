import { ApiError } from '$lib/api/client';

export function describeError(error: unknown, fallback: string): string {
	return error instanceof ApiError ? error.message : fallback;
}

/**
 * Admin 화면 5개가 공유하는 목록 상태.
 *
 * 중복 제출 가드를 여기에 두는 이유: 화면마다 `if (submitting) return;`을 손으로 넣으면
 * 언젠가 하나를 빠뜨리고, 생성은 멱등하지 않아 그게 곧 중복 레코드다. 가드가 한 곳에
 * 있으면 테스트도 한 번만 쓰면 된다.
 */
export class AdminResource<T> {
	items = $state<T[]>([]);
	loading = $state(true);
	error = $state('');
	busy = $state(false);

	// 파라미터 프로퍼티(`private readonly loader`) 대신 명시적 필드를 쓴다 —
	// 룬 필드와 섞였을 때 컴파일 순서가 도구에 따라 달라지는 것을 피한다.
	private readonly loader: () => Promise<T[]>;

	constructor(loader: () => Promise<T[]>) {
		this.loader = loader;
	}

	async load(): Promise<void> {
		this.loading = true;
		try {
			this.items = await this.loader();
			this.error = '';
		} catch (error) {
			this.error = describeError(error, '목록을 불러오지 못했습니다');
		} finally {
			this.loading = false;
		}
	}

	/** 쓰기 1건 + 재조회. 진행 중이면 두 번째 호출을 버리고 false를 돌려준다. */
	async run(action: () => Promise<unknown>, failureMessage: string): Promise<boolean> {
		if (this.busy) return false;
		this.busy = true;
		this.error = '';
		try {
			await action();
			await this.load();
			return true;
		} catch (error) {
			this.error = describeError(error, failureMessage);
			return false;
		} finally {
			this.busy = false;
		}
	}
}
