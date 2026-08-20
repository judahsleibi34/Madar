import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { createSiteChromeRenderers } from './PageBuilder.siteChrome';

const renderHeader = (logoWidth) => {
  const project = {
    siteChrome: {
      showHeader: true,
      brand: 'Visible Brand',
      logoUrl: '/uploads/logo.png',
      logoWidth,
      headerButtonLabel: '',
    },
    pages: [{ id: 'home', name: 'Home', slug: '/', showInNavigation: true }],
  };
  const renderers = createSiteChromeRenderers({
    project,
    activePage: project.pages[0],
    selected: {},
    preview: true,
    selectPage: vi.fn(),
    setSelected: vi.fn(),
  });

  return render(renderers.renderSiteHeader());
};

const renderFooter = (siteChrome) => {
  const project = {
    siteChrome: { showFooter: true, ...siteChrome },
    pages: [{ id: 'home', name: 'Home', slug: '/', showInNavigation: true }],
  };
  const renderers = createSiteChromeRenderers({
    project,
    activePage: project.pages[0],
    selected: {},
    preview: true,
    selectPage: vi.fn(),
    setSelected: vi.fn(),
  });

  return render(renderers.renderSiteFooter());
};

describe('site header logo sizing', () => {
  it('exposes the saved logo width to the shared preview/runtime header', () => {
    const view = renderHeader(96);
    const header = view.container.querySelector('.built-site-header');

    expect(header?.style.getPropertyValue('--site-header-logo-width')).toBe('96px');
  });

  it('clamps unsafe logo widths', () => {
    const small = renderHeader(1);
    expect(small.container.querySelector('.built-site-header')?.style.getPropertyValue('--site-header-logo-width')).toBe('16px');
    small.unmount();

    const large = renderHeader(999);
    expect(large.container.querySelector('.built-site-header')?.style.getPropertyValue('--site-header-logo-width')).toBe('240px');
  });
});

describe('optional responsive site footer groups', () => {
  it('omits empty link, social, payment, and contact groups', () => {
    const view = renderFooter({
      footerStoreName: '',
      logoUrl: '',
      description: '',
      footerShopLinks: '',
      footerHelpLinks: '',
      footerSocialLinks: '',
      footerSocialItems: [],
      footerPaymentMethods: '',
      footerPaymentItems: [],
      contactEmail: '',
      phone: '',
    });

    expect(view.container.querySelector('.ecommerce-footer-grid')).toBeNull();
    expect(view.container.querySelector('.ecommerce-social-row')).toBeNull();
    expect(view.container.querySelector('.ecommerce-payment-row')).toBeNull();
  });

  it('renders only populated groups and reports their count to the responsive grid', () => {
    const view = renderFooter({
      footerStoreName: '',
      logoUrl: '',
      description: '',
      footerShopTitle: 'Site pages',
      footerShopLinks: 'home',
      footerHelpLinks: '',
      footerSocialLinks: '',
      footerSocialItems: [],
      footerPaymentMethods: 'Visa',
      footerPaymentItems: [],
      contactEmail: '',
      phone: '',
    });
    const grid = view.container.querySelector('.ecommerce-footer-grid');

    expect(grid?.getAttribute('data-section-count')).toBe('2');
    expect(grid?.textContent).toContain('Site pages');
    expect(grid?.textContent).toContain('Home');
    expect(grid?.textContent).toContain('Payment Methods');
    expect(grid?.textContent).toContain('Visa');
    expect(grid?.textContent).not.toContain('Help');
  });
});
