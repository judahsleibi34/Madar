import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceCapabilitiesProvider, WorkspaceRouteAccess } from "./WorkspaceCapabilities";
import { useWorkspaceCapabilities, workspaceRouteCapabilities, builderTabCapabilities } from "./capabilityContext";
import matrix from "./planMatrix.generated.json";
import { parseUsdMinor } from "./money";
import { apiFetch, setSelectedTenantId, setCsrfToken, clearCsrfToken } from "../utils/apiClient";

const capabilities = (plan) => Object.entries(matrix.plans[plan]).filter(([,enabled]) => enabled).map(([cap]) => cap);
const response = (tenant, plan, revision = "1") => new Response(JSON.stringify({ entitlements: { tenant_id: tenant, capabilities: capabilities(plan), entitlement_revision: revision } }), { headers: { "Content-Type": "application/json" } });
afterEach(() => { cleanup(); clearCsrfToken(); setSelectedTenantId(null); vi.unstubAllGlobals(); });
function PremiumData({ loaded }) {
  useEffect(() => { loaded(); }, [loaded]);
  return <div>Premium module loaded</div>;
}
function Status() {
  const { ready, can, revision } = useWorkspaceCapabilities();
  return <div>{ready ? `${revision}:${can("ecommerce_management")}` : "waiting"}</div>;
}
function tree(tenant, child, path="/ecommerce/products") {
  return <MemoryRouter initialEntries={[path]}><WorkspaceCapabilitiesProvider user={{id:3,tenant_id:tenant}}><WorkspaceRouteAccess>{child}</WorkspaceRouteAccess></WorkspaceCapabilitiesProvider></MemoryRouter>;
}

describe("workspace capability boundary", () => {
  it.each(["forms","website"])("does not mount or fetch commerce for %s", async (plan) => {
    const loaded=vi.fn();vi.stubGlobal("fetch",vi.fn().mockResolvedValue(response(7,plan)));
    render(tree(7,<PremiumData loaded={loaded}/>));
    await screen.findByText("Plan access required");
    expect(loaded).not.toHaveBeenCalled();expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toContain("/billing/entitlements");
  });
  it.each(["business","business_plus"])("allows commerce for %s after server resolution", async (plan) => {
    const loaded=vi.fn();vi.stubGlobal("fetch",vi.fn().mockResolvedValue(response(7,plan)));
    render(tree(7,<PremiumData loaded={loaded}/>));
    await screen.findByText("Premium module loaded");expect(loaded).toHaveBeenCalledTimes(1);
  });
  it("denies unresolved service and mismatched tenant responses", async () => {
    vi.stubGlobal("fetch",vi.fn().mockResolvedValue(response(8,"business_plus")));
    const loaded=vi.fn();render(tree(7,<PremiumData loaded={loaded}/>));
    await screen.findByText("Workspace access could not be verified.");expect(loaded).not.toHaveBeenCalled();
  });
  it("unmounts premium data immediately when the selected tenant changes", async () => {
    let release;
    vi.stubGlobal("fetch",vi.fn().mockResolvedValueOnce(response(7,"business_plus")).mockImplementationOnce(() => new Promise((resolve) => {release=resolve;})));
    const loaded=vi.fn();const view=render(tree(7,<PremiumData loaded={loaded}/>));
    await screen.findByText("Premium module loaded");
    view.rerender(tree(8,<PremiumData loaded={loaded}/>));
    expect(screen.queryByText("Premium module loaded")).toBeNull();
    await act(async () => release(response(8,"forms")));
    await screen.findByText("Plan access required");expect(loaded).toHaveBeenCalledTimes(1);
  });
  it("revalidates on a backend denial and drops the previous revision", async () => {
    vi.stubGlobal("fetch",vi.fn().mockResolvedValueOnce(response(7,"business_plus","before")).mockResolvedValueOnce(response(7,"forms","after")));
    render(tree(7,<Status/>,"/dashboard"));await screen.findByText("before:true");
    act(() => window.dispatchEvent(new Event("madar:commercial-denied")));
    expect(screen.queryByText("before:true")).toBeNull();await screen.findByText("after:false");
  });
  it("uses only registered capabilities in route and tab policies", () => {
    for (const path of ["/ecommerce/products","/ecommerce/cv-rerank","/calendar","/builder-data","/builder-responses","/page-builder/projects/one/pages","/page-builder/projects/one/forms"]) {
      expect(workspaceRouteCapabilities(path).length).toBeGreaterThan(0);
      for (const cap of workspaceRouteCapabilities(path)) expect(matrix.capabilities).toContain(cap);
    }
    for (const required of Object.values(builderTabCapabilities)) for (const cap of required) expect(matrix.capabilities).toContain(cap);
  });
});

