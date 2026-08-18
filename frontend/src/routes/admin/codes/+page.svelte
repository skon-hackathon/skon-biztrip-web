<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createCode,
		createCodeGroup,
		deleteCode,
		deleteCodeGroup,
		listCodeGroups,
		updateCode,
		updateCodeGroup
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { activeLabel } from '$lib/admin';
	import type { AdminCode, AdminCodeGroup } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const groups = new AdminResource<AdminCodeGroup>(listCodeGroups);

	let groupCode = $state('');
	let groupName = $state('');
	let openGroupId = $state<number | null>(null);
	let newCode = $state('');
	let newCodeName = $state('');
	let confirmingGroupId = $state<number | null>(null);
	let confirmingCodeId = $state<number | null>(null);

	// onMount가 Promise를 반환하면 cleanup 함수로 오해될 수 있다. void로 끊는다.
	onMount(() => {
		void groups.load();
	});

	async function submitGroup(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		// 중복 제출 가드는 AdminResource.run 안에 있다.
		const ok = await groups.run(
			() => createCodeGroup({ group_code: groupCode, name: groupName }),
			'코드그룹을 만들지 못했습니다'
		);
		if (ok) {
			groupCode = '';
			groupName = '';
		}
	}

	async function submitCode(event: SubmitEvent, groupId: number): Promise<void> {
		event.preventDefault();
		const ok = await groups.run(
			() => createCode(groupId, { code: newCode, name: newCodeName }),
			'코드를 추가하지 못했습니다'
		);
		if (ok) {
			newCode = '';
			newCodeName = '';
		}
	}

	function toggleGroup(group: AdminCodeGroup): void {
		void groups.run(
			() => updateCodeGroup(group.id, { is_active: !group.is_active }),
			'그룹 상태를 바꾸지 못했습니다'
		);
	}

	function toggleCode(code: AdminCode): void {
		void groups.run(
			() => updateCode(code.id, { is_active: !code.is_active }),
			'코드 상태를 바꾸지 못했습니다'
		);
	}

	async function removeGroup(id: number): Promise<void> {
		const ok = await groups.run(() => deleteCodeGroup(id), '그룹을 삭제하지 못했습니다');
		if (ok) confirmingGroupId = null;
	}

	async function removeCode(id: number): Promise<void> {
		const ok = await groups.run(() => deleteCode(id), '코드를 삭제하지 못했습니다');
		if (ok) confirmingCodeId = null;
	}
</script>

<Card>
	<form onsubmit={submitGroup}>
		<h2 class="text-title-md">새 코드그룹</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-2">
			<TextInput label="그룹코드" bind:value={groupCode} placeholder="RISK_LEVEL" />
			<TextInput label="이름" bind:value={groupName} placeholder="위험도" />
		</div>
		<div class="mt-6">
			<Button type="submit" disabled={groups.busy || !groupCode || !groupName}>
				{groups.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if groups.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{groups.error}</p>
{/if}

{#if groups.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if groups.items.length === 0}
	<EmptyState title="코드그룹이 없습니다" description="위에서 첫 그룹을 만드세요." />
{:else}
	<div class="mt-8 flex flex-col gap-4">
		{#each groups.items as group (group.id)}
			<Card>
				<div class="flex flex-wrap items-center justify-between gap-3">
					<div class="flex items-center gap-3">
						<span class="font-mono text-body-md text-ink">{group.group_code}</span>
						<span class="text-body-sm text-muted">{group.name}</span>
						<Badge tone={group.is_active ? 'success' : 'neutral'}>
							{activeLabel(group.is_active)}
						</Badge>
						<span class="text-caption text-muted">코드 {group.codes.length}개</span>
					</div>
					<div class="flex items-center gap-3">
						<Button
							variant="tertiary"
							onclick={() => (openGroupId = openGroupId === group.id ? null : group.id)}
						>
							{openGroupId === group.id ? '접기' : '코드 보기'}
						</Button>
						<Button variant="tertiary" onclick={() => toggleGroup(group)}>
							{group.is_active ? '중지' : '사용'}
						</Button>
						{#if confirmingGroupId === group.id}
							<Button variant="tertiary" onclick={() => removeGroup(group.id)}>정말 삭제</Button>
							<Button variant="tertiary" onclick={() => (confirmingGroupId = null)}>취소</Button>
						{:else}
							<Button variant="tertiary" onclick={() => (confirmingGroupId = group.id)}>
								삭제
							</Button>
						{/if}
					</div>
				</div>

				{#if openGroupId === group.id}
					<div class="mt-6 overflow-x-auto">
						<table class="w-full min-w-[560px] border-collapse">
							<thead>
								<tr class="border-b border-hairline text-left text-caption text-muted">
									<th class="py-3">코드</th>
									<th class="py-3">이름</th>
									<th class="py-3">정렬</th>
									<th class="py-3">상태</th>
									<th class="py-3"></th>
								</tr>
							</thead>
							<tbody>
								{#each group.codes as code (code.id)}
									<tr class="border-b border-hairline">
										<td class="py-3 font-mono text-body-sm text-ink">{code.code}</td>
										<td class="py-3 text-body-sm text-ink">{code.name}</td>
										<td class="py-3 text-body-sm text-muted">{code.sort_order}</td>
										<td class="py-3">
											<Badge tone={code.is_active ? 'success' : 'neutral'}>
												{activeLabel(code.is_active)}
											</Badge>
										</td>
										<td class="py-3 text-right">
											<Button variant="tertiary" onclick={() => toggleCode(code)}>
												{code.is_active ? '중지' : '사용'}
											</Button>
											{#if confirmingCodeId === code.id}
												<Button variant="tertiary" onclick={() => removeCode(code.id)}>
													정말 삭제
												</Button>
												<Button variant="tertiary" onclick={() => (confirmingCodeId = null)}>
													취소
												</Button>
											{:else}
												<Button variant="tertiary" onclick={() => (confirmingCodeId = code.id)}>
													삭제
												</Button>
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>

					<form onsubmit={(event) => submitCode(event, group.id)} class="mt-6">
						<div class="grid grid-cols-1 gap-4 tablet:grid-cols-2">
							<TextInput label="새 코드" bind:value={newCode} placeholder="HIGH" />
							<TextInput label="새 코드 이름" bind:value={newCodeName} placeholder="높음" />
						</div>
						<div class="mt-4">
							<Button type="submit" disabled={groups.busy || !newCode || !newCodeName}>
								코드 추가
							</Button>
						</div>
					</form>
					<p class="mt-3 text-caption text-muted">
						활성 코드는 삭제할 수 없습니다 — 업무 데이터가 코드값을 문자열로 참조하므로 먼저 중지해야
						합니다.
					</p>
				{/if}
			</Card>
		{/each}
	</div>
{/if}
