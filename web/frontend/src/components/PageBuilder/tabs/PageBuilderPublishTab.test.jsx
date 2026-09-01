import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PageBuilderPublishTab from "./PageBuilderPublishTab";

const project = {
  name: "Madar Site",
  status: "published",
  publish: {},
  forms: [],
};

const projectWithForm = {
  ...project,
  publish: {
    subdomain: "disco2",
    siteBaseDomain: "madarportal.com",
  },
  forms: [{ id: "form-1", title: "Contact us" }],
  activeFormId: "form-1",
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PageBuilderPublishTab", () => {
  it("uses the canonical tenant subdomain live path", () => {
    render(
      <PageBuilderPublishTab
        project={project}
        liveSitePath="/site/disco2/"
      />
    );

    expect(screen.getByDisplayValue("https://madarportal.com/site/disco2/")).toBeTruthy();
    expect(screen.queryByDisplayValue(/project_/)).toBeNull();
  });

  it("falls back to the configured publish subdomain while website settings load", () => {
    render(
      <PageBuilderPublishTab
        project={{
          ...project,
          publish: {
            subdomain: "disco2",
          },
        }}
      />
    );

    expect(screen.getByDisplayValue("https://madarportal.com/site/disco2/")).toBeTruthy();
    expect(screen.queryByDisplayValue(/project_/)).toBeNull();
  });

  it("does not invent a public URL when no subdomain is available", () => {
    render(<PageBuilderPublishTab project={project} />);

    expect(screen.getByPlaceholderText("Configure a website subdomain before sharing the live site.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /copy link/i }).disabled).toBe(true);
    expect(screen.getByRole("button", { name: /preview site/i }).disabled).toBe(true);
  });

  it("does not show a publish action in the Publish tab", () => {
    render(<PageBuilderPublishTab project={project} liveSitePath="/site/disco2/" />);

    expect(screen.queryByRole("button", { name: /publish site|go live/i })).toBeNull();
  });

  it("offers an explicit live-project switch for a published non-live project", () => {
    const onMakeLive = vi.fn();
    render(
      <PageBuilderPublishTab
        project={project}
        isLiveProject={false}
        onMakeLive={onMakeLive}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Make this the live project" })
    );
    expect(onMakeLive).toHaveBeenCalledOnce();
  });

  it("identifies the live project without showing redundant controls", () => {
    render(<PageBuilderPublishTab project={project} isLiveProject />);

    expect(screen.getByText("Live")).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Make this the live project" })
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /take site offline/i })).toBeNull();
    expect(screen.queryByText(/currently shown on your public website/i)).toBeNull();
  });

  it("uses the production tenant URL for the published form link", () => {
    render(<PageBuilderPublishTab project={projectWithForm} publishedFormIds={["form-1"]} />);

    expect(
      screen.getByDisplayValue("https://madarportal.com/forms/disco2/form-1")
    ).toBeTruthy();
    expect(screen.queryByDisplayValue(/page-builder\/form-preview/)).toBeNull();
  });

  it("does not offer a local form link before a subdomain is configured", () => {
    render(
      <PageBuilderPublishTab
        project={{ ...projectWithForm, publish: {} }}
      />
    );

    expect(
      screen.getByPlaceholderText("Configure a workspace address before sharing the live form.")
    ).toBeTruthy();
  });

  it("does not offer a production form URL before that form is published", () => {
    render(
      <PageBuilderPublishTab
        project={{ ...projectWithForm, status: "draft" }}
        publishedFormIds={[]}
        hasConfiguredSubdomain
      />
    );

    expect(
      screen.getByPlaceholderText("Publish this saved form to create its live link.")
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /preview form/i }).disabled).toBe(true);
  });
  it("opens the saved public-form runtime from Preview form", () => {
    const openPublicFormPage = vi.fn();

    render(
      <PageBuilderPublishTab
        project={projectWithForm}
        publishedFormIds={["form-1"]}
        openPublicFormPage={openPublicFormPage}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /preview form/i }));

    expect(openPublicFormPage).toHaveBeenCalledWith("form-1");
  });

  it("previews the current builder draft while keeping the shared URL canonical", () => {
    const onPreviewSite = vi.fn();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    render(
      <PageBuilderPublishTab
        project={project}
        liveSitePath="/site/disco2/"
        onPreviewSite={onPreviewSite}
      />
    );

    expect(screen.getByDisplayValue("https://madarportal.com/site/disco2/")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /preview site/i }));

    expect(onPreviewSite).toHaveBeenCalledTimes(1);
    expect(openSpy).not.toHaveBeenCalled();
  });

  it("lists every published form and opens the selected form destination", () => {
    const openPublicFormPage = vi.fn();
    const multiFormProject = {
      ...projectWithForm,
      forms: [
        ...projectWithForm.forms,
        { id: "form-2", title: "Request a quote" },
      ],
    };

    render(
      <PageBuilderPublishTab
        project={multiFormProject}
        publishedFormIds={["form-1", "form-2"]}
        openPublicFormPage={openPublicFormPage}
      />
    );

    expect(
      screen.getByDisplayValue("https://madarportal.com/forms/disco2/form-1")
    ).toBeTruthy();
    expect(
      screen.getByDisplayValue("https://madarportal.com/forms/disco2/form-2")
    ).toBeTruthy();

    const previewButtons = screen.getAllByRole("button", { name: /preview form/i });
    fireEvent.click(previewButtons[1]);
    expect(openPublicFormPage).toHaveBeenCalledWith("form-2");
  });});
