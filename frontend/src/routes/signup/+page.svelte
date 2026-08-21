<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import { listPublicDepartments, signup } from '$lib/api/signup';
	import type { PublicDepartment } from '$lib/api/types';
	import Button from '$lib/components/Button.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import Select from '$lib/components/Select.svelte';

	let email = $state('');
	let password = $state('');
	let name = $state('');
	let departmentId = $state('');
	let departments = $state<PublicDepartment[]>([]);
	let submitting = $state(false);
	let errorMessage = $state('');
	let done = $state(false);

	const departmentChoices = $derived(
		departments.map((department) => ({
			value: String(department.id),
			label: department.name
		}))
	);

	onMount(async () => {
		try {
			departments = await listPublicDepartments();
		} catch {
			errorMessage = '부서 목록을 불러오지 못했습니다';
		}
	});

	async function handleSubmit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		// 버튼의 disabled만으로는 form.requestSubmit() 경로를 막지 못한다.
		// 가입은 멱등하지 않아 중복 POST가 곧 중복 신청이다.
		if (submitting) return;
		errorMessage = '';
		submitting = true;
		try {
			await signup({
				email,
				password,
				name,
				department_id: Number(departmentId)
			});
			done = true;
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '가입 신청을 보내지 못했습니다';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-canvas px-6">
	<div class="w-full max-w-[400px]">
		<img src="/skon-logo.png" alt="SK온" class="mb-8 h-9 w-auto" />
		{#if done}
			<h1 class="text-display-lg">가입 신청 완료</h1>
			<p class="mt-2 text-body-sm text-muted">
				관리자 승인 후 로그인할 수 있습니다. 승인 전에 로그인하면 대기 중이라고 안내됩니다.
			</p>
			<p class="mt-6 text-caption-sm text-muted">
				<a class="underline" href="/login">로그인으로</a>
			</p>
		{:else}
			<h1 class="text-display-lg">회원가입</h1>
			<p class="mt-2 text-body-sm text-muted">
				관리자 승인 후 로그인할 수 있습니다. 사번·직급·결재자는 승인할 때 관리자가 지정합니다.
			</p>

			<form class="mt-8 flex flex-col gap-4" onsubmit={handleSubmit}>
				<TextInput
					label="이메일"
					type="email"
					bind:value={email}
					placeholder="name@skon.example"
					autocomplete="email"
				/>
				<TextInput label="이름" bind:value={name} placeholder="김출장" autocomplete="name" />
				<Select label="부서" bind:value={departmentId} options={departmentChoices} />
				<TextInput
					label="비밀번호"
					type="password"
					bind:value={password}
					placeholder="8자 이상 · UTF-8 72바이트 이하"
					autocomplete="new-password"
				/>

				{#if errorMessage}
					<p class="text-caption-sm text-error" role="alert">{errorMessage}</p>
				{/if}

				<Button
					type="submit"
					full
					disabled={submitting || !email || !name || !departmentId || !password}
				>
					{submitting ? '보내는 중…' : '가입 신청'}
				</Button>
			</form>

			<p class="mt-6 text-caption-sm text-muted">
				이미 계정이 있으신가요? <a class="underline" href="/login">로그인</a>
			</p>
		{/if}
	</div>
</div>
