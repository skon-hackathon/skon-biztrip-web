<script lang="ts">
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { createTrip, submitTrip } from '$lib/api/trips';
	import type { TripInput } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import TripForm from '$lib/components/TripForm.svelte';

	const EMPTY: TripInput = {
		title: '',
		purpose_code: '',
		purpose_detail: '',
		destination_type_code: '',
		country_code: '',
		city: '',
		start_date: '',
		end_date: ''
	};

	let values = $state<TripInput>({ ...EMPTY });
	let submitting = $state(false);
	let errorMessage = $state('');

	async function save(alsoSubmit: boolean): Promise<void> {
		// 버튼 disabled만으로는 requestSubmit 경로를 막지 못한다. 출장 신청은
		// 멱등하지 않아 중복 POST가 곧 중복 레코드다.
		if (submitting) return;
		submitting = true;
		errorMessage = '';
		try {
			const created = await createTrip(values);
			if (alsoSubmit) await submitTrip(created.id);
			await goto(`/trips/${created.id}`);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '저장하지 못했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<h1 class="text-display-xl">출장 신청</h1>
<p class="mt-2 text-body-md text-muted">필수 항목을 채우고 임시저장하거나 바로 상신하세요.</p>

<div class="mt-8 max-w-[720px]">
	<TripForm initial={EMPTY} onchange={(next) => (values = next)} />

	{#if errorMessage}
		<p class="mt-6 text-body-sm text-error" role="alert">{errorMessage}</p>
	{/if}

	<div class="mt-8 flex gap-3">
		<Button variant="secondary" disabled={submitting} onclick={() => save(false)}>
			{submitting ? '저장 중…' : '임시저장'}
		</Button>
		<Button disabled={submitting} onclick={() => save(true)}>
			{submitting ? '처리 중…' : '저장 후 상신'}
		</Button>
	</div>
</div>
