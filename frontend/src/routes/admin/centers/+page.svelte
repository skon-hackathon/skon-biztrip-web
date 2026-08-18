<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createCenter,
		deleteCenter,
		listCenters,
		listDepartments,
		updateCenter
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { activeLabel, departmentNameById, departmentOptions } from '$lib/admin';
	import type { AdminCenter, CenterKind, Department } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const KINDS: { value: CenterKind; label: string }[] = [
		{ value: 'fund-centers', label: 'Fund Center (비용처리)' },
		{ value: 'cost-centers', label: 'Cost Center (비용사용)' }
	];

	let kind = $state<CenterKind>('fund-centers');
	// 로더가 kind를 클로저로 읽으므로 탭을 바꾸고 load()만 다시 부르면 된다.
	const centers = new AdminResource<AdminCenter>(() => listCenters(kind));
	const departments = new AdminResource<Department>(listDepartments);

	let code = $state('');
	let name = $state('');
	let departmentId = $state('');
	let confirmingId = $state<number | null>(null);

	onMount(() => {
		void departments.load();
	});

	$effect(() => {
		void kind;
		void centers.load();
	});

	const departmentChoices = $derived(
		departmentOptions(departments.items, { noneLabel: '부서 없음' })
	);

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await centers.run(
			() =>
				createCenter(kind, {
					code,
					name,
					department_id: departmentId ? Number(departmentId) : null
				}),
			'센터를 만들지 못했습니다'
		);
		if (ok) {
			code = '';
			name = '';
			departmentId = '';
		}
	}

	function toggle(center: AdminCenter): void {
		void centers.run(
			() => updateCenter(kind, center.id, { is_active: !center.is_active }),
			'상태를 바꾸지 못했습니다'
		);
	}

	async function remove(id: number): Promise<void> {
		const ok = await centers.run(() => deleteCenter(kind, id), '삭제하지 못했습니다');
		if (ok) confirmingId = null;
	}
</script>

<div class="flex flex-wrap gap-3">
	{#each KINDS as option (option.value)}
		<button
			type="button"
			onclick={() => (kind = option.value)}
			aria-pressed={kind === option.value}
			class="rounded-full px-5 py-2.5 text-button-sm {kind === option.value
				? 'bg-ink text-white'
				: 'border border-hairline text-ink hover:shadow-float'}"
		>
			{option.label}
		</button>
	{/each}
</div>

<div class="mt-6">
	<Card>
		<form onsubmit={submit}>
			<h2 class="text-title-md">새 센터</h2>
			<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
				<TextInput label="코드" bind:value={code} placeholder="FC1090" />
				<TextInput label="이름" bind:value={name} placeholder="배터리연구소" />
				<Select
					label="부서"
					bind:value={departmentId}
					options={departmentChoices}
					placeholder="부서 없음"
				/>
			</div>
			<div class="mt-6">
				<Button type="submit" disabled={centers.busy || !code || !name}>
					{centers.busy ? '처리 중…' : '추가'}
				</Button>
			</div>
		</form>
	</Card>
</div>

{#if centers.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{centers.error}</p>
{/if}

{#if centers.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if centers.items.length === 0}
	<EmptyState title="센터가 없습니다" description="위에서 첫 센터를 만드세요." />
{:else}
	<div class="mt-8 overflow-x-auto">
		<table class="w-full min-w-[640px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">코드</th>
					<th class="py-3">이름</th>
					<th class="py-3">부서</th>
					<th class="py-3">상태</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each centers.items as center (center.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 font-mono text-body-sm text-ink">{center.code}</td>
						<td class="py-3 text-body-sm text-ink">{center.name}</td>
						<td class="py-3 text-body-sm text-muted">
							{departmentNameById(departments.items, center.department_id)}
						</td>
						<td class="py-3">
							<Badge tone={center.is_active ? 'success' : 'neutral'}>
								{activeLabel(center.is_active)}
							</Badge>
						</td>
						<td class="py-3 text-right">
							<Button variant="tertiary" onclick={() => toggle(center)}>
								{center.is_active ? '중지' : '사용'}
							</Button>
							{#if confirmingId === center.id}
								<Button variant="tertiary" onclick={() => remove(center.id)}>정말 삭제</Button>
								<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => (confirmingId = center.id)}>삭제</Button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">
		출장·정산서가 참조하는 센터는 삭제되지 않습니다(409). 쓰지 않으려면 중지하세요.
	</p>
{/if}