describe("tenant request isolation", () => {
  it("sends the selected tenant only to the trusted API", async () => {
    vi.stubGlobal("fetch",vi.fn().mockImplementation(() => Promise.resolve(new Response('{}',{headers:{'Content-Type':'application/json'}}))));
    setSelectedTenantId(7);await apiFetch('/api/billing/entitlements');await apiFetch('https://untrusted.example.invalid/data');
    expect(fetch.mock.calls[0][1].headers.get('X-Madar-Tenant-ID')).toBe('7');
    expect(fetch.mock.calls[1][1].headers.has('X-Madar-Tenant-ID')).toBe(false);
  });
  it.each([401, 403])("does not retry a mutation in a different tenant after %s refresh", async (status) => {
    let release;
    setCsrfToken("fixture-csrf");
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({detail: status === 403 ? "Invalid CSRF token" : "Unauthorized"}), {status, headers: {"Content-Type":"application/json"}}))
      .mockImplementationOnce(() => new Promise((resolve) => { release = resolve; })));
    setSelectedTenantId(7);
    const pending = apiFetch("/api/ecommerce/products", {method:"POST", body: "{}"});
    const rejected = expect(pending).rejects.toMatchObject({name:"AbortError"});
    await waitFor(() => expect(release).toBeTypeOf("function"));
    setSelectedTenantId(8);
    release(new Response("{}", {headers:{"X-CSRF-Token":"fixture-refreshed"}}));
    await rejected;
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls.filter(([url]) => url === "/api/ecommerce/products")).toHaveLength(1);
  });
  it("does not send a mutation after tenant changes during initial CSRF acquisition", async () => {
    let release;
    vi.stubGlobal("fetch", vi.fn(() => new Promise((resolve) => { release=resolve; })));
    setSelectedTenantId(7);
    const pending=apiFetch("/api/ecommerce/products", {method:"POST",body:"{}"});
    const rejected=expect(pending).rejects.toMatchObject({name:"AbortError"});
    await waitFor(() => expect(release).toBeTypeOf("function"));
    setSelectedTenantId(8);
    release(new Response("{}", {headers:{"X-CSRF-Token":"fixture-acquired"}}));
    await rejected;
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toContain("/auth/user_status");
  });
  it("discards an old tenant's delayed response", async () => {
    let release;vi.stubGlobal('fetch',vi.fn(() => new Promise((resolve) => {release=resolve;})));
    setSelectedTenantId(7);const pending=apiFetch('/api/ecommerce/catalog');const rejected=expect(pending).rejects.toMatchObject({name:'AbortError'});
    await waitFor(() => expect(release).toBeTypeOf('function'));
    setSelectedTenantId(8);release(new Response('{}'));await rejected;
  });
});

describe('manual money input', () => {
  it('converts decimal text directly to exact minor units', () => {
    expect(parseUsdMinor('25.01')).toBe(2501);expect(parseUsdMinor('0.01')).toBe(1);expect(parseUsdMinor('10000000000.00')).toBe(1000000000000);
  });
  it.each(['-1','0','1.001','1e3','NaN','25,00','Infinity','10000000000.01'])('rejects invalid financial input %s',(value) => expect(() => parseUsdMinor(value)).toThrow());
});
