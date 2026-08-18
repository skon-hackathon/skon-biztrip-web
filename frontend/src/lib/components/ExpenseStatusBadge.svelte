<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import { EXPENSE_STATUS_LABELS, EXPENSE_STATUS_TONES } from '$lib/expenses';
	import type { ExpenseStatus } from '$lib/api/types';

	let { status }: { status: ExpenseStatus } = $props();
</script>

<Badge tone={EXPENSE_STATUS_TONES[status]}>{EXPENSE_STATUS_LABELS[status]}</Badge>
