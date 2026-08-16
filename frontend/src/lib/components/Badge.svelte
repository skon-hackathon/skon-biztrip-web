<script lang="ts">
	import type { Snippet } from 'svelte';

	type Tone = 'neutral' | 'primary' | 'success' | 'danger';

	let { tone = 'neutral', children }: { tone?: Tone; children: Snippet } = $props();

	const tones: Record<Tone, string> = {
		neutral: 'bg-canvas text-ink shadow-float',
		primary: 'bg-primary text-white',
		success: 'bg-ink text-white',
		danger: 'bg-error text-white'
	};
</script>

<span class="inline-flex items-center rounded-full px-2.5 py-1 text-badge {tones[tone]}">
	{@render children()}
</span>
