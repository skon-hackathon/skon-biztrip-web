<script lang="ts">
	import { formatDateTime } from '$lib/format';
	import type { ActivityAction, TimelineEntry } from '$lib/api/types';

	let { entries }: { entries: TimelineEntry[] } = $props();

	const ACTION_LABELS: Record<ActivityAction, string> = {
		CREATED: '작성',
		UPDATED: '수정',
		SUBMITTED: '상신',
		APPROVED: '승인',
		REJECTED: '반려',
		COMPLETED: '완료',
		SETTLED: '정산완료'
	};
</script>

{#if entries.length === 0}
	<p class="text-body-sm text-muted">기록이 없습니다.</p>
{:else}
	<ol class="flex flex-col gap-4">
		{#each entries as entry (entry.id)}
			<li class="flex gap-4">
				<div class="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary"></div>
				<div class="min-w-0">
					<p class="text-title-sm text-ink">
						{ACTION_LABELS[entry.action]} · {entry.actor_name}
					</p>
					<p class="mt-1 text-caption-sm text-muted">{formatDateTime(entry.created_at)}</p>
					{#if entry.memo}
						<p class="mt-1 text-body-sm text-muted">{entry.memo}</p>
					{/if}
				</div>
			</li>
		{/each}
	</ol>
{/if}
