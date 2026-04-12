# Frontend Theme Tokens (VS Code Dark Inspired)

This project uses a tokenized dark theme in `src/index.css` based on VS Code dark palettes (`Dark Modern`, `Dark+`, `Dark (Visual Studio)`), adapted to preserve the existing glass/Tokyo-night visual language.

## Token Naming

- `--color-vscode-*`: raw source reference colors from VS Code themes.
- `--color-*`: normalized app tokens used by UI components.
- `--tokyo-*` and `--color-tokyo-*`: compatibility aliases for existing classes and legacy utilities.

## Core Token Groups

- Surface:
  - `--color-bg-canvas`, `--color-bg-elevated`
  - `--color-surface-1`, `--color-surface-2`, `--color-surface-3`
  - `--color-surface-overlay*`
- Text:
  - `--color-text-strong`, `--color-text-primary`, `--color-text-muted`, `--color-text-subtle`, `--color-text-disabled`
- Border + focus:
  - `--color-border-fainter/faint/subtle/muted/strong`
  - `--color-border-focus`, `--color-focus-ring`
- Interactive state:
  - `--color-state-hover`, `--color-state-active`, `--opacity-disabled`
- Semantic:
  - Success: `--color-success-*`
  - Warning: `--color-warning-*`
  - Error: `--color-error-*`
  - Info: `--color-info-*`

## Usage Rules

- Use semantic tokens for status messaging (`success/warning/error/info`), not arbitrary colors.
- Use concrete token classes such as `text-[var(--color-text-primary)]` and `bg-[var(--color-surface-1)]` in components.
- Use `--color-border-focus` + `--color-focus-ring` for all focus-visible states.
- Prefer shared components (`Button`, `Input`, `Card`, `Modal`, `Badge`, layout shell) so token changes propagate consistently.

## Accessibility

Normal text tokens are validated to meet WCAG 2.1 contrast minimum **4.5:1** on main dark surfaces (`--color-bg-canvas`, `--color-surface-1`, `--color-surface-2`).

Minimum observed ratio in current token set:
- `--color-error-fg` on primary surfaces: **>= 5.07:1**

Reference ratios (worst case across main dark surfaces):
- `--color-text-strong`: **>= 15.73:1**
- `--color-text-primary`: **>= 11.95:1**
- `--color-text-muted`: **>= 7.16:1**
- `--color-text-subtle`: **>= 5.85:1**

## Quick Mapping (VS Code -> App)

- `#1F1F1F` / `#181818` -> app canvas + elevated surfaces
- `#CCCCCC` -> `--color-text-primary`
- `#0078D4` / `#026EC1` -> primary action + hover
- `#F85149` -> `--color-error-fg`
- `#4FC1FF` -> `--color-info-fg`
