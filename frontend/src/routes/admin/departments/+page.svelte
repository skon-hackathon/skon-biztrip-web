<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createDepartment,
		deleteDepartment,
		listDepartments,
		updateDepartment
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { departmentNameById, departmentOptions } from '$lib/admin';
	import type { Department } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const departments = new AdminResource<Department>(listDepartments);

	let code = $state('');
	let name = $state('');
	let parentId = $state('');
	let editingId = $state<number | null>(null);
	let editingName = $state('');
	let confirmingId = $state<number | null>(null);

	onMount(() => {
		void departments.load();
	});

	const parentChoices = $derived(departmentOptions(departments.items, { noneLabel: '상위 없음' }));

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await departments.run(
			() => createDepartment({ code, name, parent_id: parentId ? Number(parentId) : null }),
			'부서를 만들지 못했습니다'
		);
		if (ok) {
			code = '';
			name = '';
			parentId = '';
		}
	}

	function startEdit(department: Department): void {
		editingId = department.id;
		editingName = department.name;
	}

	async function saveEdit(id: number): Promise<void> {
		const ok = await departments.run(
			() => updateDepartment(id, { name: editingName }),
			'이름을 바꾸지 못했습니다'
		);
		if (ok) editingId = null;
	}

	async function remove(id: number): Promise<void> {
		const ok = await departments.run(() => deleteDepartment(id), '삭제하지 못했습니다');
		if (ok) confirmingId = null;
	}
</script>

<Card>
	<form onsubmit={submit}>
		<h2 class="text-title-md">새 부서</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
			<TextInput label="부서코드" bind:value={code} placeholder="D400" />
			<TextInput label="이름" bind:value={name} placeholder="품질보증팀" />
			<Select
				label="상위 부서"
				bind:value={parentId}
				options={parentChoices}
				placeholder="상위 없음"
			/>
		</div>
		<div class="mt-6">
			<Button type="submit" disabled={departments.busy || !code || !name}>
				{departments.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if departments.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{departments.error}</p>
{/if}

{#if departments.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if departments.items.length === 0}
	<EmptyState title="부서가 없습니다" description="위에서 첫 부서를 만드세요." />
{:else}
	<div class="mt-8 overflow-x-auto">
		<table class="w-full min-w-[600px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">코드</th>
					<th class="py-3">이름</th>
					<th class="py-3">상위</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each departments.items as department (department.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 font-mono text-body-sm text-ink">{department.code}</td>
						<td class="py-3 text-body-sm text-ink">
							{#if editingId === department.id}
								<TextInput label="이름" bind:value={editingName} />
							{:else}
								{department.name}
							{/if}
						</td>
						<td class="py-3 text-body-sm text-muted">
							{departmentNameById(departments.items, department.parent_id)}
						</td>
						<td class="py-3 text-right">
							{#if editingId === department.id}
								<Button variant="tertiary" onclick={() => saveEdit(department.id)}>저장</Button>
								<Button variant="tertiary" onclick={() => (editingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => startEdit(department)}>이름 변경</Button>
								{#if confirmingId === department.id}
									<Button variant="tertiary" onclick={() => remove(department.id)}>
										정말 삭제
									</Button>
									<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
								{:else}
									<Button variant="tertiary" onclick={() => (confirmingId = department.id)}>
										삭제
									</Button>
								{/if}
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">
		사용자·센터가 속한 부서는 삭제되지 않습니다(409 HAS_DEPENDENTS).
	</p>
{/if}
