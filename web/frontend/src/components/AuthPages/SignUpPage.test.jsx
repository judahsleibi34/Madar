import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const postAuthJson = vi.fn();

afterEach(cleanup);

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key, options = {}) => ({
      "signup.title": "Register",
      "signup.subtitle": "Create your account",
      "signup.firstName": "First name",
      "signup.lastName": "Last name",
      "signup.email": "Email",
      "signup.password": "Password",
      "signup.confirmPassword": "Confirm password",
      "signup.agreeToTerms": "I agree to the",
      "signup.termsAndConditions": "Terms and Conditions",
      "signup.termsRequired": "You must agree to the Terms and Conditions to create an account.",
      "signup.submit": "Create Account",
      "signup.loading": "Creating Account...",
      "signup.hasAccount": "Already have an account?",
      "signup.login": "Log In",
      "signup.togglePassword": "Toggle password visibility",
      "signup.toggleConfirmPassword": "Toggle confirm password visibility",
      "signup.success": "Account created",
      "validation.required": "This field is required.",
      "validation.invalidEmail": "Enter a valid email.",
      "verification.providerUnavailable": "Email verification is temporarily unavailable. Please try again shortly.",
    }[key] || options.defaultValue || key),
  }),
}));

vi.mock("../../utils/apiClient", async (importOriginal) => ({
  ...(await importOriginal()),
  postAuthJson: (...args) => postAuthJson(...args),
}));

import SignUpPage from "./SignUpPage";

const fillRequiredAccountFields = () => {
  fireEvent.change(screen.getByPlaceholderText("First name"), {
    target: { value: "Madar" },
  });
  fireEvent.change(screen.getByPlaceholderText("Last name"), {
    target: { value: "Owner" },
  });
  fireEvent.change(screen.getByPlaceholderText("Email"), {
    target: { value: "owner@example.com" },
  });
  fireEvent.change(screen.getByPlaceholderText("Password"), {
    target: { value: "password123" },
  });
  fireEvent.change(screen.getByPlaceholderText("Confirm password"), {
    target: { value: "password123" },
  });
};

describe("signup terms consent", () => {
  beforeEach(() => {
    postAuthJson.mockReset();
    postAuthJson.mockResolvedValue({
      response: { ok: true },
      data: { requires_email_verification: false },
    });
  });

  it("requires consent and links to the terms page before creating an account", async () => {
    render(
      <MemoryRouter>
        <SignUpPage lang="en" />
      </MemoryRouter>
    );

    fillRequiredAccountFields();

    const termsLink = screen.getByRole("link", { name: "Terms and Conditions" });
    expect(termsLink.getAttribute("href")).toBe("/terms-and-conditions");
    expect(termsLink.getAttribute("target")).toBe("_blank");

    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    expect(postAuthJson).not.toHaveBeenCalled();
    expect(
      screen.getByText("You must agree to the Terms and Conditions to create an account.")
    ).toBeTruthy();

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => expect(postAuthJson).toHaveBeenCalledTimes(1));
    expect(postAuthJson).toHaveBeenCalledWith(
      "/auth/signup",
      expect.objectContaining({ terms_accepted: true })
    );
  });
});

describe("signup API error classification", () => {
  beforeEach(() => postAuthJson.mockReset());

  const submitSignup = () => {
    render(<MemoryRouter><SignUpPage lang="en" /></MemoryRouter>);
    fillRequiredAccountFields();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Create Account" }));
  };

  it.each([
    { code: "email_verification_delivery_failed", message: "The account could not be created because the verification email was not sent." },
    { detail: { code: "email_verification_delivery_failed", message: "The account could not be created because the verification email was not sent." } },
  ])("shows a provider message for delivery failure without blaming the email field: %j", async (data) => {
    postAuthJson.mockResolvedValue({ response: { ok: false, status: 503 }, data });
    submitSignup();
    await waitFor(() => expect(screen.getByText("Email verification is temporarily unavailable. Please try again shortly.")).toBeTruthy());
    expect(screen.queryByText("Enter a valid email.")).toBeNull();
    expect(screen.getByPlaceholderText("Email").getAttribute("aria-invalid")).not.toBe("true");
  });

  it.each([
    { status: 400, detail: "Invalid email address" },
    { status: 422, detail: [{ loc: ["body", "email"], msg: "value is not a valid email address" }] },
  ])("keeps malformed-email API errors on the email field: %j", async ({ status, detail }) => {
    postAuthJson.mockResolvedValue({ response: { ok: false, status }, data: { detail } });
    submitSignup();
    await waitFor(() => expect(screen.getByText("Enter a valid email.")).toBeTruthy());
    expect(screen.queryByText("Email verification is temporarily unavailable. Please try again shortly.")).toBeNull();
    expect(screen.getByPlaceholderText("Email").getAttribute("aria-invalid")).toBe("true");
  });
});
