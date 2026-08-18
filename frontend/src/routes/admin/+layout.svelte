<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { ADMIN_TABS } from '$lib/admin';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	// 서버가 403으로 막지만, 화면까지 오면 빈 표와 에러 문구만 보인다.
	// 라우트 가드는 UX용이고 권한의 근거는 서버다.
	const isAdmin = $derived(auth.user?.role === 'ADMIN');

	$effect(() => {
		if (auth.user && !isAdmin) goto('/');
	});

	function isActive(href: string): boolean {
		return page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);
	}
</script>

{#if isAdmin}
	<h1 class="text-display-xl">관리</h1>
	<p class="mt-2 text-body-md text-muted">
		마스터 데이터를 고치면 출장·정산 화면의 드롭다운과 <strong>API 검증</strong>이 함께 바뀝니다.
	</p>

	<nav aria-label="관리 메뉴" class="mt-8 flex gap-6 overflow-x-auto border-b border-hairline">
		{#each ADMIN_TABS as tab (tab.href)}
			<a
				href={tab.href}
				aria-current={isActive(tab.href) ? 'page' : undefined}
				class="shrink-0 pb-3 text-nav-link {isActive(tab.href)
					? 'border-b-2 border-ink text-ink'
					: 'text-muted hover:text-ink'}"
			>
				{tab.label}
			</a>
		{/each}
	</nav>

	<div class="mt-8">
		{@render children()}
	</div>
{/if}
