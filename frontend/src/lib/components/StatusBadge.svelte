<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { TRIP_STATUS_LABELS, TRIP_STATUS_TONES } from '$lib/trip-status';
	import type { TripStatus } from '$lib/api/types';

	let { status }: { status: TripStatus } = $props();
</script>

<Badge tone={TRIP_STATUS_TONES[status]}>{TRIP_STATUS_LABELS[status]}</Badge>
