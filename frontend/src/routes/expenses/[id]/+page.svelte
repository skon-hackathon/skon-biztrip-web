<script lang="ts">
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { listCostCenters, listFundCenters } from '$lib/api/centers';
	import { byGroupCode, listCodeGroups } from '$lib/api/codes';
	import {
		addExpenseItem,
		approveExpense,
		deleteExpenseItem,
		getExpense,
		getExpenseTimeline,
		getMatchCandidates,
		rejectExpense,
		reopenExpense,
		submitExpense,
		updateExpense,
		updateExpenseItem
	} from '$lib/api/expenses';
	import type {
		CardTransactionItem,
		ExpenseItemPatch,
		ExpenseReportDetail,
		MatchCandidate,
		TimelineEntry
	} from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import CardTransactionPicker from '$lib/components/CardTransactionPicker.svelte';
	import ExpenseItemsTable from '$lib/components/ExpenseItemsTable.svelte';
	import ExpenseStatusBadge from '$lib/components/ExpenseStatusBadge.svelte';
	import MatchPanel from '$lib/components/MatchPanel.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import Select from '$lib/components/Select.svelte';
	import Textarea from '$lib/components/Textarea.svelte';
	import Timeline from '$lib/components/Timeline.svelte';
	import { formatDateRange, formatKrw } from '$lib/format';
	import { auth } from '$lib/stores/auth.svelte';

	let report = $state<ExpenseReportDetail | null>(null);
	let candidates = $state<MatchCandidate[]>([]);
	let entries = $state<TimelineEntry[]>([]);
	let categories = $state<{ value: string; label: string }[]>([]);
	let costCenters = $state<{ value: string; label: string }[]>([]);
	let fundCenters = $state<{ value: string; label: string }[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');
	let actionError = $state('');
	let busy = $state(false);
	let rejecting = $state(false);
	let rejectReason = $state('');
	let fundCenterValue = $state('');
	let costCenterValue = $state('');
	let pickerOpen = $state(false);
	let picker = $state<ReturnType<typeof CardTransactionPicker> | null>(null);

	const reportId = $derived(Number(page.params.id));
	const isOwner = $derived(!!report && report.user_id === auth.user?.id);
	const isApprover = $derived(!!report && report.approver_id === auth.user?.id);
	const editable = $derived(
		!!report && isOwner && (report.status === 'DRAFT' || report.status === 'REJECTED')
	);

	$effect(() => {
		const id = reportId;
		void load(id);
	});

	// 서버 값이 바뀌면 헤더 셀렉트를 맞춘다. PATCH 응답이 곧 진실이므로 사용자의 선택이
	// 응답으로 덮이는 것은 의도된 동작이다.
	$effect(() => {
		fundCenterValue = report?.fund_center_code ?? '';
		costCenterValue = report?.cost_center_code ?? '';
	});

	async function load(id: number): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			const [detail, matched, timeline, groups, costs, funds] = await Promise.all([
				getExpense(id),
				getMatchCandidates(id),
				getExpenseTimeline(id),
				listCodeGroups(),
				listCostCenters(),
				listFundCenters()
			]);
			report = detail;
			candidates = matched;
			entries = timeline;
			categories = (byGroupCode(groups).EXPENSE_CATEGORY?.codes ?? []).map((code) => ({
				value: code.code,
				label: code.name
			}));
			costCenters = costs.map((center) => ({
				value: center.code,
				label: `${center.code} · ${center.name}`
			}));
			fundCenters = funds.map((center) => ({
				value: center.code,
				label: `${center.code} · ${center.name}`
			}));
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '정산서를 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	/**
	 * 모든 쓰기는 이 한 곳을 지난다. 첫 줄의 `if (busy) return;`이 중복 제출 가드다 —
	 * 버튼의 disabled만으로는 연타·엔터 경로를 막지 못하고, 항목 추가와 제출은 멱등하지
	 * 않아 중복 호출이 곧 중복 레코드다.
	 */
	async function act(
		action: () => Promise<ExpenseReportDetail>,
		{ refreshCandidates = false }: { refreshCandidates?: boolean } = {}
	): Promise<void> {
		if (busy) return;
		busy = true;
		actionError = '';
		try {
			report = await action();
			entries = await getExpenseTimeline(reportId);
			if (refreshCandidates) candidates = await getMatchCandidates(reportId);
			rejecting = false;
			rejectReason = '';
		} catch (error) {
			actionError = error instanceof ApiError ? error.message : '처리하지 못했습니다';
		} finally {
			busy = false;
		}
	}

	function addCandidate(candidate: MatchCandidate): void {
		void act(
			() =>
				addExpenseItem(reportId, {
					card_transaction_id: candidate.transaction_id,
					expense_category_code: candidate.suggested_category_code
				}),
			{ refreshCandidates: true }
		);
	}

	/**
	 * 자동매칭 후보 밖의 거래를 담는다. 비목은 서버가 계산해 준 추천값을 그대로 쓴다 —
	 * 화면이 업종→비목 매핑을 따로 가지면 자동매칭과 추천이 갈라진다.
	 *
	 * 담은 거래는 unsettled 필터에서 빠지므로 피커를 다시 불러 목록을 맞춘다.
	 */
	function addTransaction(transaction: CardTransactionItem): void {
		void act(
			() =>
				addExpenseItem(reportId, {
					card_transaction_id: transaction.id,
					expense_category_code: transaction.suggested_expense_category_code
				}),
			{ refreshCandidates: true }
		).then(() => picker?.reload());
	}

	function patchItem(itemId: number, patch: ExpenseItemPatch): void {
		void act(() => updateExpenseItem(itemId, patch));
	}

	function removeItem(itemId: number): void {
		void act(() => deleteExpenseItem(itemId), { refreshCandidates: true });
	}

	/**
	 * 셀렉트 변경마다 PATCH를 보내지 않고 명시적 저장 버튼을 둔다. 두 값을 연달아 고칠 때
	 * 왕복이 두 번 생기고, 늦게 도착한 응답이 방금 고른 값을 덮을 수 있기 때문이다.
	 */
	function saveCenters(): void {
		void act(() =>
			updateExpense(reportId, {
				fund_center_code: fundCenterValue || null,
				cost_center_code: costCenterValue || null
			})
		);
	}
</script>

{#if loading}
	<p class="text-body-sm text-muted">불러오는 중…</p>
{:else if errorMessage}
	<p class="text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if report}
	<div class="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
		<div>
			<p class="text-caption text-muted">{report.report_no}</p>
			<div class="mt-2 flex items-center gap-3">
				<h1 class="text-display-xl">{report.trip_title}</h1>
				<ExpenseStatusBadge status={report.status} />
			</div>
			<p class="mt-2 text-body-sm text-muted">
				<a href={`/trips/${report.trip_id}`} class="underline-offset-4 hover:underline">
					{report.trip_no}
				</a>
				· {formatDateRange(report.trip_start_date, report.trip_end_date)}
			</p>

			{#if report.status === 'REJECTED' && report.reject_reason}
				<div class="mt-6 rounded-md border border-error px-4 py-3">
					<p class="text-caption text-error">반려 사유</p>
					<p class="mt-1 text-body-md text-ink">{report.reject_reason}</p>
				</div>
			{/if}

			<h2 class="mt-10 text-display-sm">비용 처리 부서</h2>
			<div class="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
				<Select
					label="펀드센터 (기본값)"
					bind:value={fundCenterValue}
					options={fundCenters}
					disabled={!editable || busy}
				/>
				<Select
					label="코스트센터 (기본값)"
					bind:value={costCenterValue}
					options={costCenters}
					disabled={!editable || busy}
				/>
			</div>
			{#if editable}
				<div class="mt-4">
					<Button variant="secondary" disabled={busy} onclick={saveCenters}>부서 저장</Button>
				</div>
			{/if}

			<h2 class="mt-10 text-display-sm">자동매칭 후보</h2>
			<p class="mt-1 text-body-sm text-muted">
				출장 기간 전후 1일 이내의 본인 법인카드 사용내역입니다.
			</p>
			<div class="mt-4">
				<MatchPanel {candidates} {busy} {editable} onadd={addCandidate} />
			</div>

			<div class="mt-10 flex flex-wrap items-center justify-between gap-3">
				<h2 class="text-display-sm">정산 항목</h2>
				{#if editable}
					<Button variant="secondary" disabled={busy} onclick={() => (pickerOpen = true)}>
						법인카드 사용내역 보기
					</Button>
				{/if}
			</div>
			<div class="mt-4">
				{#if report.items.length === 0}
					<p class="text-body-sm text-muted">아직 담은 항목이 없습니다.</p>
				{:else}
					<ExpenseItemsTable
						{report}
						{categories}
						{costCenters}
						{fundCenters}
						{editable}
						{busy}
						onupdate={patchItem}
						ondelete={removeItem}
					/>
				{/if}
			</div>

			<h2 class="mt-10 text-display-sm">진행 이력</h2>
			<div class="mt-4">
				<Timeline {entries} />
			</div>
		</div>

		<aside class="lg:sticky lg:top-8 lg:self-start">
			<Card>
				<p class="text-caption text-muted">정산 총액</p>
				<p class="mt-1 text-display-xl text-ink">{formatKrw(report.total_amount_krw)}</p>
				<p class="mt-2 text-caption-sm text-muted">
					{report.user_name} → {report.approver_name ?? '결재자 미지정'}
				</p>

				{#if actionError}
					<p class="mt-4 text-caption-sm text-error" role="alert">{actionError}</p>
				{/if}

				<div class="mt-6 flex flex-col gap-3">
					{#if isOwner && report.status === 'DRAFT'}
						<Button full disabled={busy} onclick={() => act(() => submitExpense(reportId))}>
							제출
						</Button>
					{/if}

					{#if isOwner && report.status === 'REJECTED'}
						<Button
							full
							variant="secondary"
							disabled={busy}
							onclick={() => act(() => reopenExpense(reportId))}
						>
							다시 작성
						</Button>
					{/if}

					{#if isApprover && report.status === 'SUBMITTED'}
						<Button full disabled={busy} onclick={() => act(() => approveExpense(reportId))}>
							승인
						</Button>
						{#if rejecting}
							<Textarea label="반려 사유" bind:value={rejectReason} rows={3} />
							<Button
								full
								variant="secondary"
								disabled={busy}
								onclick={() => act(() => rejectExpense(reportId, rejectReason))}
							>
								반려 확정
							</Button>
							<Button full variant="tertiary" disabled={busy} onclick={() => (rejecting = false)}>
								취소
							</Button>
						{:else}
							<Button full variant="secondary" disabled={busy} onclick={() => (rejecting = true)}>
								반려
							</Button>
						{/if}
					{/if}

					{#if report.status === 'APPROVED'}
						<p class="text-body-sm text-muted">승인 완료 — 출장이 정산완료로 전이되었습니다.</p>
					{/if}
				</div>
			</Card>
		</aside>
	</div>

	<!-- 열 때마다 새로 마운트한다. 담고 닫은 뒤 다시 열면 목록이 최신이어야 한다. -->
	{#if pickerOpen}
		<Modal open title="법인카드 사용내역" onclose={() => (pickerOpen = false)}>
			<CardTransactionPicker bind:this={picker} {busy} {editable} onadd={addTransaction} />
		</Modal>
	{/if}
{/if}
