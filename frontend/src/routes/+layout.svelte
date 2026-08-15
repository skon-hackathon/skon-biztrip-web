<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AppShell from '$lib/components/AppShell.svelte';
	import { auth } from '$lib/stores/auth.svelte';

	let { children } = $props();

	const PUBLIC_PATHS = ['/login'];
	let restored = $state(false);

	// 복원은 마운트 시 한 번만. $effect 안에서 호출하면 auth 상태 변경이
	// 다시 effect를 트리거해 무한 루프가 된다.
	onMount(async () => {
		await auth.restore();
		restored = true;
	});

	$effect(() => {
		if (!restored) return;
		if (auth.user === null && !PUBLIC_PATHS.includes(page.url.pathname)) {
			goto('/login');
		}
	});
</script>

{#if !restored}
	<div class="flex min-h-screen items-center justify-center text-body-sm text-muted">
		불러오는 중…
	</div>
{:else if PUBLIC_PATHS.includes(page.url.pathname)}
	{@render children()}
{:else if auth.user}
	<AppShell>
		{@render children()}
	</AppShell>
{/if}
