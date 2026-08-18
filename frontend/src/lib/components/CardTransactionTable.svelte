<script lang="ts">
	import type { CardTransactionItem } from '$lib/api/types';
	import { formatDateTime, formatKrw } from '$lib/format';

	let { rows }: { rows: CardTransactionItem[] } = $props();

	const CATEGORY_LABELS: Record<string, string> = {
		MEAL: '음식점',
		TRANSPORT: '교통',
		LODGING: '숙박',
		ENTERTAIN: '유흥/접대',
		ETC: '기타'
	};
</script>

<div class="overflow-x-auto">
	<table class="w-full min-w-[720px] border-collapse">
		<thead>
			<tr class="border-b border-hairline text-left">
				<th class="py-3 text-caption text-muted">승인일시</th>
				<th class="py-3 text-caption text-muted">가맹점</th>
				<th class="py-3 text-caption text-muted">업종</th>
				<th class="py-3 text-right text-caption text-muted">금액</th>
			</tr>
		</thead>
		<tbody>
			{#each rows as row (row.id)}
				<tr class="border-b border-hairline">
					<td class="py-3 text-body-sm text-muted">{formatDateTime(row.approved_at)}</td>
					<td class="py-3 text-body-md text-ink">
						{row.merchant_name}
						{#if row.is_cancelled}
							<span class="ml-2 text-caption-sm text-error">취소</span>
						{/if}
					</td>
					<td class="py-3 text-body-sm text-muted">
						{CATEGORY_LABELS[row.merchant_category_code] ?? row.merchant_category_code}
					</td>
					<td class="py-3 text-right text-body-md text-ink">{formatKrw(row.amount_krw)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
