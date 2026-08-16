<script lang="ts">
	import type { Snippet } from 'svelte';

	type Variant = 'primary' | 'secondary' | 'tertiary' | 'pill';

	let {
		variant = 'primary',
		type = 'button',
		disabled = false,
		full = false,
		onclick,
		children
	}: {
		variant?: Variant;
		type?: 'button' | 'submit';
		disabled?: boolean;
		full?: boolean;
		onclick?: (event: MouseEvent) => void;
		children: Snippet;
	} = $props();

	const base = 'inline-flex items-center justify-center transition-colors disabled:cursor-not-allowed';
	const variants: Record<Variant, string> = {
		primary:
			'h-12 rounded-sm bg-primary px-6 text-button-md text-white hover:bg-primary-active disabled:bg-primary-disabled',
		secondary:
			'h-12 rounded-sm border border-ink bg-canvas px-6 text-button-md text-ink hover:bg-surface-soft disabled:border-border-strong disabled:text-muted-soft',
		tertiary: 'text-button-md text-ink underline-offset-4 hover:underline disabled:text-muted-soft',
		pill: 'rounded-full bg-primary px-5 py-2.5 text-button-sm text-white hover:bg-primary-active disabled:bg-primary-disabled'
	};
</script>

<button
	{type}
	{disabled}
	{onclick}
	class="{base} {variants[variant]} {full ? 'w-full' : ''}"
>
	{@render children()}
</button>
