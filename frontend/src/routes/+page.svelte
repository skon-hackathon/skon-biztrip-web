<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import { listNotifications } from '$lib/api/notifications';
	import { listTrips } from '$lib/api/trips';
	import type { NotificationItem, TripListItem } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Card from '$lib/components/Card.svelte';
	import TripCard from '$lib/components/TripCard.svelte';
	import { formatDateTime } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	const ROLE_LABELS: Record<string, string> = {
		EMPLOYEE: '사원',
		MANAGER: '팀장',
		ADMIN: '관리자'
	};

	let ongoing = $state(0);
	let waiting = $state(0);
	let unsettled = $state(0);
	let recentTrips = $state<TripListItem[]>([]);
	let recentNotifications = $state<NotificationItem[]>([]);
	let errorMessage = $state('');
	let loading = $state(true);

	// 전용 집계 API를 만들지 않는다 — size=1로 목록을 불러 total만 읽으면 된다.
	onMount(async () => {
		try {
			const [ongoingPage, waitingPage, unsettledPage, latest, notified] = await Promise.all([
				listTrips({ status: ['SUBMITTED', 'APPROVED'], size: 1 }),
				listTrips({ scope: 'approvals', status: ['SUBMITTED'], size: 1 }),
				listTrips({ status: ['COMPLETED'], size: 1 }),
				listTrips({ size: 3 }),
				listNotifications({ size: 5 })
			]);
			ongoing = ongoingPage.total;
			waiting = waitingPage.total;
			unsettled = unsettledPage.total;
			recentTrips = latest.items;
			recentNotifications = notified.items;
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '현황을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	});
</script>

<h1 class="text-display-xl">안녕하세요, {auth.user?.name}님</h1>
<p class="mt-2 text-body-md text-muted">
	{auth.user?.department_name} · {auth.user?.role
		? (ROLE_LABELS[auth.user.role] ?? auth.user.role)
		: ''}
</p>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{/if}

<div class="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
	<a href="/trips?status=SUBMITTED" class="block">
		<Card hoverable>
			<p class="text-caption text-muted">진행 중 출장</p>
			<p class="mt-2 text-display-md">{loading ? '…' : `${ongoing}건`}</p>
			<div class="mt-3"><Badge>승인대기 · 승인</Badge></div>
		</Card>
	</a>
	<a href="/approvals" class="block">
		<Card hoverable>
			<p class="text-caption text-muted">결재 대기</p>
			<p class="mt-2 text-display-md">{loading ? '…' : `${waiting}건`}</p>
		</Card>
	</a>
	<a href="/trips?status=COMPLETED" class="block">
		<Card hoverable>
			<p class="text-caption text-muted">미정산 출장</p>
			<p class="mt-2 text-display-md">{loading ? '…' : `${unsettled}건`}</p>
			<div class="mt-3"><Badge>정산은 Phase 3</Badge></div>
		</Card>
	</a>
</div>

<div class="mt-12 grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
	<section>
		<h2 class="text-display-sm">최근 출장</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
			{#each recentTrips as trip (trip.id)}
				<TripCard {trip} />
			{/each}
			{#if !loading && recentTrips.length === 0}
				<p class="text-body-sm text-muted">아직 신청한 출장이 없습니다.</p>
			{/if}
		</div>
	</section>

	<section>
		<h2 class="text-display-sm">최근 알림</h2>
		<ul class="mt-4 flex flex-col gap-3">
			{#each recentNotifications as item (item.id)}
				<li class="rounded-md border border-hairline px-4 py-3">
					<a href={item.link_url ?? '/notifications'} class="block">
						<p class="text-title-sm text-ink">{item.title}</p>
						<p class="mt-1 text-caption-sm text-muted">{formatDateTime(item.created_at)}</p>
					</a>
				</li>
			{/each}
			{#if !loading && recentNotifications.length === 0}
				<li class="text-body-sm text-muted">알림이 없습니다.</li>
			{/if}
		</ul>
	</section>
</div>
