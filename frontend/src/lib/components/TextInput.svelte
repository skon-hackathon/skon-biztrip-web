<script lang="ts">
	let {
		label,
		value = $bindable(''),
		type = 'text',
		placeholder = '',
		error = '',
		id = crypto.randomUUID()
	}: {
		label: string;
		value?: string;
		type?: 'text' | 'email' | 'password' | 'date' | 'number';
		placeholder?: string;
		error?: string;
		id?: string;
	} = $props();
</script>

<div class="flex flex-col gap-2">
	<label for={id} class="text-caption text-muted">{label}</label>
	<input
		{id}
		{type}
		{placeholder}
		bind:value
		class="h-14 rounded-sm border bg-canvas px-3 text-body-md text-ink outline-none focus:border-2 focus:border-ink {error
			? 'border-error'
			: 'border-hairline'}"
	/>
	{#if error}
		<p class="text-caption-sm text-error">{error}</p>
	{/if}
</div>
