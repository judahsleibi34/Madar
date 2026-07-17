import { expect, test } from "@playwright/test";

const DEFAULT_PUBLISHED_FORM_PATH =
  "/forms/jus/form_1f38be21-0601-4169-bfe1-d47fe088e094";

test("published form fills its preview card within one pixel", async ({ page }) => {
  const publishedFormUrl = process.env.PUBLISHED_FORM_URL || DEFAULT_PUBLISHED_FORM_PATH;
  await page.goto(publishedFormUrl, { waitUntil: "networkidle" });

  const form = page.locator("main.tenant-runtime-form-page form.runtime-form");
  await expect(form).toBeVisible();

  const obsoleteWrapper = page.locator("section.tenant-runtime-standalone-form");

  const geometry = await form.evaluate((formNode) => {
    const card =
      formNode.closest("section.tenant-runtime-standalone-form") ||
      formNode.closest("main.tenant-runtime-form-page");
    if (!card) throw new Error("Published form preview card was not found");

    const describeNode = (node) => {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return {
        node: `${node.tagName.toLowerCase()}${node.id ? `#${node.id}` : ""}${
          [...node.classList].map((className) => `.${className}`).join("")
        }`,
        rect: {
          left: rect.left,
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
        },
        padding: style.padding,
        margin: style.margin,
        width: style.width,
        height: style.height,
        maxWidth: style.maxWidth,
        inset: style.inset,
        transform: style.transform,
        boxSizing: style.boxSizing,
      };
    };

    const ancestors = [];
    let current = formNode;
    while (current) {
      ancestors.push(describeNode(current));
      if (current === document.documentElement) break;
      current = current.parentElement;
    }

    return {
      card: describeNode(card),
      form: describeNode(formNode),
      ancestors,
    };
  });

  console.log(`PUBLISHED_FORM_GEOMETRY ${JSON.stringify(geometry, null, 2)}`);

  const card = (await obsoleteWrapper.count()) > 0
    ? obsoleteWrapper.first()
    : page.locator("main.tenant-runtime-form-page");
  const cardBox = await card.boundingBox();
  const formBox = await form.boundingBox();
  expect(cardBox).not.toBeNull();
  expect(formBox).not.toBeNull();

  const cardRect = {
    left: cardBox.x,
    top: cardBox.y,
    right: cardBox.x + cardBox.width,
    bottom: cardBox.y + cardBox.height,
  };
  const formRect = {
    left: formBox.x,
    top: formBox.y,
    right: formBox.x + formBox.width,
    bottom: formBox.y + formBox.height,
  };

  for (const edge of ["left", "top", "right", "bottom"]) {
    expect(
      Math.abs(formRect[edge] - cardRect[edge]),
      `${edge} edge differs: card=${cardRect[edge]}, form=${formRect[edge]}`
    ).toBeLessThanOrEqual(1);
  }

  await expect(obsoleteWrapper).toHaveCount(0);
});

test("published standalone form surfaces are consistently white", async ({ page }) => {
  const publishedFormUrl = process.env.PUBLISHED_FORM_URL || DEFAULT_PUBLISHED_FORM_PATH;
  await page.goto(publishedFormUrl, { waitUntil: "networkidle" });

  const surfaceSelectors = [
    "main.tenant-runtime-form-page",
    "main.tenant-runtime-form-page > form.runtime-form",
    "main.tenant-runtime-form-page .runtime-form-section",
    "main.tenant-runtime-form-page .runtime-question",
    "main.tenant-runtime-form-page .runtime-form-pagination",
    "main.tenant-runtime-form-page .runtime-question input:not([type='checkbox']):not([type='radio']):not([type='file'])",
    "main.tenant-runtime-form-page .runtime-question textarea",
    "main.tenant-runtime-form-page .runtime-question select",
  ];

  let checkedSurfaceCount = 0;
  for (const selector of surfaceSelectors) {
    const surfaces = page.locator(selector);
    const count = await surfaces.count();
    checkedSurfaceCount += count;

    for (let index = 0; index < count; index += 1) {
      const backgroundColor = await surfaces
        .nth(index)
        .evaluate((node) => getComputedStyle(node).backgroundColor);
      expect(backgroundColor, `${selector}[${index}] background`).toBe(
        "rgb(255, 255, 255)"
      );
    }
  }

  expect(checkedSurfaceCount).toBeGreaterThan(4);
});
