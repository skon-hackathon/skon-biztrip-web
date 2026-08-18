<script lang="ts">
	import type { ExpenseItemPatch, ExpenseReportDetail } from '$lib/api/types';
	import { formatKrw } from '$lib/format';

	let {
		report,
		categories,
		costCenters,
		fundCenters,
		editable = true,
		busy = false,
		onupdate,
		ondelete
	}: {
		report: ExpenseReportDetail;
		categories: { value: string; label: string }[];
		costCenters: { value: string; label: string }[];
		fundCenters: { value: string; label: string }[];
		editable?: boolean;
		busy?: boolean;
		onupdate: (itemId: number, patch: ExpenseItemPatch) => void;
		ondelete: (itemId: number) => void;
	} = $props();

	// 행 안의 셀렉트는 Select.svelte 대신 raw <select>를 쓴다 — 표에서는 열 머리글이 이미
	// 라벨이고, 행마다 시각적 라벨을 반복하면 표가 읽히지 않는다. 접근성은 aria-label로 채운다.
	const cellSelect =
		'h-10 rounded-sm border border-hairline bg-canvas px-2 text-body-sm text-ink disabled:text-muted-soft';
</script>

<div class="overflow-x-auto">
	<table class="w-full min-w-[860px] border-collapse">
		<thead>
			<tr class="border-b border-hairline text-left">
				<th class="py-3 text-caption text-muted">가맹점 / 메모</th>
				<th class="py-3 text-caption text-muted">비목</th>
				<th class="py-3 text-caption text-muted">코스트센터</th>
				<th class="py-3 text-caption text-muted">펀드센터</th>
				<th class="py-3 text-right text-caption text-muted">금액</th>
				<th class="py-3 text-right text-caption text-muted">제외</th>
				<th class="py-3"></th>
			</tr>
		</thead>
		<tbody>
			{#each report.items as item (item.id)}
				<tr class="border-b border-hairline {item.is_excluded ? 'text-muted-soft' : ''}">
					<td class="py-3 text-body-md text-ink">
						{item.merchant_name ?? '수기 항목'}
						{#if item.memo}
							<span class="ml-2 text-caption-sm text-muted">{item.memo}</span>
						{/if}
					</td>
					<td class="py-3">
						{#if editable}
							<select
								aria-label="비목"
								value={item.expense_category_code}
								disabled={busy}
								onchange={(event) =>
									onupdate(item.id, { expense_category_code: event.currentTarget.value })}
								class={cellSelect}
							>
								{#each categories as option (option.value)}
									<option value={option.value}>{option.label}</option>
								{/each}
							</select>
						{:else}
							<span class="text-body-sm text-ink">{item.expense_category_code}</span>
						{/if}
					</td>
					<td class="py-3">
						{#if editable}
							<select
								aria-label="코스트센터"
								value={item.cost_center_code ?? ''}
								disabled={busy}
								onchange={(event) =>
									onupdate(item.id, { cost_center_code: event.currentTarget.value || null })}
								class={cellSelect}
							>
								<option value="">상속 ({report.cost_center_code ?? '미지정'})</option>
								{#each costCenters as option (option.value)}
									<option value={option.value}>{option.label}</option>
								{/each}
							</select>
						{:else}
							<span class="text-body-sm text-ink">
								{item.effective_cost_center_code ?? '미지정'}
								{#if item.cost_center_code === null}<span class="text-muted"> (상속)</span>{/if}
							</span>
						{/if}
					</td>
					<td class="py-3">
						{#if editable}
							<select
								aria-label="펀드센터"
								value={item.fund_center_code ?? ''}
								disabled={busy}
								onchange={(event) =>
									onupdate(item.id, { fund_center_code: event.currentTarget.value || null })}
								class={cellSelect}
							>
								<option value="">상속 ({report.fund_center_code ?? '미지정'})</option>
								{#each fundCenters as option (option.value)}
									<option value={option.value}>{option.label}</option>
								{/each}
							</select>
						{:else}
							<span class="text-body-sm text-ink">
								{item.effective_fund_center_code ?? '미지정'}
								{#if item.fund_center_code === null}<span class="text-muted"> (상속)</span>{/if}
							</span>
						{/if}
					</td>
					<td class="py-3 text-right text-body-md text-ink">{formatKrw(item.amount_krw)}</td>
					<td class="py-3 text-right">
						<input
							type="checkbox"
							aria-label="정산에서 제외"
							checked={item.is_excluded}
							disabled={!editable || busy}
							onchange={(event) => onupdate(item.id, { is_excluded: event.currentTarget.checked })}
							class="h-4 w-4"
						/>
					</td>
					<td class="py-3 text-right">
						{#if editable}
							<button
								class="text-button-sm text-ink underline-offset-4 hover:underline disabled:text-muted-soft"
								disabled={busy}
								onclick={() => ondelete(item.id)}
							>
								삭제
							</button>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
