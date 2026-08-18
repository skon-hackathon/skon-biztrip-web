<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { ApiError } from '$lib/api/client';
	import { listScopes } from '$lib/api/meta';
	import type { ScopeInfo } from '$lib/api/types';
	import { curlSnippet } from '$lib/api-keys';
	import Button from '$lib/components/Button.svelte';
	import Card from '$lib/components/Card.svelte';

	let scopes = $state<ScopeInfo[]>([]);
	let errorMessage = $state('');

	// 스코프 표를 화면에 하드코딩하지 않는다 — 백엔드의 SCOPE_REQUIREMENTS에서 뽑아
	// 내려주므로 코드와 문서가 어긋날 수 없다.
	onMount(async () => {
		try {
			scopes = await listScopes();
		} catch (error) {
			errorMessage = error instanceof ApiError ? error.message : '스코프를 불러오지 못했습니다';
		}
	});

	const examples = [
		{
			title: '1. 내 출장 목록',
			snippet: curlSnippet({ method: 'GET', path: '/api/v1/trips?scope=mine&status=DRAFT' }),
			scope: 'trips:read'
		},
		{
			title: '2. 출장 신청',
			snippet: curlSnippet({
				method: 'POST',
				path: '/api/v1/trips',
				// 코드값은 /api/v1/codes가 내려주는 실제 값이다. 가짜 값을 예제에 쓰면
				// 그대로 복사한 사용자가 400 INVALID_CODE를 만난다.
				body: {
					title: '울산 공장 점검',
					purpose_code: 'CUSTOMER',
					purpose_detail: '라인 점검 및 협력사 미팅',
					destination_type_code: 'DOMESTIC',
					country_code: 'KR',
					city: '울산',
					start_date: '2026-09-01',
					end_date: '2026-09-02',
					transport_code: 'AIR',
					accommodation_code: 'HOTEL',
					cost_center_code: 'CC2100',
					estimated_cost: '300000'
				}
			}),
			scope: 'trips:write'
		},
		{
			title: '3. 상신',
			snippet: curlSnippet({ method: 'POST', path: '/api/v1/trips/41/submit' }),
			scope: 'trips:write'
		},
		{
			title: '4. 정산서 생성 후 카드거래 자동매칭 후보 조회',
			snippet: curlSnippet({ method: 'GET', path: '/api/v1/expenses/13/match-candidates' }),
			scope: 'expenses:read'
		},
		{
			title: '5. 정산 항목 담기',
			snippet: curlSnippet({
				method: 'POST',
				path: '/api/v1/expenses/13/items',
				body: { card_transaction_id: 512, expense_type_code: 'MEAL' }
			}),
			scope: 'expenses:write'
		}
	];
</script>

<h1 class="text-display-xl">개발자 가이드</h1>
<p class="mt-4 max-w-[720px] text-body-md text-muted">
	이 시스템의 웹 화면은 공개 API 위에 그려져 있습니다. <strong>사람이 화면에서 하는 일과 똑같은 일을
	AI Agent가 API Key로 수행할 수 있습니다</strong> — 별도의 Agent 전용 엔드포인트는 없습니다.
</p>

<div class="mt-8 flex gap-3">
	<Button onclick={() => goto('/settings/api-keys')}>API 키 발급</Button>
	<Button variant="secondary" onclick={() => window.open('/docs', '_blank')}>
		OpenAPI 문서 (/docs)
	</Button>
</div>

<h2 class="mt-12 text-display-sm">1. 인증</h2>
<Card>
	<p class="text-body-md text-ink">
		모든 요청에 <code class="font-mono">X-API-Key</code> 헤더를 붙입니다. 브라우저는
		<code class="font-mono">Authorization: Bearer &lt;JWT&gt;</code>를 쓰며, 두 헤더가 함께 오면 API
		Key가 우선합니다.
	</p>
	<pre class="mt-4 overflow-x-auto rounded-sm bg-surface-soft p-4 font-mono text-body-sm text-ink">export SKON_BASE_URL=http://localhost
