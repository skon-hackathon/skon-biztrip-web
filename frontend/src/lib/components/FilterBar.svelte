<script lang="ts">
	import { TRIP_STATUS_LABELS, TRIP_STATUS_ORDER } from '$lib/trip-status';
	import type { TripStatus } from '$lib/api/types';

	let {
		q = $bindable(''),
		startDateFrom = $bindable(''),
		status = $bindable<TripStatus | ''>(''),
		onsearch
	}: {
		q?: string;
		startDateFrom?: string;
		status?: TripStatus | '';
		onsearch: () => void;
	} = $props();

	// $props.id()는 컴포넌트당 한 번만 부를 수 있다. 베이스 하나에서 접미사를 붙인다.
	// crypto.randomUUID()를 쓰지 않는 이유는 운영이 평문 HTTP라 SecureContext가 아니어서
	// 그 API 자체가 존재하지 않기 때문이다.
	const baseId = $props.id();
	const qId = `${baseId}-q`;
	const dateId = `${baseId}-date`;
	const statusId = `${baseId}-status`;

	function handleSubmit(event: SubmitEvent): void {
		event.preventDefault();
		onsearch();
	}
</script>

<form onsubmit={handleSubmit}>
	<div class="flex h-16 items-center rounded-full border border-hairline bg-canvas pr-2 shadow-float">
		<div class="flex flex-1 flex-col justify-center px-6">
			<label for={qId} class="text-badge tracking-wide text-muted uppercase">어디로</label>
			<input
				id={qId}
				bind:value={q}
				placeholder="도시 · 제목 · 출장번호"
				class="bg-transparent text-caption text-ink outline-none placeholder:text-muted-soft"
			/>
		</div>

		<div class="h-8 w-px bg-hairline"></div>

		<div class="flex flex-1 flex-col justify-center px-6">
			<label for={dateId} class="text-badge tracking-wide text-muted uppercase">언제부터</label>
			<input
				id={dateId}
				type="date"
				bind:value={startDateFrom}
				class="bg-transparent text-caption text-ink outline-none"
			/>
		</div>

		<div class="h-8 w-px bg-hairline"></div>

		<div class="flex flex-1 flex-col justify-center px-6">
			<label for={statusId} class="text-badge tracking-wide text-muted uppercase">상태</label>
			<select
				id={statusId}
				bind:value={status}
				class="bg-transparent text-caption text-ink outline-none"
			>
				<option value="">전체</option>
				{#each TRIP_STATUS_ORDER as value (value)}
					<option {value}>{TRIP_STATUS_LABELS[value]}</option>
				{/each}
			</select>
		</div>

		<button
			type="submit"
			aria-label="검색"
			class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary text-white hover:bg-primary-active"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2.5">
				<circle cx="11" cy="11" r="7" />
				<path d="M20 20l-3.5-3.5" stroke-linecap="round" />
			</svg>
		</button>
	</div>
</form>
