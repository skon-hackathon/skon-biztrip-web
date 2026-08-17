<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import AppShell from '$lib/components/AppShell.svelte';
	import { isPublicPath, loginPathFor } from '$lib/nav';
	import { auth } from '$lib/stores/auth.svelte';

	let { children } = $props();

	let restored = $state(false);

	// 복원은 마운트 시 한 번만. $effect 안에서 호출하면 auth 상태 변경이
	// 다시 effect를 트리거해 무한 루프가 된다.
	onMount(async () => {
		// 세션 만료 등으로 401이 나면 스토어가 이 콜백으로 화면을 정리한다.
		// 스토어가 $app/navigation을 직접 import하면 vitest에서 못 돌리므로 주입한다.
		auth.onUnauthorized = () => {
			goto(loginPathFor(page.url.pathname, page.url.search));
		};
		await auth.restore();
		restored = true;
	});

	$effect(() => {
		if (!restored) return;
		if (auth.user === null && !isPublicPath(page.url.pathname)) {
			goto(loginPathFor(page.url.pathname, page.url.search));
		}
	});
</script>

{#if !restored}
	<div class="flex min-h-screen items-center justify-center text-body-sm text-muted">
		불러오는 중…
	</div>
{:else if isPublicPath(page.url.pathname)}
	{@render children()}
{:else if auth.user}
	<AppShell>
		{@render children()}
	</AppShell>
{/if}
