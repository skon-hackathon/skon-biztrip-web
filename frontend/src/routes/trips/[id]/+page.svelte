<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import {
		approveTrip,
		completeTrip,
		deleteTrip,
		getTimeline,
		getTrip,
		rejectTrip,
		reopenTrip,
		submitTrip
	} from '$lib/api/trips';
	import type { TimelineEntry, TripDetail } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import Textarea from '$lib/components/Textarea.svelte';
	import Timeline from '$lib/components/Timeline.svelte';
	import { formatDateRange, formatDateTime, formatKrw, tripLength } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	let trip = $state<TripDetail | null>(null);
	let entries = $state<TimelineEntry[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');
	let actionError = $state('');
	let busy = $state(false);
	let rejecting = $state(false);
	let rejectReason = $state('');

	const tripId = $derived(Number(page.params.id));
	const isOwner = $derived(!!trip && trip.user_id === auth.user?.id);
	const isApprover = $derived(!!trip && trip.approver_id === auth.user?.id);

	$effect(() => {
		const id = tripId;
		void load(id);
	});

	async function load(id: number): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			[trip, entries] = await Promise.all([getTrip(id), getTimeline(id)]);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '출장을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	async function act(action: (id: number) => Promise<TripDetail>): Promise<void> {
		if (busy) return;
		busy = true;
		actionError = '';
		try {
			trip = await action(tripId);
			entries = await getTimeline(tripId);
			rejecting = false;
			rejectReason = '';
		} catch (error) {
			actionError = error instanceof ApiError ? error.message : '처리하지 못했습니다';
		} finally {
			busy = false;
		}
	}

	async function removeTrip(): Promise<void> {
		if (busy) return;
		busy = true;
		actionError = '';
		try {
			await deleteTrip(tripId);
			await goto('/trips');
		} catch (error) {
			actionError = error instanceof ApiError ? error.message : '삭제하지 못했습니다';
			busy = false;
		}
	}
</script>

{#if loading}
	<p class="text-body-sm text-muted">불러오는 중…</p>
{:else if errorMessage}
	<p class="text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if trip}
	<div class="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
		<div>
			<p class="text-caption text-muted">{trip.trip_no}</p>
			<div class="mt-2 flex items-center gap-3">
				<h1 class="text-display-xl">{trip.title}</h1>
				<StatusBadge status={trip.status} />
			</div>

			{#if trip.status === 'REJECTED' && trip.reject_reason}
				<div class="mt-6 rounded-md border border-error px-4 py-3">
					<p class="text-caption text-error">반려 사유</p>
					<p class="mt-1 text-body-md text-ink">{trip.reject_reason}</p>
				</div>
			{/if}

			<dl class="mt-8 grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
				<div>
					<dt class="text-caption text-muted">기간</dt>
					<dd class="mt-1 text-body-md text-ink">
						{formatDateRange(trip.start_date, trip.end_date)} · {tripLength(
							trip.start_date,
							trip.end_date
						)}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">목적지</dt>
					<dd class="mt-1 text-body-md text-ink">{trip.country_code} · {trip.city}</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">이동수단 / 숙박</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.transport_code} · {trip.accommodation_code}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">코스트센터</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.cost_center_code}{trip.cost_center_name ? ` · ${trip.cost_center_name}` : ''}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">신청자 / 결재자</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.user_name} / {trip.approver_name ?? '미지정'}
					</dd>
				</div>
				<div>
					<dt class="text-caption text-muted">상신 / 승인 시각</dt>
					<dd class="mt-1 text-body-md text-ink">
						{trip.submitted_at ? formatDateTime(trip.submitted_at) : '-'} / {trip.approved_at
							? formatDateTime(trip.approved_at)
							: '-'}
					</dd>
				</div>
			</dl>

			<h2 class="mt-10 text-display-sm">출장 목적</h2>
			<p class="mt-2 whitespace-pre-line text-body-md text-ink">{trip.purpose_detail}</p>

			<h2 class="mt-10 text-display-sm">진행 이력</h2>
			<div class="mt-4">
				<Timeline {entries} />
			</div>
		</div>

		<aside class="lg:sticky lg:top-8 lg:self-start">
			<Card>
				<p class="text-caption text-muted">예상 비용</p>
				<p class="mt-1 text-display-md text-ink">{formatKrw(trip.estimated_cost)}</p>

				{#if actionError}
					<p class="mt-4 text-caption-sm text-error" role="alert">{actionError}</p>
				{/if}

				<div class="mt-6 flex flex-col gap-3">
					{#if isOwner && (trip.status === 'DRAFT' || trip.status === 'REJECTED')}
						<Button full disabled={busy} onclick={() => goto(`/trips/${tripId}/edit`)}>수정</Button>
					{/if}

					{#if isOwner && trip.status === 'DRAFT'}
						<Button full variant="secondary" disabled={busy} onclick={() => act(submitTrip)}>
							상신
						</Button>
						<Button full variant="tertiary" disabled={busy} onclick={removeTrip}>삭제</Button>
					{/if}

					{#if isOwner && trip.status === 'REJECTED'}
						<Button full variant="secondary" disabled={busy} onclick={() => act(reopenTrip)}>
							다시 작성
						</Button>
					{/if}

					{#if isOwner && trip.status === 'APPROVED'}
						<Button full variant="secondary" disabled={busy} onclick={() => act(completeTrip)}>
							완료 처리
						</Button>
					{/if}

					{#if isApprover && trip.status === 'SUBMITTED'}
						<Button full disabled={busy} onclick={() => act(approveTrip)}>승인</Button>
						{#if rejecting}
							<Textarea label="반려 사유" bind:value={rejectReason} rows={3} />
							<Button
								full
								variant="secondary"
								disabled={busy}
								onclick={() => act((id) => rejectTrip(id, rejectReason))}
							>
								반려 확정
							</Button>
							<Button full variant="tertiary" disabled={busy} onclick={() => (rejecting = false)}>
								취소
							</Button>
						{:else}
							<Button full variant="secondary" disabled={busy} onclick={() => (rejecting = true)}>
								반려
							</Button>
						{/if}
					{/if}

					{#if trip.status === 'COMPLETED' || trip.status === 'SETTLED'}
						<p class="text-body-sm text-muted">정산은 Phase 3에서 연결됩니다.</p>
					{/if}
				</div>
			</Card>
		</aside>
	</div>
{/if}
