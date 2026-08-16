<script lang="ts">
	import Badge from '$lib/components/Badge.svelte';
	import Card from '$lib/components/Card.svelte';
	import { auth } from '$lib/stores/auth.svelte';

	const ROLE_LABELS: Record<string, string> = {
		EMPLOYEE: '사원',
		MANAGER: '팀장',
		ADMIN: '관리자'
	};
</script>

<h1 class="text-display-xl">안녕하세요, {auth.user?.name}님</h1>
<p class="mt-2 text-body-md text-muted">
	{auth.user?.department_name} · {auth.user?.role ? (ROLE_LABELS[auth.user.role] ?? auth.user.role) : ''}
</p>

<div class="mt-8 grid grid-cols-1 gap-4 md:grid-cols-3">
	<Card>
		<p class="text-caption text-muted">진행 중 출장</p>
		<p class="mt-2 text-display-md">Phase 2에서 연결</p>
		<div class="mt-3"><Badge>준비 중</Badge></div>
	</Card>
	<Card>
		<p class="text-caption text-muted">결재 대기</p>
		<p class="mt-2 text-display-md">Phase 2에서 연결</p>
	</Card>
	<Card>
		<p class="text-caption text-muted">미정산 출장</p>
		<p class="mt-2 text-display-md">Phase 3에서 연결</p>
	</Card>
</div>
