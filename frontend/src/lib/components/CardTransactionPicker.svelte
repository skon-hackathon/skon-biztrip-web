<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import { listCardTransactions } from '$lib/api/cards';
	import type { CardTransactionItem, Page } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import { formatDateTime, formatKrw } from '$lib/format';

	const SIZE = 20;

	let {
		busy = false,
		editable = true,
		onadd
	}: {
		busy?: boolean;
		editable?: boolean;
		onadd: (transaction: CardTransactionItem) => void;
	} = $props();

	const CATEGORY_LABELS: Record<string, string> = {
		MEAL: '음식점',
		TRANSPORT: '교통',
		LODGING: '숙박',
		ENTERTAIN: '유흥/접대',
		ETC: '기타'
	};

	let result = $state<Page<CardTransactionItem> | null>(null);
	let currentPage = $state(1);
	let q = $state('');
	let loading = $state(true);
	let errorMessage = $state('');

	const totalPages = $derived(result ? Math.max(1, Math.ceil(result.total / SIZE)) : 1);

	/** 부모가 항목을 담고 나면 그 거래는 unsettled에서 빠진다. 다시 불러 목록을 맞춘다. */
	export async function reload(): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			result = await listCardTransactions({
				unsettled: true,
				q: q || undefined,
				page: currentPage,
				size: SIZE
			});
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '카드 거래를 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	// $effect로 q·currentPage를 추적하지 않는다 — 검색어를 한 글자 칠 때마다 조회가
	// 나가고, 페이지 이동은 명시 호출과 겹쳐 두 번 나간다.
	onMount(reload);

	function search(): void {
		currentPage = 1;
		void reload();
	}

	function goToPage(next: number): void {
		currentPage = next;
		void reload();
	}
</script>

<p class="text-body-sm text-muted">
	아직 어떤 정산서에도 담기지 않은 본인 법인카드 사용내역입니다. 출장 기간 밖의 결제도 담을 수
	있습니다.
</p>

<div class="mt-4 flex items-end gap-3">
	<div class="grow">
		<TextInput label="가맹점 검색" bind:value={q} placeholder="한밭식당" />
	</div>
	<Button variant="secondary" onclick={search}>검색</Button>
</div>

{#if errorMessage}
	<p class="mt-6 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-6 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-6 text-body-sm text-muted">미정산 {result.total}건</p>
	<div class="mt-3 overflow-x-auto">
		<table class="w-full min-w-[640px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left">
					<th class="py-3 text-caption text-muted">승인일시</th>
					<th class="py-3 text-caption text-muted">가맹점</th>
					<th class="py-3 text-caption text-muted">업종</th>
					<th class="py-3 text-right text-caption text-muted">금액</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each result.items as row (row.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 text-body-sm text-muted">{formatDateTime(row.approved_at)}</td>
						<td class="py-3 text-body-md text-ink">{row.merchant_name}</td>
						<td class="py-3 text-body-sm text-muted">
							{CATEGORY_LABELS[row.merchant_category_code] ?? row.merchant_category_code}
						</td>
						<td class="py-3 text-right text-body-md text-ink">{formatKrw(row.amount_krw)}</td>
						<td class="py-3 text-right">
							{#if editable}
								<Button variant="pill" disabled={busy} onclick={() => onadd(row)}>담기</Button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if totalPages > 1}
		<div class="mt-6 flex items-center justify-center gap-4">
			<Button
				variant="secondary"
				disabled={currentPage <= 1}
				onclick={() => goToPage(currentPage - 1)}
			>
				이전
			</Button>
			<span class="text-body-sm text-muted">{currentPage} / {totalPages}</span>
			<Button
				variant="secondary"
				disabled={currentPage >= totalPages}
				onclick={() => goToPage(currentPage + 1)}
			>
				다음
			</Button>
		</div>
	{/if}
{:else}
	<p class="mt-6 text-body-sm text-muted">정산하지 않은 카드 사용내역이 없습니다.</p>
{/if}
