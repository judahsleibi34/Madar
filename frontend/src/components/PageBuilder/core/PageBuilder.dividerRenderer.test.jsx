import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { createElementRenderer } from './PageBuilder.elementRenderer';

describe('horizontal line rendering', () => {
  it('renders an explicit separator with inspector thickness and color', () => {
    const element = {
      id: 'line-1',
      type: 'thinDivider',
      styles: {
        color: '#8790A3',
        backgroundColor: 'transparent',
        '--divider-thickness': '20px',
      },
    };
    const renderElement = createElementRenderer({
      carouselElementTypes: new Set(),
      selected: { type: 'element', id: element.id },
      preview: false,
      getFreeElementStyle: () => ({}),
      getElementStyle: (item) => ({ ...item.styles }),
      startDrag: vi.fn(),
      findElementLocation: vi.fn(),
      setInsertTarget: vi.fn(),
      setSelected: vi.fn(),
      captureCanvasTextSelection: vi.fn(),
      shouldIgnoreInlineTextBlur: () => false,
      updateElementInlineText: vi.fn(),
      runElementAction: vi.fn(),
      renderConnectedForm: vi.fn(),
      getReservationBlockValue: vi.fn(),
    });

    render(renderElement(element));
    const separator = screen.getByRole('separator');

    expect(separator.tagName).toBe('DIV');
    expect(separator.style.getPropertyValue('--divider-thickness')).toBe('20px');
    expect(separator.style.getPropertyValue('--divider-color')).toBe('#8790A3');
  });
});
