import { expect, test } from "@playwright/test";

const viewports = [
  [1280, 720],
  [1146, 870],
  [1024, 768],
  [1024, 600],
  [768, 1024],
  [430, 932],
  [390, 844],
  [360, 800],
];

const routes = [
  "/dashboard",
  "/page-builder",
  "/builder-responses",
  "/builder-data",
  "/archive",
  "/my-plan",
  "/settings/security",
  "/settings",
  "/notifications",
  "/settings/change-password",
  "/admin/users",
  "/admin/account-access",
];

const fakeUser = {
  id: 9001,
  auth_id: "responsive-drawer-audit",
  tenant_id: 901,
  first_name: "Responsive",
  last_name: "Audit",
  name: "Responsive Audit",
  email: "responsive-drawer-audit@example.invalid",
  avatar: "",
  subscription_type: "pro",
  plan: "pro",
  builder_type: "website",
  features: [],
  payment_status: "active",
  user_type: "admin",
};

async function installAuthMock(page) {
  await page.route("**/auth/user_status**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ logged_in: true, authenticated: true, user: fakeUser }),
    });
  });
}

async function inspectDrawer(page, direction) {
  return page.locator(".responsive-navigation-drawer").evaluate((drawer, expectedDirection) => {
    const rect = (element) => element?.getBoundingClientRect();
    const style = (element) => element && getComputedStyle(element);
    const navigation = drawer.querySelector(".admin-sidebar-nav");
    const rows = [...(navigation?.querySelectorAll(":scope > button, :scope > a") || [])];
    const activeRow = rows.find((row) => row.classList.contains("active"));
    const inactiveRow = rows.find((row) => !row.classList.contains("active"));
    const account = drawer.querySelector(".admin-sidebar-user");
    const actions = drawer.querySelector(".admin-sidebar-final-actions");
    const actionCells = [...(actions?.children || [])];
    const themeCell = drawer.querySelector(".admin-sidebar-theme-row");
    const scrollContent = drawer.querySelector(".responsive-navigation-scroll-content");
    const alignedSections = [
      drawer.querySelector(".admin-sidebar-brand"),
      drawer.querySelector(".admin-sidebar-search"),
      drawer.querySelector(".admin-sidebar-notifications"),
      navigation,
      account,
      actions,
    ].filter((element) => element?.getClientRects().length);
    const sectionRects = alignedSections.map(rect);
    const reference = sectionRects[0];
    const nestedScrollers = [...drawer.querySelectorAll("*")].filter((element) => {
      if (element === scrollContent) return false;
      const computed = getComputedStyle(element);
      return ["auto", "scroll"].includes(computed.overflowY) &&
        element.scrollHeight > element.clientHeight + 2;
    });
    const rowRects = rows.map(rect);
    const actionRects = actionCells.map(rect);
    const drawerRect = rect(drawer);
    const accountRect = rect(account);
    const actionsRect = rect(actions);
    const themeCellRect = rect(themeCell);
    const footerIcons = [
      drawer.querySelector(".admin-sidebar-lang-switcher .language-toggle-animation"),
      drawer.querySelector(".admin-sidebar-theme-row .theme-toggle-icon"),
      drawer.querySelector(".admin-sidebar-logout > svg"),
    ].map(rect);
    const footerLabels = [
      drawer.querySelector(".admin-sidebar-lang-switcher .language-toggle-current"),
      drawer.querySelector(".admin-sidebar-theme-row .theme-toggle-label"),
      drawer.querySelector(".admin-sidebar-logout > span"),
    ].map(rect);

    return {
      direction: style(drawer)?.direction,
      drawerInsideViewport:
        drawerRect.left >= -1 && drawerRect.right <= document.documentElement.clientWidth + 1,
      noDocumentOverflow:
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      bodyLocked: getComputedStyle(document.body).overflow === "hidden",
      verticalNavigation:
        style(navigation)?.display === "flex" && style(navigation)?.flexDirection === "column",
      rowsEqual:
        rowRects.length > 0 && rowRects.every((row) => Math.abs(row.height - rowRects[0].height) <= 1),
      rowsUsable: rows.every((row) => {
        const rowStyle = style(row);
        const icon = row.querySelector("svg")?.getBoundingClientRect();
        return row.getBoundingClientRect().height >= 44 &&
          rowStyle.justifyContent === "flex-start" &&
          rowStyle.textAlign === "start" &&
          Math.abs((icon?.width || 0) - 22) <= 1;
      }),
      activeStable:
        !activeRow || !inactiveRow || (
          Math.abs(rect(activeRow).height - rect(inactiveRow).height) <= 1 &&
          style(activeRow).paddingInlineStart === style(inactiveRow).paddingInlineStart &&
          style(activeRow).paddingInlineEnd === style(inactiveRow).paddingInlineEnd
        ),
      sectionsAligned: sectionRects.every((section) =>
        expectedDirection === "rtl"
          ? Math.abs(section.right - reference.right) <= 1
          : Math.abs(section.left - reference.left) <= 1
      ),
      accountAboveActions:
        accountRect && actionsRect && accountRect.bottom <= actionsRect.top + 1,
      equalActionCells:
        actionRects.length === 3 && actionRects.every((cell) =>
          Math.abs(cell.width - actionRects[0].width) <= 1 &&
          Math.abs(cell.height - actionRects[0].height) <= 1
        ),
      directionAwareActionOrder:
        actionRects.length === 3 && (
          expectedDirection === "rtl"
            ? actionRects[0].left > actionRects[1].left && actionRects[1].left > actionRects[2].left
            : actionRects[0].left < actionRects[1].left && actionRects[1].left < actionRects[2].left
        ),

      footerContentAligned:
        footerIcons.every((icon) => icon && Math.abs(icon.top - footerIcons[0].top) <= 4) &&
        footerLabels.every((label) => label && Math.abs(label.top - footerLabels[0].top) <= 4),
      themeActionAccessible:
        themeCellRect &&
        themeCell?.tagName === "BUTTON" &&
        ["true", "false"].includes(themeCell.getAttribute("aria-pressed")) &&
        !drawer.querySelector(".admin-sidebar-theme-row .theme-toggle-switch"),
      nestedScrollerCount: nestedScrollers.length,
      scrollContentOverflowX: style(scrollContent)?.overflowX,
      requiredLabelsVisible: rows.every((row) => row.querySelector("span")?.getClientRects().length),
    };
  }, direction);
}

