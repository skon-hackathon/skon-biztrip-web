<script lang="ts">
	import { onMount } from 'svelte';
	import {
		createUser,
		listDepartments,
		listUsers,
		setUserPassword,
		updateUser
	} from '$lib/api/admin';
	import { AdminResource } from '$lib/stores/admin-resource.svelte';
	import { ROLE_LABELS, activeLabel, departmentOptions } from '$lib/admin';
	import { auth } from '$lib/stores/auth.svelte';
	import type { AdminUser, Department, UserRole } from '$lib/api/types';
	import Badge from '$lib/components/Badge.svelte';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';

	const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
		{ value: 'EMPLOYEE', label: ROLE_LABELS.EMPLOYEE },
		{ value: 'MANAGER', label: ROLE_LABELS.MANAGER },
		{ value: 'ADMIN', label: ROLE_LABELS.ADMIN }
	];

	let search = $state('');
	// 목록은 페이지 응답이므로 items만 뽑아 AdminResource에 담는다.
	const users = new AdminResource<AdminUser>(async () => {
		const page = await listUsers({ q: search || undefined, size: 100 });
		return page.items;
	});
	const departments = new AdminResource<Department>(listDepartments);

	let email = $state('');
	let password = $state('');
	let name = $state('');
	let employeeNo = $state('');
	let departmentId = $state('');
	let positionCode = $state('STAFF');
	// Select의 bind:value는 string이다. UserRole로 선언하면 svelte-check가 에러를 낸다.
	let role = $state('EMPLOYEE');

	let resettingId = $state<number | null>(null);
	let newPassword = $state('');

	onMount(() => {
		void departments.load();
		void users.load();
	});

	const departmentChoices = $derived(departmentOptions(departments.items));

	async function submit(event: SubmitEvent): Promise<void> {
		event.preventDefault();
		const ok = await users.run(
			() =>
				createUser({
					email,
					password,
					name,
					employee_no: employeeNo,
					department_id: Number(departmentId),
					position_code: positionCode,
					role: role as UserRole
				}),
			'사용자를 만들지 못했습니다'
		);
		if (ok) {
			email = '';
			password = '';
			name = '';
			employeeNo = '';
			departmentId = '';
			role = 'EMPLOYEE';
		}
	}

	function toggleActive(user: AdminUser): void {
		void users.run(
			() => updateUser(user.id, { is_active: !user.is_active }),
			'상태를 바꾸지 못했습니다'
		);
	}

	function changeRole(user: AdminUser, next: UserRole): void {
		void users.run(() => updateUser(user.id, { role: next }), '역할을 바꾸지 못했습니다');
	}

	async function resetPassword(id: number): Promise<void> {
		const ok = await users.run(
			() => setUserPassword(id, newPassword),
			'비밀번호를 바꾸지 못했습니다'
		);
		if (ok) {
			resettingId = null;
			newPassword = '';
		}
	}
</script>

<Card>
	<form onsubmit={submit}>
		<h2 class="text-title-md">새 사용자</h2>
		<div class="mt-4 grid grid-cols-1 gap-4 tablet:grid-cols-3">
			<TextInput label="이메일" type="email" bind:value={email} placeholder="name@skon.example" />
			<TextInput label="이름" bind:value={name} placeholder="김출장" />
			<TextInput label="사번" bind:value={employeeNo} placeholder="E0100" />
			<Select label="부서" bind:value={departmentId} options={departmentChoices} />
			<TextInput label="직급코드" bind:value={positionCode} placeholder="STAFF" />
			<Select label="역할" bind:value={role} options={ROLE_OPTIONS} />
			<TextInput
				label="초기 비밀번호"
				type="password"
				bind:value={password}
				placeholder="8자 이상 · UTF-8 72바이트 이하"
			/>
		</div>
		<div class="mt-6">
			<Button
				type="submit"
				disabled={users.busy || !email || !name || !employeeNo || !departmentId || !password}
			>
				{users.busy ? '처리 중…' : '추가'}
			</Button>
		</div>
	</form>
</Card>

{#if users.error}
	<p class="mt-6 text-body-sm text-error" role="alert">{users.error}</p>
{/if}

<div class="mt-8 flex items-end gap-3">
	<div class="w-full max-w-md">
		<TextInput label="검색" bind:value={search} placeholder="이름 · 이메일 · 사번" />
	</div>
	<Button variant="secondary" onclick={() => users.load()}>검색</Button>
</div>

{#if users.loading}
	<p class="mt-8 text-body-sm text-muted">불러오는 중…</p>
{:else if users.items.length === 0}
	<EmptyState title="사용자가 없습니다" description="검색어를 바꾸거나 새 사용자를 추가하세요." />
{:else}
	<div class="mt-6 overflow-x-auto">
		<table class="w-full min-w-[900px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">사번</th>
					<th class="py-3">이름</th>
					<th class="py-3">이메일</th>
					<th class="py-3">부서</th>
					<th class="py-3">결재자</th>
					<th class="py-3">역할</th>
					<th class="py-3">상태</th>
					<th class="py-3"></th>
				</tr>
			</thead>
			<tbody>
				{#each users.items as user (user.id)}
					<tr class="border-b border-hairline">
						<td class="py-3 font-mono text-body-sm text-muted">{user.employee_no}</td>
						<td class="py-3 text-body-sm text-ink">{user.name}</td>
						<td class="py-3 text-body-sm text-muted">{user.email}</td>
						<td class="py-3 text-body-sm text-muted">{user.department_name}</td>
						<td class="py-3 text-body-sm text-muted">{user.manager_name ?? '—'}</td>
						<td class="py-3">
							<select
								aria-label="{user.name} 역할"
								value={user.role}
								onchange={(event) => changeRole(user, event.currentTarget.value as UserRole)}
								class="h-10 rounded-sm border border-hairline bg-canvas px-2 text-body-sm text-ink"
							>
								{#each ROLE_OPTIONS as option (option.value)}
									<option value={option.value}>{option.label}</option>
								{/each}
							</select>
						</td>
						<td class="py-3">
							<Badge tone={user.is_active ? 'success' : 'neutral'}>
								{activeLabel(user.is_active)}
							</Badge>
						</td>
						<td class="py-3 text-right">
							{#if resettingId === user.id}
								<div class="flex items-center justify-end gap-2">
									<input
										type="password"
										bind:value={newPassword}
										aria-label="{user.name} 새 비밀번호"
										class="h-10 rounded-sm border border-hairline px-2 text-body-sm"
									/>
									<Button variant="tertiary" onclick={() => resetPassword(user.id)}>저장</Button>
									<Button variant="tertiary" onclick={() => (resettingId = null)}>취소</Button>
								</div>
							{:else}
								<Button variant="tertiary" onclick={() => (resettingId = user.id)}>
									비밀번호
								</Button>
								<Button
									variant="tertiary"
									disabled={user.id === auth.user?.id}
									onclick={() => toggleActive(user)}
								>
									{user.is_active ? '비활성화' : '활성화'}
								</Button>
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-caption text-muted">
		사용자는 삭제할 수 없습니다 — 출장·정산·카드가 참조합니다. 비활성화하면 로그인이 즉시 막힙니다.
		자기 자신은 강등·비활성화할 수 없습니다(409).
	</p>
{/if}
