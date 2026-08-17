<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { notifications } from '$lib/stores/notifications.svelte';
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	const tabs = [
		{ href: '/trips', label: '출장' },
		{ href: '/expenses', label: '정산' },
		{ href: '/developers', label: '개발자' }
	];

	// 결재함은 결재자 역할에게만 의미가 있으므로 우측 블록에 조건부로 둔다.
	// 가운데 3-탭은 DESIGN.md의 3-product tab이라 늘리지 않는다.
	const canApprove = $derived(auth.user?.role === 'MANAGER' || auth.user?.role === 'ADMIN');

	// 라우트가 바뀔 때마다 미읽음 수를 새로 센다. 상신·승인이 다른 화면에서
	// 일어나므로 마운트 시 한 번만 세면 뱃지가 곧 낡는다.
	$effect(() => {
		void page.url.pathname;
		void notifications.refresh();
	});

	function isActive(href: string): boolean {
		const path = page.url.pathname;
		return path === href || path.startsWith(`${href}/`);
	}

	function signOut(): void {
		auth.clear();
		notifications.reset();
		goto('/login');
	}
</script>

<div class="min-h-screen bg-canvas">
	<header class="grid h-20 grid-cols-[1fr_auto_1fr] items-center border-b border-hairline px-8">
		<a href="/" class="flex items-center justify-self-start">
			<img src="/skon-logo.png" alt="SK온 출장시스템" class="h-8 w-auto" />
		</a>

		<nav aria-label="주 메뉴" class="flex items-center justify-self-center gap-8">
			{#each tabs as tab (tab.href)}
				<a
					href={tab.href}
					aria-current={isActive(tab.href) ? 'page' : undefined}
					class="pb-1 text-nav-link {isActive(tab.href)
						? 'border-b-2 border-ink text-ink'
						: 'text-muted hover:text-ink'}"
				>
					{tab.label}
				</a>
			{/each}
		</nav>

		<div class="flex items-center justify-self-end gap-4">
			{#if auth.user}
				{#if canApprove}
					<a
						href="/approvals"
						aria-current={isActive('/approvals') ? 'page' : undefined}
						class="text-button-sm {isActive('/approvals')
							? 'text-ink'
							: 'text-muted hover:text-ink'}"
					>
						결재함
					</a>
				{/if}
				<a
					href="/notifications"
					aria-label="알림"
					class="relative flex h-10 w-10 items-center justify-center rounded-full hover:shadow-float"
				>
					<svg
						viewBox="0 0 24 24"
						class="h-5 w-5"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M6 9a6 6 0 1112 0c0 4 1.5 5 1.5 5h-15S6 13 6 9z" stroke-linejoin="round" />
						<path d="M10 19a2 2 0 004 0" stroke-linecap="round" />
					</svg>
					{#if notifications.unread > 0}
						<span
							class="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-badge text-white"
						>
							{notifications.unread > 99 ? '99+' : notifications.unread}
						</span>
					{/if}
				</a>
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
