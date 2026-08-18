<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { listExpenses, type ExpenseQuery } from '$lib/api/expenses';
	import type { ExpenseReportListItem, ExpenseStatus, Page } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ExpenseStatusBadge from '$lib/components/ExpenseStatusBadge.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import { EXPENSE_STATUS_LABELS, EXPENSE_STATUS_ORDER } from '$lib/expenses';
	import { formatDateRange, formatKrw } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	const SIZE = 12;

	let result = $state<Page<ExpenseReportListItem> | null>(null);
	let loading = $state(true);
	let errorMessage = $state('');

	let q = $state(page.url.searchParams.get('q') ?? '');
	let status = $state<ExpenseStatus | ''>(
		(page.url.searchParams.get('status') as ExpenseStatus) ?? ''
	);
	let scope = $state<'mine' | 'approvals'>(
		page.url.searchParams.get('scope') === 'approvals' ? 'approvals' : 'mine'
	);

	const canApprove = $derived(auth.user?.role === 'MANAGER' || auth.user?.role === 'ADMIN');
	const currentPage = $derived(Number(page.url.searchParams.get('page') ?? '1'));
	const totalPages = $derived(result ? Math.max(1, Math.ceil(result.total / SIZE)) : 1);

	const statusOptions = EXPENSE_STATUS_ORDER.map((value) => ({
		value,
		label: EXPENSE_STATUS_LABELS[value]
	}));

	// page.url.search만 의존성으로 읽는다 — 아래에서 대입하는 상태는 이 effect가 읽지
	// 않으므로 다시 트리거되지 않는다.
	$effect(() => {
		const search = page.url.search;
		void load(new URLSearchParams(search));
	});

	async function load(params: URLSearchParams): Promise<void> {
		loading = true;
		errorMessage = '';
		const query: ExpenseQuery = { page: Number(params.get('page') ?? '1'), size: SIZE };
		const searchText = params.get('q');
		const statusValue = params.get('status');
		if (searchText) query.q = searchText;
		if (statusValue) query.status = [statusValue as ExpenseStatus];
		if (params.get('scope') === 'approvals') query.scope = 'approvals';
		try {
			result = await listExpenses(query);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '정산 목록을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function applyFilters(): void {
		const params = new URLSearchParams();
		if (q) params.set('q', q);
		if (status) params.set('status', status);
		if (scope === 'approvals') params.set('scope', 'approvals');
		goto(`/expenses${params.toString() ? `?${params}` : ''}`);
	}

	function goToPage(next: number): void {
		const params = new URLSearchParams(page.url.searchParams);
		params.set('page', String(next));
		goto(`/expenses?${params}`);
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">정산</h1>
	<Button variant="secondary" onclick={() => goto('/cards')}>카드 내역</Button>
</div>

<div class="mt-6">
	<Card>
		<div class="grid grid-cols-1 gap-4 md:grid-cols-4">
			<TextInput label="검색" bind:value={q} placeholder="정산번호 · 출장명" />
			<Select label="상태" bind:value={status} options={statusOptions} placeholder="전체" />
			{#if canApprove}
				<Select
					label="구분"
					bind:value={scope}
					options={[
						{ value: 'mine', label: '내 정산' },
						{ value: 'approvals', label: '결재 대상' }
					]}
					placeholder="내 정산"
				/>
			{/if}
			<div class="flex items-end">
				<Button onclick={applyFilters}>검색</Button>
			</div>
		</div>
	</Card>
</div>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if result && result.items.length > 0}
	<p class="mt-8 text-body-sm text-muted">전체 {result.total}건</p>
	<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
		{#each result.items as report (report.id)}
			<a href={`/expenses/${report.id}`} class="block">
				<Card hoverable>
					<div class="flex items-start justify-between">
						<p class="text-caption text-muted">{report.report_no}</p>
						<ExpenseStatusBadge status={report.status} />
					</div>
					<p class="mt-2 text-title-md text-ink">{report.trip_title}</p>
					<p class="mt-1 text-body-sm text-muted">
						{report.trip_no} · {formatDateRange(report.trip_start_date, report.trip_end_date)}
					</p>
					<p class="mt-4 text-display-sm text-ink">{formatKrw(report.total_amount_krw)}</p>
					<p class="mt-2 text-caption-sm text-muted">
						{report.user_name} → {report.approver_name ?? '결재자 미지정'}
					</p>
				</Card>
			</a>
		{/each}
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
		<EmptyState
			title="정산서가 없습니다"
			description="완료된 출장 상세에서 정산서를 만들 수 있습니다."
		>
			{#snippet action()}
				<Button onclick={() => goto('/trips?status=COMPLETED')}>완료된 출장 보기</Button>
			{/snippet}
		</EmptyState>
	</div>
{/if}
