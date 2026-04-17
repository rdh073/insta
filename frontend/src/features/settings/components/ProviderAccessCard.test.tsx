// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderToStaticMarkup } from 'react-dom/server';
import type { ProviderOAuth } from '../hooks/useProviderOAuth';
import { ProviderAccessCard } from './ProviderAccessCard';

vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock('../../../api/provider-settings', () => ({
  ollamaApi: { health: vi.fn() },
}));

// @testing-library/react auto-cleanup requires globals: true in vitest config.
// Since this project doesn't set globals, call cleanup explicitly.
afterEach(() => cleanup());

function makeOAuth(): ProviderOAuth {
  return {
    busy: false,
    codeEntry: false,
    code: '',
    status: { connected: false, expiresAtMs: null, accountId: null },
    setCode: vi.fn(),
    handleConnect: vi.fn().mockResolvedValue(undefined),
    handleSubmit: vi.fn().mockResolvedValue(undefined),
    handleCancel: vi.fn(),
    handleRevoke: vi.fn().mockResolvedValue(undefined),
  };
}

describe('ProviderAccessCard – API key input binding', () => {
  // Regression: value={apiKey} where apiKey is undefined makes the input uncontrolled.
  // React omits the value attribute from the HTML, allowing programmatic writes to bypass
  // the onChange chain. After the fix (value={apiKey ?? ''}), value="" is always present.
  it('renders API key input as controlled (value="" in HTML) even when apiKey prop is undefined', () => {
    const html = renderToStaticMarkup(
      <ProviderAccessCard
        provider="openai"
        isOAuthProvider={false}
        effectiveBaseUrl=""
        onBaseUrlChange={() => {}}
        apiKey={undefined as unknown as string}
        onApiKeyChange={() => {}}
        oauth={makeOAuth()}
      />,
    );
    const inputMatch = html.match(/<input[^>]*name="api_key_openai"[^>]*>/);
    expect(inputMatch).not.toBeNull();
    expect(inputMatch?.[0]).toContain('value=""');
  });

  it('fires onApiKeyChange for each keystroke via userEvent.type', async () => {
    const onApiKeyChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ProviderAccessCard
        provider="openai"
        isOAuthProvider={false}
        effectiveBaseUrl=""
        onBaseUrlChange={vi.fn()}
        apiKey=""
        onApiKeyChange={onApiKeyChange}
        oauth={makeOAuth()}
      />,
    );
    const input = screen.getByLabelText(/openai api key/i);
    await user.type(input, 'sk-test');
    expect(onApiKeyChange).toHaveBeenCalled();
  });

  it('fires onApiKeyChange via fireEvent.input (autofill / Chrome DevTools fill path)', () => {
    const onApiKeyChange = vi.fn();
    render(
      <ProviderAccessCard
        provider="openai"
        isOAuthProvider={false}
        effectiveBaseUrl=""
        onBaseUrlChange={vi.fn()}
        apiKey=""
        onApiKeyChange={onApiKeyChange}
        oauth={makeOAuth()}
      />,
    );
    const input = screen.getByLabelText(/openai api key/i);
    fireEvent.input(input, { target: { value: 'sk-autofilled' } });
    expect(onApiKeyChange).toHaveBeenCalledWith('sk-autofilled');
  });

  it('fires onApiKeyChange via fireEvent.input when apiKey was initially undefined', () => {
    const onApiKeyChange = vi.fn();
    render(
      <ProviderAccessCard
        provider="openai"
        isOAuthProvider={false}
        effectiveBaseUrl=""
        onBaseUrlChange={vi.fn()}
        apiKey={undefined as unknown as string}
        onApiKeyChange={onApiKeyChange}
        oauth={makeOAuth()}
      />,
    );
    const input = screen.getByLabelText(/openai api key/i);
    fireEvent.input(input, { target: { value: 'sk-autofilled' } });
    expect(onApiKeyChange).toHaveBeenCalledWith('sk-autofilled');
  });
});
