<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		title,
		description = '',
		action
	}: { title: string; description?: string; action?: Snippet } = $props();
</script>

<div class="flex flex-col items-center gap-3 rounded-md border border-hairline py-16 text-center">
	<p class="text-title-md text-ink">{title}</p>
	{#if description}
		<p class="text-body-sm text-muted">{description}</p>
	{/if}
	{#if action}
		<div class="mt-2">{@render action()}</div>
	{/if}
</div>
