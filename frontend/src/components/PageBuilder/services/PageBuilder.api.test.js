import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../../../utils/apiClient";
import {
  BUILDER_CLIENT_CONTRACT,
  createBuilderSiteMember,
  deleteBuilderSiteMember,
  fetchBuilderProject,
  fetchProtectedSitePage,
  fetchBuilderSiteMembers,
  publishBuilderProject,
  updateBuilderProject,
  updateBuilderSiteMember,
} from "./PageBuilder.api";

vi.mock("../../../utils/apiClient", () => ({
  apiFetch: vi.fn(),
  createApiError: vi.fn((response, data) => Object.assign(new Error("API error"), {
    status: response.status,
    data,
  })),
}));

const jsonResponse = (data, { ok = true, status = 200 } = {}) => ({
  ok,
  status,
  text: vi.fn().mockResolvedValue(JSON.stringify(data)),
});

describe("builder project cloud API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("updates and reloads the exact explicit project with the complete schema", async () => {
    const projectId = "3023144a-6f48-46ee-90ed-fe712f51283a";
    const pages = [
      { id: "home", name: "Home" },
      { id: "test-2", name: "Test 2" },
      { id: "page-3", name: "Page 3" },
    ];
    const saved = {
      id: projectId,
      draft_revision: 6,
      draft_schema: { pages },
    };
    apiFetch
      .mockResolvedValueOnce(jsonResponse({ project: saved }))
      .mockResolvedValueOnce(jsonResponse({ project: saved }));

    const update = await updateBuilderProject(projectId, {
      draft_schema: { pages },
      expected_revision: 5,
    });
    const reloaded = await fetchBuilderProject(projectId);

    expect(update).toEqual(saved);
    expect(reloaded.draft_schema.pages).toHaveLength(3);
    expect(apiFetch.mock.calls[0][0]).toBe(`/api/builder/projects/${projectId}`);
    expect(JSON.parse(apiFetch.mock.calls[0][1].body)).toMatchObject({
      expected_revision: 5,
      draft_schema: { pages },
    });
    expect(apiFetch.mock.calls[0][1].headers).toMatchObject({
      "X-Madar-Builder-Contract": BUILDER_CLIENT_CONTRACT,
    });
    expect(apiFetch.mock.calls[1][0]).toBe(`/api/builder/projects/${projectId}`);
  });

  it("sends the current client contract before publishing", async () => {
    apiFetch.mockResolvedValueOnce(jsonResponse({ project: { id: "project-1" } }));
    await publishBuilderProject("project-1", 9);
    expect(apiFetch.mock.calls[0][1].headers).toMatchObject({
      "X-Madar-Builder-Contract": BUILDER_CLIENT_CONTRACT,
    });
    expect(JSON.parse(apiFetch.mock.calls[0][1].body)).toEqual({ expected_revision: 9 });
  });

  it("lists, creates, updates, and removes server-backed site members", async () => {
    const projectId = "project-1";
    const member = {
      id: "21",
      name: "Site Member",
      roleId: "customer",
      status: "Active",
    };
    apiFetch
      .mockResolvedValueOnce(jsonResponse({ members: [member] }))
      .mockResolvedValueOnce(jsonResponse({ member }, { status: 201 }))
      .mockResolvedValueOnce(jsonResponse({ member: { ...member, roleId: "vip" } }))
      .mockResolvedValueOnce(jsonResponse({ removed: true }));

    expect(await fetchBuilderSiteMembers(projectId)).toEqual([member]);
    expect(await createBuilderSiteMember(projectId, {
      full_name: "Site Member",
      email: "member@example.com",
      password: "safe-password",
      role_id: "customer",
      status: "active",
    })).toEqual(member);
    expect(await updateBuilderSiteMember(projectId, member.id, {
      role_id: "vip",
    })).toMatchObject({ roleId: "vip" });
    expect(await deleteBuilderSiteMember(projectId, member.id)).toEqual({ removed: true });

    expect(apiFetch.mock.calls.map(([url]) => url)).toEqual([
      `/api/builder/projects/${projectId}/site-members`,
      `/api/builder/projects/${projectId}/site-members`,
      `/api/builder/projects/${projectId}/site-members/${member.id}`,
      `/api/builder/projects/${projectId}/site-members/${member.id}`,
    ]);
    expect(apiFetch.mock.calls[1][1].method).toBe("POST");
    expect(apiFetch.mock.calls[2][1].method).toBe("PATCH");
    expect(apiFetch.mock.calls[3][1].method).toBe("DELETE");
  });

  it("fetches protected pages through the authenticated public-site API", async () => {
    apiFetch.mockResolvedValueOnce(jsonResponse({
      project: { published_schema: { pages: [{ id: "member-page" }] } },
    }));

    const result = await fetchProtectedSitePage("tenant-site", "/member-area");

    expect(result.project.published_schema.pages[0].id).toBe("member-page");
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/public/sites/tenant-site/pages/member-area",
      { method: "GET", cache: "no-store" }
    );
  });
});
