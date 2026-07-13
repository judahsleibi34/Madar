import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const postAuthJson = vi.fn();

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
    }[key] || options.defaultValue || key),
  }),
}));

vi.mock("../../utils/apiClient", () => ({
  postAuthJson: (...args) => postAuthJson(...args),
  readApiError: () => "",
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