export SKON_API_KEY=sk_live_...</pre>
</Card>

<h2 class="mt-12 text-display-sm">2. 스코프</h2>
{#if errorMessage}
	<p class="mt-4 text-body-sm text-error" role="alert">{errorMessage}</p>
{:else}
	<div class="mt-4 overflow-x-auto">
		<table class="w-full min-w-[640px] border-collapse">
			<thead>
				<tr class="border-b border-hairline text-left text-caption text-muted">
					<th class="py-3">스코프</th>
					<th class="py-3">설명</th>
					<th class="py-3">엔드포인트</th>
				</tr>
			</thead>
			<tbody>
				{#each scopes as info (info.scope)}
					<tr class="border-b border-hairline align-top">
						<td class="py-3 font-mono text-body-sm text-ink">{info.scope}</td>
						<td class="py-3 text-body-sm text-muted">{info.description}</td>
						<td class="py-3 font-mono text-body-sm text-muted">
							{#if info.endpoints.length === 0}
								—
							{:else}
								{#each info.endpoints as endpoint (endpoint)}
									<div>{endpoint}</div>
								{/each}
							{/if}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<p class="mt-3 text-body-sm text-muted">
		표에 없는 엔드포인트(<code class="font-mono">/auth/me</code>,
		<code class="font-mono">/codes</code>, <code class="font-mono">/fund-centers</code>,
		<code class="font-mono">/cost-centers</code>, <code class="font-mono">/notifications</code>,
		<code class="font-mono">/scopes</code>)는 인증만 하면 호출할 수 있습니다.
		<code class="font-mono">/api-keys</code>는 로그인 세션 전용이라 API Key로 새 키를 만들 수 없습니다.
	</p>
{/if}

<h2 class="mt-12 text-display-sm">3. 시나리오</h2>
<div class="mt-4 flex flex-col gap-6">
	{#each examples as example (example.title)}
		<Card>
			<div class="flex items-baseline justify-between">
				<h3 class="text-title-md">{example.title}</h3>
				<span class="font-mono text-body-sm text-muted">{example.scope}</span>
			</div>
			<pre
				class="mt-3 overflow-x-auto rounded-sm bg-surface-soft p-4 font-mono text-body-sm text-ink">{example.snippet}</pre>
		</Card>
	{/each}
</div>

<h2 class="mt-12 text-display-sm">4. 에러 처리</h2>
<Card>
	<p class="text-body-md text-ink">모든 에러 응답이 같은 모양입니다.</p>
	<pre class="mt-3 overflow-x-auto rounded-sm bg-surface-soft p-4 font-mono text-body-sm text-ink">{JSON.stringify(
			{ error: { code: 'TRIP_INVALID_TRANSITION', message: '이미 상신된 출장입니다', field: null } },
			null,
			2
		)}</pre>
	<div class="mt-4 overflow-x-auto">
		<table class="w-full min-w-[560px] border-collapse">
			<tbody>
				{#each [['400', '입력 검증 실패 — field에 문제 필드가 담깁니다'], ['401', '인증 실패 — 키 없음·폐기(API_KEY_REVOKED)·만료(API_KEY_EXPIRED)'], ['403', '스코프 부족 — SCOPE_REQUIRED. 메시지에 필요한 스코프가 있습니다'], ['404', '리소스 없음 — 타인 리소스 접근도 404입니다'], ['409', '상태전이 위반 — code를 보고 재시도 여부를 판단하세요'], ['422', '스키마 위반 — SCHEMA_INVALID']] as [code, meaning] (code)}
					<tr class="border-b border-hairline">
						<td class="w-16 py-2 font-mono text-body-sm text-ink">{code}</td>
						<td class="py-2 text-body-sm text-muted">{meaning}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</Card>
