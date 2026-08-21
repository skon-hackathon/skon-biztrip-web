<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import { byGroupCode, listCodeGroups } from '$lib/api/codes';
	import type { CodeGroup, TripInput } from '$lib/api/types';
	import Select from '$lib/components/Select.svelte';
	import TextInput from '$lib/components/TextInput.svelte';
	import Textarea from '$lib/components/Textarea.svelte';

	let {
		initial,
		onchange
	}: {
		initial: TripInput;
		onchange: (values: TripInput) => void;
	} = $props();

	// initial은 마운트 시 한 번만 읽는다. 이후 부모가 초기값을 바꿔도 사용자가 입력 중인
	// 값을 덮어써서는 안 된다. 수정 화면은 initial이 준비된 뒤에야 이 컴포넌트를 띄운다.
	let values = $state<TripInput>({ ...untrack(() => initial) });
	let groups = $state<Record<string, CodeGroup>>({});
	let loadError = $state('');

	// 부모가 저장 시점에 최신 값을 읽을 수 있게 매 변경을 올려보낸다. 부모가 대입하는
	// 상태는 이 컴포넌트가 읽지 않으므로 루프가 생기지 않는다.
	$effect(() => {
		onchange({ ...values });
	});

	onMount(async () => {
		try {
			groups = byGroupCode(await listCodeGroups());
		} catch (error) {
			loadError = error instanceof ApiError ? error.message : '기준정보를 불러오지 못했습니다';
		}
	});

	function optionsOf(groupCode: string): { value: string; label: string }[] {
		return (groups[groupCode]?.codes ?? []).map((code) => ({
			value: code.code,
			label: code.name
		}));
	}
</script>

{#if loadError}
	<p class="mb-6 text-body-sm text-error" role="alert">{loadError}</p>
{/if}

<div class="flex flex-col gap-6">
	<TextInput label="출장 제목" bind:value={values.title} placeholder="울산공장 품질점검" />

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<Select label="출장 목적" bind:value={values.purpose_code} options={optionsOf('TRIP_PURPOSE')} />
		<Select
			label="국내 / 해외"
			bind:value={values.destination_type_code}
			options={optionsOf('DESTINATION_TYPE')}
		/>
	</div>

	<Textarea
		label="목적 상세"
		bind:value={values.purpose_detail}
		placeholder="무엇을 하러 가는지 구체적으로 적어주세요"
	/>

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<Select label="국가" bind:value={values.country_code} options={optionsOf('COUNTRY')} />
		<TextInput label="도시" bind:value={values.city} placeholder="울산" />
	</div>

	<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
		<TextInput label="시작일" type="date" bind:value={values.start_date} />
		<TextInput label="종료일" type="date" bind:value={values.end_date} />
	</div>
</div>
