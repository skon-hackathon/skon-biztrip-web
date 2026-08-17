<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { getTrip, updateTrip } from '$lib/api/trips';
	import type { TripInput } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import TripForm from '$lib/components/TripForm.svelte';

	let initial = $state<TripInput | null>(null);
	let values = $state<TripInput | null>(null);
	let loading = $state(true);
	let loadError = $state('');
	let errorMessage = $state('');
	let submitting = $state(false);

	const tripId = $derived(Number(page.params.id));

	$effect(() => {
		const id = tripId;
		void load(id);
	});

	async function load(id: number): Promise<void> {
		loading = true;
		loadError = '';
		try {
			const trip = await getTrip(id);
			initial = {
				title: trip.title,
				purpose_code: trip.purpose_code,
				purpose_detail: trip.purpose_detail,
				destination_type_code: trip.destination_type_code,
				country_code: trip.country_code,
				city: trip.city,
				start_date: trip.start_date,
				end_date: trip.end_date,
				transport_code: trip.transport_code,
				accommodation_code: trip.accommodation_code,
				cost_center_code: trip.cost_center_code,
				// API는 Decimal을 "450000.00" 문자열로 보낸다. number 입력에 그대로 넣으면
				// 소수점이 보이므로 정수 문자열로 다듬는다.
				estimated_cost: String(Math.round(Number(trip.estimated_cost)))
			};
			values = { ...initial };
		} catch (error) {
			loadError = error instanceof ApiError ? error.message : '출장을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	async function save(): Promise<void> {
		if (submitting || !values) return;
		submitting = true;
		errorMessage = '';
		try {
			await updateTrip(tripId, values);
			await goto(`/trips/${tripId}`);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '저장하지 못했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<h1 class="text-display-xl">출장 수정</h1>

{#if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if loadError}
	<p class="mt-8 text-body-sm text-error" role="alert">{loadError}</p>
{:else if initial}
	<div class="mt-8 max-w-[720px]">
		<TripForm {initial} onchange={(next) => (values = next)} />

		{#if errorMessage}
			<p class="mt-6 text-body-sm text-error" role="alert">{errorMessage}</p>
		{/if}

		<div class="mt-8 flex gap-3">
			<Button variant="secondary" disabled={submitting} onclick={() => goto(`/trips/${tripId}`)}>
				취소
			</Button>
			<Button disabled={submitting} onclick={save}>
				{submitting ? '저장 중…' : '저장'}
			</Button>
		</div>
	</div>
{/if}
