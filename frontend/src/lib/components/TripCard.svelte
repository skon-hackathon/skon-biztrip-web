<script lang="ts">
	import Card from '$lib/components/Card.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { formatDateRange, formatKrw, tripLength } from '$lib/format';
	import type { TripListItem } from '$lib/api/types';

	let { trip, showOwner = false }: { trip: TripListItem; showOwner?: boolean } = $props();
</script>

<a href="/trips/{trip.id}" class="block">
	<Card hoverable>
		<div class="flex items-start justify-between gap-4">
			<div class="min-w-0">
				<p class="text-caption text-muted">{trip.trip_no}</p>
				<p class="mt-1 truncate text-title-md text-ink">{trip.title}</p>
			</div>
			<StatusBadge status={trip.status} />
		</div>

		<p class="mt-4 text-body-sm text-muted">
			{trip.city} · {trip.destination_type_code === 'OVERSEAS' ? '해외' : '국내'} · {tripLength(
				trip.start_date,
				trip.end_date
			)}
		</p>
		<p class="mt-1 text-body-sm text-muted">
			{formatDateRange(trip.start_date, trip.end_date)}
		</p>

		<div class="mt-4 flex items-end justify-between">
			{#if showOwner}
				<p class="text-body-sm text-muted">{trip.user_name}</p>
			{:else}
				<p class="text-body-sm text-muted">
					{trip.approver_name ? `결재자 ${trip.approver_name}` : '결재자 미지정'}
				</p>
			{/if}
			<p class="text-title-md text-ink">{formatKrw(trip.estimated_cost)}</p>
		</div>
	</Card>
</a>
