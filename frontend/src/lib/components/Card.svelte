<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		padded = true,
		hoverable = false,
		children
	}: { padded?: boolean; hoverable?: boolean; children: Snippet } = $props();
</script>

<div
	class="rounded-md border border-hairline bg-canvas {padded ? 'p-6' : ''} {hoverable
		? 'transition-shadow hover:shadow-float'
		: ''}"
>
	{@render children()}
</div>
