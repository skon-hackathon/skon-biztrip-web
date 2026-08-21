<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { ApiError } from '$lib/api/client';
	import { safeRedirect } from '$lib/nav';
	import Button from '$lib/components/Button.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import { auth } from '$lib/stores/auth.svelte';

	let email = $state('user1@skon.example');
	let password = $state('skon1234!');
	let errorMessage = $state('');
	let submitting = $state(false);

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		if (submitting) return;
		errorMessage = '';
		submitting = true;
		try {
			await auth.login(email, password);
			await goto(safeRedirect(page.url.searchParams.get('redirect')));
		} catch (error) {
			errorMessage =
				error instanceof ApiError ? error.message : '로그인 중 문제가 발생했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-canvas px-6">
	<div class="w-full max-w-[400px]">
		<img src="/skon-logo.png" alt="SK온" class="mb-8 h-9 w-auto" />
		<h1 class="text-display-lg">출장시스템 로그인</h1>
		<p class="mt-2 text-body-sm text-muted">사내 계정으로 로그인하세요.</p>

		<form class="mt-8 flex flex-col gap-4" onsubmit={handleSubmit}>
			<TextInput
				label="이메일"
				type="email"
				bind:value={email}
				placeholder="name@skon.example"
				autocomplete="username"
			/>
			<TextInput label="비밀번호" type="password" bind:value={password} autocomplete="current-password" />

			{#if errorMessage}
				<p class="text-caption-sm text-error" role="alert">{errorMessage}</p>
			{/if}

			<Button type="submit" full disabled={submitting}>
				{submitting ? '로그인 중…' : '로그인'}
			</Button>
		</form>

		<p class="mt-6 text-caption-sm text-muted">
			데모 계정 — 사원 user1@skon.example / 팀장 manager1@skon.example / 관리자 admin@skon.example ·
			비밀번호 공통 skon1234!
		</p>

		<p class="mt-6 text-caption text-muted">
			계정이 없으신가요? <a class="underline" href="/signup">회원가입</a>
		</p>
	</div>
</div>
