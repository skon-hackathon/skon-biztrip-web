<script lang="ts">
	let {
		label,
		value = $bindable(''),
		type = 'text',
		placeholder = '',
		error = '',
		id
	}: {
		label: string;
		value?: string;
		type?: 'text' | 'email' | 'password' | 'date' | 'number';
		placeholder?: string;
		error?: string;
		id?: string;
	} = $props();

	const fallbackId = $props.id();
	const inputId = $derived(id ?? fallbackId);
	const errorId = $derived(`${inputId}-error`);
</script>

<div class="flex flex-col gap-2">
	<label for={inputId} class="text-caption text-muted">{label}</label>
	<input
		id={inputId}
		{type}
		{placeholder}
		bind:value
		aria-invalid={!!error}
		aria-describedby={error ? errorId : undefined}
		class="h-14 rounded-sm border bg-canvas px-3 text-body-md text-ink outline-none focus:border-2 focus:border-ink {error
			? 'border-error'
			: 'border-hairline'}"
	/>
	{#if error}
		<p id={errorId} class="text-caption-sm text-error">{error}</p>
	{/if}
</div>
