<script lang="ts">
	import { ApiError } from '$lib/api/client';
	import { listTrips } from '$lib/api/trips';
	import type { Page, TripListItem, TripStatus } from '$lib/api/types';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TripCard from '$lib/components/TripCard.svelte';
	import { TRIP_STATUS_LABELS } from '$lib/trip-status';

	const TABS: { value: TripStatus | 'ALL'; label: string }[] = [
		{ value: 'SUBMITTED', label: '결재 대기' },
		{ value: 'APPROVED', label: TRIP_STATUS_LABELS.APPROVED },
		{ value: 'REJECTED', label: TRIP_STATUS_LABELS.REJECTED },
		{ value: 'ALL', label: '전체' }
	];

	let active = $state<TripStatus | 'ALL'>('SUBMITTED');
	let result = $state<Page<TripListItem> | null>(null);
	let loading = $state(true);
	let errorMessage = $state('');

	$effect(() => {
		const status = active;
		void load(status);
	});

	async function load(status: TripStatus | 'ALL'): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			result = await listTrips({
				scope: 'approvals',
				status: status === 'ALL' ? undefined : [status],
				size: 24
			});
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '결재함을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}
</script>

<h1 class="text-display-xl">결재함</h1>
<p class="mt-2 text-body-md text-muted">내가 결재자로 지정된 출장입니다.</p>

<div class="mt-6 flex gap-2">
	{#each TABS as tab (tab.value)}
		<button
			onclick={() => (active = tab.value)}
			aria-pressed={active === tab.value}
			class="h-10 rounded-full border px-4 text-button-sm {active === tab.value
				? 'border-ink bg-ink text-white'
				: 'border-hairline text-ink hover:shadow-float'}"
		>
			{tab.label}
		</button>
	{/each}
</div>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">{result.total}건</p>
	<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
		{#each result.items as trip (trip.id)}
			<TripCard {trip} showOwner />
		{/each}
	</div>
{:else}
	<div class="mt-8">
		<EmptyState
			title="결재할 출장이 없습니다"
			description="상신된 출장이 도착하면 여기에 표시됩니다."
		/>
	</div>
{/if}
