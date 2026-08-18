<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createAdminCard,
		deleteAdminCard,
		listAdminCards,
		listUsers,
		updateAdminCard
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { activeLabel } from '$lib/admin';
	import type { AdminCard, AdminUser } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const cards = new AdminResource<AdminCard>(listAdminCards);
	const users = new AdminResource<AdminUser>(async () => (await listUsers({ size: 100 })).items);

	let ownerId = $state('');
	let cardNo = $state('');
	let brand = $state('');
	let confirmingId = $state<number | null>(null);

	onMount(() => {
		void users.load();
		void cards.load();
	});

	const ownerChoices = $derived(
		users.items.map((user) => ({
			value: String(user.id),
			label: `${user.name} · ${user.employee_no}`
		}))
	);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await cards.run(
			() =>
				createAdminCard({
					user_id: Number(ownerId),
					card_no_masked: cardNo,
					brand
				}),
			'카드를 만들지 못했습니다'
		);
		if (ok) {
			ownerId = '';
			cardNo = '';
			brand = '';
		}
	}

	function toggle(card: AdminCard): void {
		void cards.run(
			() => updateAdminCard(card.id, { is_active: !card.is_active }),
			'상태를 바꾸지 못했습니다'
		);
	}

	async function remove(id: number): Promise<void> {
		const ok = await cards.run(() => deleteAdminCard(id), '삭제하지 못했습니다');
		if (ok) confirmingId = null;
	}
</script>

<Card>
	<form onsubmit={submit}>
		<h2 class="text-title-md">새 법인카드</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
			<Select label="소유자" bind:value={ownerId} options={ownerChoices} placeholder="사용자 선택" />
			<TextInput label="카드번호(마스킹)" bind:value={cardNo} placeholder="5327-****-****-1234" />
			<TextInput label="브랜드" bind:value={brand} placeholder="신한" />
		</div>
		<div class="mt-6">
			<Button type="submit" disabled={cards.busy || !ownerId || !cardNo || !brand}>
				{cards.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if cards.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{cards.error}</p>
{/if}

{#if cards.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if cards.items.length === 0}
	<EmptyState title="법인카드가 없습니다" description="위에서 첫 카드를 등록하세요." />
{:else}
	<div class="mt-8 overflow-x-auto">
		<table class="w-full min-w-[720px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">소유자</th>
					<th class="py-3">카드번호</th>
					<th class="py-3">브랜드</th>
					<th class="py-3">상태</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each cards.items as card (card.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 text-body-sm text-ink">{card.user_name}</td>
						<td class="py-3 font-mono text-body-sm text-muted">{card.card_no_masked}</td>
						<td class="py-3 text-body-sm text-muted">{card.brand}</td>
						<td class="py-3">
							<Badge tone={card.is_active ? 'success' : 'neutral'}>
								{activeLabel(card.is_active)}
							</Badge>
						</td>
						<td class="py-3 text-right">
							<Button variant="tertiary" onclick={() => toggle(card)}>
								{card.is_active ? '중지' : '사용'}
							</Button>
							{#if confirmingId === card.id}
								<Button variant="tertiary" onclick={() => remove(card.id)}>정말 삭제</Button>
								<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => (confirmingId = card.id)}>삭제</Button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">거래내역이 있는 카드는 삭제되지 않습니다(409). 중지하세요.</p>
{/if}
