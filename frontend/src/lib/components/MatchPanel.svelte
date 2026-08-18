<script lang="ts">
	import type { MatchCandidate } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import { formatDateTime, formatKrw } from '$lib/format';

	let {
		candidates,
		busy = false,
		editable = true,
		onadd
	}: {
		candidates: MatchCandidate[];
		busy?: boolean;
		editable?: boolean;
		onadd: (candidate: MatchCandidate) => void;
	} = $props();
</script>

{#if candidates.length === 0}
	<p class="text-body-sm text-muted">출장 기간과 겹치는 카드 거래가 없습니다.</p>
{:else}
	<ul class="flex flex-col gap-3">
		{#each candidates as candidate (candidate.transaction_id)}
			<li
				class="flex items-start justify-between gap-4 rounded-md border border-hairline px-4 py-3"
			>
				<div>
					<p class="text-title-sm text-ink">{candidate.merchant_name}</p>
					<p class="mt-1 text-caption-sm text-muted">{formatDateTime(candidate.approved_at)}</p>
					<div class="mt-2 flex flex-wrap gap-2">
						{#each candidate.reasons as reason (reason)}
							<!-- 매칭 사유는 API가 준 문자열을 그대로 쓴다. 화면에서 따로 만들면
							     Agent가 받는 설명과 사람이 보는 설명이 갈라진다. -->
							<span class="rounded-full bg-surface-soft px-2.5 py-1 text-badge text-ink">
								{reason}
							</span>
						{/each}
					</div>
				</div>
				<div class="flex shrink-0 flex-col items-end gap-2">
					<p class="text-body-md text-ink">{formatKrw(candidate.amount_krw)}</p>
					{#if candidate.already_added}
						<span class="text-caption-sm text-muted">담김</span>
					{:else if editable}
						<Button variant="pill" disabled={busy} onclick={() => onadd(candidate)}>담기</Button>
					{/if}
				</div>
			</li>
		{/each}
	</ul>
{/if}
