<script lang="ts">
	let {
		label,
		value = $bindable(''),
		options,
		placeholder = '선택하세요',
		error = '',
		id,
		name,
		disabled = false
	}: {
		label: string;
		value?: string;
		options: { value: string; label: string }[];
		placeholder?: string;
		error?: string;
		id?: string;
		name?: string;
		disabled?: boolean;
	} = $props();

	// crypto.randomUUID()를 쓰지 않는다 — 운영은 평문 HTTP라 SecureContext가 아니어서
	// 그 API 자체가 없고, 페이지 전체가 렌더에 실패한다.
	const fallbackId = $props.id();
	const selectId = $derived(id ?? fallbackId);
	const errorId = $derived(`${selectId}-error`);
</script>

<div class="flex flex-col gap-2">
	<label for={selectId} class="text-caption text-muted">{label}</label>
	<select
		id={selectId}
		{name}
		{disabled}
		bind:value
		aria-invalid={!!error}
		aria-describedby={error ? errorId : undefined}
		class="h-14 rounded-sm border bg-canvas px-3 text-body-md text-ink outline-none focus:border-2 focus:border-ink disabled:text-muted-soft {error
			? 'border-error'
			: 'border-hairline'}"
	>
		<option value="" disabled>{placeholder}</option>
		{#each options as option (option.value)}
			<option value={option.value}>{option.label}</option>
		{/each}
	</select>
	{#if error}
		<p id={errorId} class="text-caption-sm text-error">{error}</p>
	{/if}
</div>
