/**
 * Reviews E2E Tests
 * Tests the anonymous review workflow in both no-script and script modes.
 */

const { test, expect } = require('@playwright/test');
const { randomUUID } = require('node:crypto');
const { TEST_CONFIG } = require('./utils/test-helpers');

test.use({
  baseURL: TEST_CONFIG.baseURL,
});

const ANONYMIZED_USER_ID_PATTERN = /^[A-Za-z0-9]+\.\.\.$/;

function uniqueReviewMessage(prefix) {
  return `${prefix} ${randomUUID()}`;
}

async function fetchReviewData(page) {
  const response = await page.request.get(`${TEST_CONFIG.testPath}/reviews/list`);
  expect(response.status()).toBe(200);
  return response.json();
}

test.describe('Reviews Functionality', () => {
  test('should load the reviews page with statistics and review form', async ({ page }) => {
    const response = await page.goto(`${TEST_CONFIG.testPath}/reviews`);
    expect(response.status()).toBe(200);

    await expect(page.getByRole('heading', { name: /Service Reviews/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Review Statistics/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Submit Your Review/i })).toBeVisible();
    await expect(page.locator('input[name="rating"]')).toHaveCount(5);
    await expect(page.locator('#review_text')).toBeVisible();
    await expect(page.getByRole('button', { name: /Submit Review/i })).toBeVisible();
  });

  test('should submit a review through the no-script form and render it on the page', async ({ page }) => {
    const message = uniqueReviewMessage('No-script review');

    await page.goto(`${TEST_CONFIG.testPath}/reviews`);
    await page.check('#rating-4');
    await page.fill('#review_text', message);
    await page.getByRole('button', { name: /Submit Review/i }).click();

    await expect(page.locator('.message.success')).toContainText('Thank you for your review');
    await expect(page.locator('.review-text', { hasText: message })).toBeVisible();

    const reviewData = await fetchReviewData(page);
    expect(reviewData.reviews.some((review) => review.text === message && review.rating === 4)).toBe(true);
  });

  test('should submit a review through the script endpoints and expose it via JSON', async ({ page }) => {
    const message = uniqueReviewMessage('Script review');

    await page.goto(`${TEST_CONFIG.testPath}/reviews/yesscript`);
    await expect(page.locator('#review-form')).toBeVisible();
    await expect(page.locator('#reviews-list')).toBeVisible();

    await page.check('#rating-5');
    await page.fill('#review_text', message);

    const [submitResponse] = await Promise.all([
      page.waitForResponse((res) => res.url().includes('/reviews/submit')),
      page.getByRole('button', { name: /Submit Review/i }).click(),
    ]);

    expect(submitResponse.status()).toBe(200);
    expect(submitResponse.headers()['content-type']).toContain('application/json');

    const submitPayload = await submitResponse.json();
    expect(submitPayload.success).toBe(true);
    expect(submitPayload.message).toContain('Thank you for your review');

    await expect(page.locator('#reviews-list')).toContainText(message);

    const reviewData = await fetchReviewData(page);
    const insertedReview = reviewData.reviews.find((review) => review.text === message);

    expect(insertedReview).toBeDefined();
    expect(insertedReview.rating).toBe(5);
    expect(insertedReview.user_id).toMatch(ANONYMIZED_USER_ID_PATTERN);
    expect(reviewData.my_review_count).toBeGreaterThanOrEqual(1);
    expect(reviewData.stats.my_review_count).toBe(reviewData.my_review_count);
  });

  test('should expose per-session review activity endpoint', async ({ page }) => {
    await page.goto(`${TEST_CONFIG.testPath}/reviews`);
    await page.check('#rating-5');
    await page.fill('#review_text', uniqueReviewMessage('Session review activity'));
    await page.getByRole('button', { name: /Submit Review/i }).click();

    const meResponse = await page.request.get(`${TEST_CONFIG.testPath}/reviews/me`);
    expect(meResponse.status()).toBe(200);
    const payload = await meResponse.json();
    expect(payload.success).toBe(true);
    expect(payload.my_review_count).toBeGreaterThanOrEqual(1);
  });

  test('should reject invalid AJAX submissions without a rating', async ({ page }) => {
    await page.goto(`${TEST_CONFIG.testPath}/reviews/yesscript`);

    const response = await page.request.post(`${TEST_CONFIG.testPath}/reviews/submit`, {
      form: {
        review_text: uniqueReviewMessage('Missing rating review'),
      },
    });

    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('application/json');

    const payload = await response.json();
    expect(payload).toEqual({
      success: false,
      message: 'Please select a valid rating (1-5 stars).',
    });
  });
});
