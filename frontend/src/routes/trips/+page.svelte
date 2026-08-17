<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { listTrips, type TripQuery } from '$lib/api/trips';
	import type { Page, TripListItem, TripStatus } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import TripCard from '$lib/components/TripCard.svelte';

	const SIZE = 12;

	let result = $state<Page<TripListItem> | null>(null);
	let loading = $state(true);
	let errorMessage = $state('');

	let q = $state(page.url.searchParams.get('q') ?? '');
	let startDateFrom = $state(page.url.searchParams.get('start_date_from') ?? '');
	let status = $state<TripStatus | ''>((page.url.searchParams.get('status') as TripStatus) ?? '');

	const currentPage = $derived(Number(page.url.searchParams.get('page') ?? '1'));
	const totalPages = $derived(result ? Math.max(1, Math.ceil(result.total / SIZE)) : 1);

	// page.url.search만 의존성으로 읽는다. 아래에서 대입하는 result/loading은 이 effect가
	// 읽지 않으므로 다시 트리거되지 않는다.
	$effect(() => {
		const search = page.url.search;
		void load(new URLSearchParams(search));
	});

	async function load(params: URLSearchParams): Promise<void> {
		loading = true;
		errorMessage = '';
		const query: TripQuery = { page: Number(params.get('page') ?? '1'), size: SIZE };
		const searchText = params.get('q');
		const from = params.get('start_date_from');
		const statusValue = params.get('status');
		if (searchText) query.q = searchText;
		if (from) query.start_date_from = from;
		if (statusValue) query.status = [statusValue as TripStatus];
		try {
			result = await listTrips(query);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '목록을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function applyFilters(): void {
		const params = new URLSearchParams();
		if (q) params.set('q', q);
		if (startDateFrom) params.set('start_date_from', startDateFrom);
		if (status) params.set('status', status);
		goto(`/trips${params.toString() ? `?${params}` : ''}`);
	}

	function goToPage(next: number): void {
		const params = new URLSearchParams(page.url.searchParams);
		params.set('page', String(next));
		goto(`/trips?${params}`);
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">내 출장</h1>
	<Button onclick={() => goto('/trips/new')}>출장 신청</Button>
</div>

<div class="mt-6">
	<FilterBar bind:q bind:startDateFrom bind:status onsearch={applyFilters} />
</div>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">전체 {result.total}건</p>
	<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
		{#each result.items as trip (trip.id)}
			<TripCard {trip} />
		{/each}
	</div>

	{#if totalPages > 1}
		<div class="mt-8 flex items-center justify-center gap-4">
			<Button
				variant="secondary"
				disabled={currentPage <= 1}
				onclick={() => goToPage(currentPage - 1)}>이전</Button
			>
			<span class="text-body-sm text-muted">{currentPage} / {totalPages}</span>
			<Button
				variant="secondary"
				disabled={currentPage >= totalPages}
				onclick={() => goToPage(currentPage + 1)}>다음</Button
			>
		</div>
	{/if}
{:else}
	<div class="mt-8">
		<EmptyState title="출장이 없습니다" description="조건을 바꾸거나 새 출장을 신청해 보세요.">
			{#snippet action()}
				<Button onclick={() => goto('/trips/new')}>출장 신청</Button>
			{/snippet}
		</EmptyState>
	</div>
{/if}