test("shared authenticated drawer stays aligned, scrollable, and direction-aware", async ({ page }) => {
  test.setTimeout(8 * 60 * 1000);
  await installAuthMock(page);

  const cases = [
    ...viewports.map(([width, height]) => ({ route: "/dashboard", width, height })),
    ...routes
      .filter((route) => route !== "/dashboard")
      .map((route) => ({ route, width: 1024, height: 768 })),
  ];

  for (const direction of ["ltr", "rtl"]) {
    await page.addInitScript((language) => {
      localStorage.setItem("madar.language", language);
    }, direction === "rtl" ? "ar" : "en");

    for (const { route, width, height } of cases) {
      await page.setViewportSize({ width, height });
      await page.goto(route, { waitUntil: "domcontentloaded" });
      const trigger = page.locator(".responsive-navigation-trigger");
      await expect(trigger).toBeVisible();
      await trigger.click();

      const drawer = page.locator(".responsive-navigation-drawer");
      await expect(drawer).toBeVisible();

      const result = await inspectDrawer(page, direction);
      expect(result, `${route} at ${width}x${height} (${direction})`).toMatchObject({
        direction,
        drawerInsideViewport: true,
        noDocumentOverflow: true,
        bodyLocked: true,
        verticalNavigation: true,
        rowsEqual: true,
        rowsUsable: true,
        activeStable: true,
        sectionsAligned: true,
        accountAboveActions: true,
        equalActionCells: true,
        directionAwareActionOrder: true,
        footerContentAligned: true,
        themeActionAccessible: true,
        nestedScrollerCount: 0,
        scrollContentOverflowX: "hidden",
        requiredLabelsVisible: true,
      });

      const scrollContent = drawer.locator(".responsive-navigation-scroll-content");
      await scrollContent.evaluate((element) => {
        element.scrollTop = element.scrollHeight;
      });
      await expect(drawer.locator(".admin-sidebar-logout")).toBeVisible();

      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden();
      await expect(trigger).toBeFocused();

      await trigger.click();
      await page.locator(".responsive-navigation-backdrop").click({
        position: {
          x: direction === "rtl" ? 2 : width - 2,
          y: Math.max(2, Math.floor(height / 2)),
        },
      });
      await expect(drawer).toBeHidden();
    }
  }
});

test("drawer language action switches the live application language", async ({ page }) => {
  await installAuthMock(page);
  await page.addInitScript(() => localStorage.setItem("madar.language", "en"));
  await page.setViewportSize({ width: 430, height: 932 });
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });

  const trigger = page.locator(".responsive-navigation-trigger");
  await trigger.click();
  const drawer = page.locator(".responsive-navigation-drawer");
  const languageButton = drawer.locator(".admin-sidebar-lang-switcher");

  await expect(languageButton).toHaveAttribute("data-language", "en");
  await languageButton.click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(languageButton).toHaveAttribute("data-language", "ar");
  await expect(drawer).toBeVisible();

  await languageButton.click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(languageButton).toHaveAttribute("data-language", "en");
});
