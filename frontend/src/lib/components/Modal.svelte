<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		open = false,
		title,
		onclose,
		children
	}: {
		open?: boolean;
		title: string;
		onclose: () => void;
		children: Snippet;
	} = $props();

	// <dialog>.showModal()은 SecureContext 전용 API가 아니므로 평문 HTTP 운영에서도
	// 동작한다. 직접 오버레이를 그리는 대신 이걸 쓰는 이유는 포커스 트랩과 Esc 닫기를
	// 브라우저가 해주기 때문이다.
	let dialog = $state<HTMLDialogElement | null>(null);
	const titleId = $props.id();

	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) dialog.showModal();
		if (!open && dialog.open) dialog.close();
	});

	/**
	 * 백드롭 클릭으로 닫는다. <dialog>는 백드롭에도 dialog 자신의 click이 오므로,
	 * 이벤트 대상이 dialog 자신일 때만 닫는다 — 내용 영역을 클릭했을 때는 target이
	 * 내부 요소이므로 닫히지 않는다.
	 */
	function handleClick(event: MouseEvent): void {
		if (event.target === dialog) onclose();
	}
</script>

<dialog
	bind:this={dialog}
	aria-labelledby={titleId}
	onclick={handleClick}
	onclose={onclose}
	class="w-[min(920px,92vw)] rounded-md border border-hairline bg-canvas p-0 backdrop:bg-black/40"
>
	<div class="flex items-center justify-between gap-4 border-b border-hairline px-6 py-5">
		<h2 id={titleId} class="text-display-sm">{title}</h2>
		<button
			type="button"
			aria-label="닫기"
			onclick={onclose}
			class="text-button-md text-muted hover:text-ink"
		>
			닫기
		</button>
	</div>
	<div class="max-h-[70vh] overflow-y-auto px-6 py-6">
		{@render children()}
	</div>
</dialog>
