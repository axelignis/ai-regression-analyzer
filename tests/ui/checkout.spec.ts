import { test, expect } from '@playwright/test';

// INTENTIONAL FAILURE — assertion_error
// Actual price is $29.99. Asserting $9.99 produces a controlled, deterministic failure.
test('checkout: product price matches expected value', async ({ page }) => {
  await page.goto('https://www.saucedemo.com');
  await page.fill('[data-test="username"]', 'standard_user');
  await page.fill('[data-test="password"]', 'secret_sauce');
  await page.click('[data-test="login-button"]');

  const price = page
    .locator('.inventory_item')
    .first()
    .locator('.inventory_item_price');

  await expect(price).toHaveText('$9.99');
});
