import { lazy } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import RouteSuspense from "./RouteSuspense";

afterEach(cleanup);
it("shows loading immediately while a route bundle is pending", () => {
  const Pending = lazy(() => new Promise(() => {}));
  render(<RouteSuspense label="Loading page"><Pending /></RouteSuspense>);
  expect(screen.getByRole("status")).toBeTruthy();
  expect(screen.getByLabelText("Loading page")).toBeTruthy();
});
