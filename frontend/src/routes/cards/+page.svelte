<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { listCardTransactions, listCards } from '$lib/api/cards';
	import type { CardItem, CardTransactionItem, Page } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import CardTransactionTable from '$lib/components/CardTransactionTable.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const SIZE = 20;

	let cards = $state<CardItem[]>([]);
	let selectedCardId = $state<number | null>(null);
	let result = $state<Page<CardTransactionItem> | null>(null);
	let currentPage = $state(1);
	let q = $state('');
	let approvedFrom = $state('');
	let approvedTo = $state('');
	let includeCancelled = $state(false);
	let loading = $state(true);
	let errorMessage = $state('');

	const totalPages = $derived(result ? Math.max(1, Math.ceil(result.total / SIZE)) : 1);

	onMount(async () => {
		try {
			cards = await listCards();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '카드를 불러오지 못했습니다';
		}
		await load();
	});

	async function load(): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			result = await listCardTransactions({
				card_id: selectedCardId ?? undefined,
				q: q || undefined,
				approved_from: approvedFrom || undefined,
				approved_to: approvedTo || undefined,
				include_cancelled: includeCancelled,
				page: currentPage,
				size: SIZE
			});
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '거래를 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function applyFilters(): void {
		currentPage = 1;
		void load();
	}

	function selectCard(cardId: number | null): void {
		selectedCardId = cardId;
		applyFilters();
	}

	function goToPage(next: number): void {
		currentPage = next;
		void load();
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">내 법인카드</h1>
	<!-- 전체 새로고침(window.location)을 쓰지 않는다 — 인증 스토어가 restore를 다시 돌아야 한다. -->
	<Button variant="secondary" onclick={() => goto('/expenses')}>정산 목록</Button>
</div>

<div class="mt-6 mb-6 flex flex-wrap gap-3">
	<button
		class="rounded-full border px-4 py-2 text-button-sm {selectedCardId === null
			? 'border-ink text-ink'
			: 'border-hairline text-muted'}"
		onclick={() => selectCard(null)}
	>
		전체
	</button>
	{#each cards as card (card.id)}
		<button
			class="rounded-full border px-4 py-2 text-button-sm {selectedCardId === card.id
				? 'border-ink text-ink'
				: 'border-hairline text-muted'}"
			onclick={() => selectCard(card.id)}
		>
			{card.brand} · {card.card_no_masked}
		</button>
	{/each}
</div>

<Card>
	<div class="grid grid-cols-1 gap-4 md:grid-cols-4">
		<TextInput label="가맹점 검색" bind:value={q} placeholder="한밭식당" />
		<TextInput label="승인일 시작" type="date" bind:value={approvedFrom} />
		<TextInput label="승인일 종료" type="date" bind:value={approvedTo} />
		<div class="flex items-end gap-4">
			<label class="flex items-center gap-2 text-body-sm text-ink">
				<input type="checkbox" bind:checked={includeCancelled} class="h-4 w-4" />
				취소 포함
			</label>
			<Button onclick={applyFilters}>검색</Button>
		</div>
	</div>
</Card>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">전체 {result.total}건</p>
	<div class="mt-4">
		<CardTransactionTable rows={result.items} />
	</div>
	{#if totalPages > 1}
		<div class="mt-8 flex items-center justify-center gap-4">
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
	<div class="mt-8">
		<EmptyState title="카드 거래가 없습니다" description="조건을 바꿔 다시 검색해 보세요." />
	</div>
{/if}
