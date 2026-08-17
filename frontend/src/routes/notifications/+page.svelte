<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { listNotifications, markNotificationRead } from '$lib/api/notifications';
	import type { NotificationItem } from '$lib/api/types';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { formatDateTime } from '$lib/format';
	import { notifications } from '$lib/stores/notifications.svelte';

	let items = $state<NotificationItem[]>([]);
	let loading = $state(true);
	let errorMessage = $state('');
	let busyId = $state<number | null>(null);

	onMount(load);

	async function load(): Promise<void> {
		loading = true;
		errorMessage = '';
		try {
			const page = await listNotifications({ size: 50 });
			items = page.items;
			notifications.unread = page.unread;
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '알림을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	async function open(item: NotificationItem): Promise<void> {
		if (busyId !== null) return;
		busyId = item.id;
		try {
			if (!item.is_read) {
				const updated = await markNotificationRead(item.id);
				items = items.map((row) => (row.id === updated.id ? updated : row));
				notifications.unread = Math.max(0, notifications.unread - 1);
			}
			if (item.link_url) await goto(item.link_url);
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '처리하지 못했습니다';
		} finally {
			busyId = null;
		}
	}
</script>

<h1 class="text-display-xl">알림</h1>

{#if errorMessage}
	<p class="mt-8 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else if loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if items.length > 0}
	<ul class="mt-8 flex flex-col gap-3">
		{#each items as item (item.id)}
			<li>
				<button
					onclick={() => open(item)}
					class="w-full rounded-md border px-5 py-4 text-left hover:shadow-float {item.is_read
						? 'border-hairline'
						: 'border-ink'}"
				>
					<div class="flex items-center justify-between gap-4">
						<p class="text-title-sm text-ink">{item.title}</p>
						{#if !item.is_read}
							<span class="h-2 w-2 shrink-0 rounded-full bg-primary"></span>
						{/if}
					</div>
					<p class="mt-1 text-body-sm text-muted">{item.body}</p>
					<p class="mt-2 text-caption-sm text-muted">{formatDateTime(item.created_at)}</p>
				</button>
			</li>
		{/each}
	</ul>
{:else}
	<div class="mt-8">
		<EmptyState title="알림이 없습니다" description="결재 요청이나 결과가 오면 여기에 쌓입니다." />
	</div>
{/if}
