/**
 * Shell helpers — open URLs and reveal files in the OS file manager.
 * Uses Tauri's shell plugin when running inside the desktop app,
 * falls back to window.open in dev/browser mode.
 */

function isTauri() {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

/**
 * Open a URL (mailto:, https:, file:) in the OS default handler.
 */
export async function openUrl(url) {
  if (isTauri()) {
    const { open } = await import('@tauri-apps/plugin-shell')
    await open(url)
  } else {
    window.open(url, '_blank')
  }
}

/**
 * Reveal a file path in Finder / Explorer.
 * In Tauri: opens the containing folder.
 * In dev: does nothing (no filesystem access from browser).
 */
export async function revealInFinder(filePath) {
  if (!filePath) return
  if (isTauri()) {
    const { open } = await import('@tauri-apps/plugin-shell')
    // Open the parent directory
    const dir = filePath.replace(/[/\\][^/\\]+$/, '')
    await open(dir)
  }
  // In dev mode: no-op — user sees the path on screen
}
