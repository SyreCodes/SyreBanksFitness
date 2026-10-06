import { describe, expect, it } from 'vitest';
import { formatPrice, type Product } from './content';

const product = (currency: string, price_minor: number): Product => ({ id: 'price', name: 'Coaching', description: '', currency, price_minor, billing_interval: 'monthly' });

describe('public product price formatting', () => {
  it('uses zero minor-unit decimals for Rwanda francs', () => { expect(formatPrice(product('RWF', 150000))).toContain('150,000'); });
  it('converts USD cents and preserves fractional prices', () => { expect(formatPrice(product('USD', 10000))).toBe('$100'); expect(formatPrice(product('USD', 10050))).toBe('$100.50'); });
});
