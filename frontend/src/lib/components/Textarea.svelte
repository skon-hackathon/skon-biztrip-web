<script lang="ts">
	let {
		label,
		value = $bindable(''),
		placeholder = '',
		rows = 4,
		error = '',
		id,
		name
	}: {
		label: string;
		value?: string;
		placeholder?: string;
		rows?: number;
		error?: string;
		id?: string;
		name?: string;
	} = $props();

	const fallbackId = $props.id();
	const areaId = $derived(id ?? fallbackId);
	const errorId = $derived(`${areaId}-error`);
</script>

<div class="flex flex-col gap-2">
	<label for={areaId} class="text-caption text-muted">{label}</label>
	<textarea
		id={areaId}
		{name}
		{rows}
		{placeholder}
		bind:value
		aria-invalid={!!error}
		aria-describedby={error ? errorId : undefined}
		class="rounded-sm border bg-canvas p-3 text-body-md text-ink outline-none focus:border-2 focus:border-ink {error
			? 'border-error'
			: 'border-hairline'}"
	></textarea>
	{#if error}
		<p id={errorId} class="text-caption-sm text-error">{error}</p>
	{/if}
</div>
