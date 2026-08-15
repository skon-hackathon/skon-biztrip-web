<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const tabs = [
		{ href: '/trips', label: '출장' },
		{ href: '/expenses', label: '정산' },
		{ href: '/developers', label: '개발자' }
	];

	function isActive(href: string): boolean {
		return page.url.pathname.startsWith(href);
	}

	function signOut(): void {
		auth.clear();
		goto('/login');
	}
</script>

<div class="min-h-screen bg-canvas">
	<header class="flex h-20 items-center border-b border-hairline px-8">
		<a href="/" class="flex items-center">
			<img src="/skon-logo.png" alt="SK온 출장시스템" class="h-8 w-auto" />
		</a>

		<nav class="mx-auto flex items-center gap-8">
			{#each tabs as tab (tab.href)}
				<a
					href={tab.href}
					class="pb-1 text-nav-link {isActive(tab.href)
						? 'border-b-2 border-ink text-ink'
						: 'text-muted hover:text-ink'}"
				>
					{tab.label}
				</a>
			{/each}
		</nav>

		<div class="flex items-center gap-4">
			{#if auth.user}
				<span class="text-body-sm text-muted">{auth.user.name} · {auth.user.department_name}</span>
				<button
					onclick={signOut}
					class="h-10 rounded-full border border-hairline px-4 text-button-sm text-ink hover:shadow-float"
				>
					로그아웃
				</button>
			{/if}
		</div>
	</header>

	<main class="mx-auto max-w-[1280px] px-8 py-12">
		{@render children()}
	</main>
</div>
