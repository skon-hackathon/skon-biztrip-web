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
	const isAdmin = $derived(auth.user?.role === 'ADMIN');

	let menuOpen = $state(false);

	// 라우트가 바뀔 때마다 미읽음 수를 새로 센다. 상신·승인이 다른 화면에서
	// 일어나므로 마운트 시 한 번만 세면 뱃지가 곧 낡는다.
	$effect(() => {
		void page.url.pathname;
		void notifications.refresh();
	});

	// 내비게이션이 끝나면 시트를 닫는다. 열어둔 채로 화면이 바뀌면 뒤 화면이 가려진다.
	$effect(() => {
		void page.url.pathname;
		menuOpen = false;
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
	<header
		class="grid h-20 grid-cols-[1fr_auto] items-center border-b border-hairline px-4 tablet:grid-cols-[1fr_auto_1fr] tablet:px-8"
	>
		<a href="/" class="flex items-center justify-self-start">
			<img src="/skon-logo.png" alt="SK온 출장시스템" class="h-8 w-auto" />
		</a>

		<nav aria-label="주 메뉴" class="hidden items-center justify-self-center gap-8 tablet:flex">
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

		<div class="hidden items-center justify-self-end gap-4 tablet:flex">
			{#if auth.user}
				<a
					href="/cards"
					aria-current={isActive('/cards') ? 'page' : undefined}
					class="text-button-sm {isActive('/cards') ? 'text-ink' : 'text-muted hover:text-ink'}"
				>
					카드
				</a>
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
				{#if isAdmin}
					<a
						href="/admin/codes"
						aria-current={isActive('/admin') ? 'page' : undefined}
						class="text-button-sm {isActive('/admin') ? 'text-ink' : 'text-muted hover:text-ink'}"
					>
						관리
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

		<!-- 744px 미만: 로고 + 햄버거만 남긴다 (DESIGN.md Mobile 행). -->
		<button
			type="button"
			onclick={() => (menuOpen = !menuOpen)}
			aria-expanded={menuOpen}
			aria-controls="mobile-menu"
			aria-label="메뉴"
			class="relative flex h-10 w-10 items-center justify-center justify-self-end rounded-full hover:shadow-float tablet:hidden"
		>
			<svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round" />
			</svg>
			{#if notifications.unread > 0}
				<span
					class="absolute top-0 right-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-badge text-white"
				>
					{notifications.unread > 99 ? '99+' : notifications.unread}
				</span>
			{/if}
		</button>
	</header>

	{#if menuOpen && auth.user}
		<div id="mobile-menu" class="border-b border-hairline px-4 py-4 tablet:hidden">
			<nav aria-label="모바일 메뉴" class="flex flex-col gap-1">
				{#each tabs as tab (tab.href)}
					<a href={tab.href} class="py-3 text-nav-link text-ink">{tab.label}</a>
				{/each}
				<a href="/cards" class="py-3 text-nav-link text-ink">카드</a>
				{#if canApprove}
					<a href="/approvals" class="py-3 text-nav-link text-ink">결재함</a>
				{/if}
				{#if isAdmin}
					<a href="/admin/codes" class="py-3 text-nav-link text-ink">관리</a>
				{/if}
				<a href="/notifications" class="py-3 text-nav-link text-ink">
					알림{notifications.unread > 0 ? ` (${notifications.unread})` : ''}
				</a>
			</nav>
			<div class="mt-4 flex items-center justify-between border-t border-hairline pt-4">
				<span class="text-body-sm text-muted">
					{auth.user.name} · {auth.user.department_name}
				</span>
				<button
					onclick={signOut}
					class="h-10 rounded-full border border-hairline px-4 text-button-sm text-ink"
				>
					로그아웃
				</button>
			</div>
		</div>
	{/if}

	<main class="mx-auto max-w-[1280px] px-4 py-8 tablet:px-8 tablet:py-12">
		{@render children()}
	</main>
</div>
