<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { createApiKey, listApiKeys, revokeApiKey } from '$lib/api/api-keys';
	import type { ApiKeyCreated, ApiKeyScope, ApiKeySummary } from '$lib/api/types';
	import {
		EXPIRY_OPTIONS,
		KEY_STATE_LABELS,
		KEY_STATE_TONES,
		SCOPE_LABELS,
		SCOPE_ORDER
	} from '$lib/api-keys';
	import { formatDateTime } from '$lib/format';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	let keys = $state<ApiKeySummary[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');

	let name = $state('');
	let selectedScopes = $state<ApiKeyScope[]>([]);
	let expiresInDays = $state('');
	let submitting = $state(false);

	/** 발급 직후 한 번만 보여줄 평문. 이 화면을 떠나면 영영 못 본다. */
	let issued = $state<ApiKeyCreated | null>(null);
	let copyNotice = $state('');
	let keyInput = $state<HTMLInputElement | null>(null);
	let confirmingId = $state<number | null>(null);

	onMount(load);

	async function load(): Promise<void> {
		loading = true;
		try {
			keys = await listApiKeys();
			errorMessage = '';
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '키를 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	function toggleScope(scope: ApiKeyScope): void {
		selectedScopes = selectedScopes.includes(scope)
			? selectedScopes.filter((item) => item !== scope)
			: [...selectedScopes, scope];
	}

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		// 버튼 disabled만으로는 form.requestSubmit() 경로를 막지 못한다. 발급은 멱등하지 않다.
		if (submitting) return;
		submitting = true;
		errorMessage = '';
		copyNotice = '';
		try {
			issued = await createApiKey({
				name,
				scopes: selectedScopes,
				expires_in_days: expiresInDays ? Number(expiresInDays) : null
			});
			name = '';
			selectedScopes = [];
			expiresInDays = '';
			await load();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '발급에 실패했습니다';
		} finally {
			submitting = false;
		}
	}

	/**
	 * 운영은 평문 HTTP라 SecureContext가 아니다 — `navigator.clipboard`는 아예 없을 수 있다.
	 * 있으면 쓰고, 없으면 선택 + execCommand로 떨어지고, 그것도 실패하면 직접 복사하라고 말한다.
	 * localhost에서는 첫 경로가 항상 성공하므로 이 폴백은 배포 후에야 검증된다.
	 */
	async function copyKey(): Promise<void> {
		const value = issued?.key ?? '';
		if (!value) return;
		try {
			if (navigator.clipboard?.writeText) {
				await navigator.clipboard.writeText(value);
				copyNotice = '복사했습니다';
				return;
			}
		} catch {
			// 폴백으로 넘어간다
		}
		keyInput?.select();
		const copied = document.execCommand?.('copy');
		copyNotice = copied ? '복사했습니다' : '직접 선택해 복사하세요';
	}

	async function revoke(id: number): Promise<void> {
		try {
			await revokeApiKey(id);
			confirmingId = null;
			if (issued?.id === id) issued = null;
			await load();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '폐기에 실패했습니다';
		}
	}
</script>

<div class="flex items-center justify-between">
	<h1 class="text-display-xl">API 키</h1>
	<!-- 전체 새로고침(window.location)을 쓰지 않는다 — 인증 스토어가 restore를 다시 돌아야 한다. -->
	<Button variant="secondary" onclick={() => goto('/developers')}>개발자 가이드</Button>
</div>

<p class="mt-4 text-body-md text-muted">
	여기서 발급한 키로 외부 Agent가 웹 화면과 <strong>같은 엔드포인트</strong>를 호출합니다. 키의 권한은
	선택한 스코프까지만입니다.
</p>

{#if issued}
	<div class="mt-8 rounded-md border-2 border-primary p-6">
		<h2 class="text-title-md">발급된 키 — 지금 복사하세요</h2>
		<p class="mt-2 text-body-sm text-error">
			이 값은 <strong>다시 볼 수 없습니다.</strong> 서버에는 해시만 저장되며, 잃어버리면 새 키를 발급해야
			합니다.
		</p>
		<div class="mt-4 flex gap-3">
			<input
				bind:this={keyInput}
				value={issued.key}
				readonly
				aria-label="발급된 API 키"
				class="h-14 flex-1 rounded-sm border border-hairline bg-surface-soft px-3 font-mono text-body-sm text-ink"
			/>
			<Button onclick={copyKey}>복사</Button>
			<Button variant="secondary" onclick={() => (issued = null)}>닫기</Button>
		</div>
		{#if copyNotice}
			<p class="mt-2 text-body-sm text-muted" role="status">{copyNotice}</p>
		{/if}
	</div>
{/if}

<Card>
	<form onsubmit={handleSubmit} class="mt-0">
		<h2 class="text-title-md">새 키 발급</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
			<TextInput label="이름" bind:value={name} placeholder="정산 자동화 Agent" />
			<Select label="만료" bind:value={expiresInDays} options={EXPIRY_OPTIONS} placeholder="만료 선택" />
		</div>
		<fieldset class="mt-6">
			<legend class="text-caption text-muted">스코프</legend>
			<div class="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
				{#each SCOPE_ORDER as scope (scope)}
					<label class="flex items-center gap-2 text-body-sm text-ink">
						<input
							type="checkbox"
							class="h-4 w-4"
							checked={selectedScopes.includes(scope)}
							onchange={() => toggleScope(scope)}
						/>
						<span class="font-mono text-body-sm">{scope}</span>
						<span class="text-muted">{SCOPE_LABELS[scope]}</span>
					</label>
				{/each}
			</div>
		</fieldset>
		<div class="mt-6">
			<Button type="submit" disabled={submitting || !name || selectedScopes.length === 0}>
				{submitting ? '발급 중…' : '발급'}
			</Button>
		</div>
	</form>
</Card>

{#if errorMessage}
	<p class="mt-6 text-body-sm text-error" role="alert">{errorMessage}</p>
{/if}

<h2 class="mt-12 text-title-md">발급된 키</h2>
{#if loading}
	<p class="mt-4 text-body-sm text-muted">불러오는 중…</p>
{:else if keys.length === 0}
	<EmptyState title="발급된 키가 없습니다" description="위에서 첫 키를 발급하세요." />
{:else}
	<table class="mt-4 w-full border-collapse">
		<thead>
			<tr class="border-b border-hairline text-left text-caption text-muted">
				<th class="py-3">이름</th>
				<th class="py-3">키</th>
				<th class="py-3">스코프</th>
				<th class="py-3">상태</th>
				<th class="py-3">마지막 사용</th>
				<th class="py-3">만료</th>
				<th class="py-3"></th>
			</tr>
		</thead>
		<tbody>
			{#each keys as key (key.id)}
				<tr class="border-b border-hairline">
					<td class="py-3 text-body-sm text-ink">{key.name}</td>
					<td class="py-3 font-mono text-body-sm text-muted">{key.key_prefix}…</td>
					<td class="py-3 text-body-sm text-muted">{key.scopes.join(', ')}</td>
					<td class="py-3">
						<Badge tone={KEY_STATE_TONES[key.state]}>{KEY_STATE_LABELS[key.state]}</Badge>
					</td>
					<td class="py-3 text-body-sm text-muted">
						{key.last_used_at ? formatDateTime(key.last_used_at) : '없음'}
					</td>
					<td class="py-3 text-body-sm text-muted">
						{key.expires_at ? formatDateTime(key.expires_at) : '없음'}
					</td>
					<td class="py-3 text-right">
						{#if key.state === 'ACTIVE'}
							{#if confirmingId === key.id}
								<Button variant="tertiary" onclick={() => revoke(key.id)}>정말 폐기</Button>
								<Button variant="tertiary" onclick={() => (confirmingId = null)}>취소</Button>
							{:else}
								<Button variant="tertiary" onclick={() => (confirmingId = key.id)}>폐기</Button>
							{/if}
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
{/if}
