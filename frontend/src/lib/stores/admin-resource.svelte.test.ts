import { describe, expect, it, vi } from 'vitest';
import { AdminResource } from './admin-resource.svelte';
import { ApiError } from '$lib/api/client';

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason: unknown) => void;
	const promise = new Promise<T>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

describe('AdminResource.load', () => {
	it('fills items and clears loading', async () => {
		const resource = new AdminResource(async () => [1, 2, 3]);

		await resource.load();

		expect(resource.items).toEqual([1, 2, 3]);
		expect(resource.loading).toBe(false);
		expect(resource.error).toBe('');
	});

	it('keeps the ApiError message', async () => {
		const resource = new AdminResource(async () => {
			throw new ApiError(409, 'HAS_DEPENDENTS', '참조가 있어 삭제할 수 없습니다');
		});

		await resource.load();

		expect(resource.error).toBe('참조가 있어 삭제할 수 없습니다');
		expect(resource.loading).toBe(false);
	});

	it('falls back for non-ApiError failures', async () => {
		const resource = new AdminResource(async () => {
			throw new Error('네트워크');
		});

		await resource.load();

		expect(resource.error).toBe('목록을 불러오지 못했습니다');
	});
});

describe('AdminResource.run', () => {
	it('reloads after a successful write', async () => {
		const loader = vi.fn(async () => ['a']);
		const resource = new AdminResource(loader);
		await resource.load();
		loader.mockClear();

		const ok = await resource.run(async () => undefined, '실패');

		expect(ok).toBe(true);
		expect(loader).toHaveBeenCalledTimes(1);
	});

	it('drops a second write while the first is in flight', async () => {
		// 버튼 disabled만으로는 form.requestSubmit() 경로를 막지 못한다.
		// 생성은 멱등하지 않으므로 두 번째 POST가 곧 중복 레코드다.
		const gate = deferred<void>();
		const action = vi.fn(async () => {
			await gate.promise;
		});
		const resource = new AdminResource(async () => []);

		const first = resource.run(action, '실패');
		const second = await resource.run(action, '실패');
		gate.resolve();
		await first;

		expect(second).toBe(false);
		expect(action).toHaveBeenCalledTimes(1);
	});

	it('reports failure and stays usable', async () => {
		const resource = new AdminResource(async () => []);

		const ok = await resource.run(async () => {
			throw new ApiError(400, 'INVALID_CODE', '코드가 잘못되었습니다');
		}, '실패');

		expect(ok).toBe(false);
		expect(resource.error).toBe('코드가 잘못되었습니다');
		expect(resource.busy).toBe(false);
	});
});
