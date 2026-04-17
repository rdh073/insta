import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ManageAccountsLink } from './DashboardPage';

describe('DashboardPage ManageAccountsLink', () => {
  it('renders an anchor pointing to /accounts', () => {
    const html = renderToStaticMarkup(<ManageAccountsLink />);

    expect(html).toContain('href="/accounts"');
    expect(html).not.toContain('href="/"');
    expect(html).toContain('Manage accounts');
  });
});
