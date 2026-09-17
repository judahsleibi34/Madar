// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import AdminCommercialAccessPage from "./AdminCommercialAccessPage";
import { clearCsrfToken, setCsrfToken } from "../utils/apiClient";
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json"}});
const history={success:true,commercial:{period:null},entitlements:{commercial_status:'review_required',plan_id:null,capabilities:[]},history:{payments:[],periods:[],events:[]},history_has_more:false};
afterEach(()=>{cleanup();clearCsrfToken();vi.unstubAllGlobals();});
it('renders unresolved commercial access and submits a strict idempotent cash command',async()=>{
 setCsrfToken('synthetic-csrf');
 vi.stubGlobal('fetch',vi.fn(async(url,init)=>url.endsWith('/billing/catalog')?json({catalog:{products:[{id:'business',name:'Business',type:'base_plan',price_minor:2500}]}}):init?.method==='POST'?json({success:true,result:{payment_id:'synthetic'}}):json(history)));
 render(<MemoryRouter initialEntries={['/admin/commercial/7']}><Routes><Route path='/admin/commercial/:tenantId' element={<AdminCommercialAccessPage/>}/></Routes></MemoryRouter>);
 await screen.findByText('No proven active plan');await screen.findByRole('option',{name:'Business'});
 fireEvent.change(screen.getByLabelText('Plan',{exact:true}),{target:{value:'business'}});
 fireEvent.change(screen.getByLabelText('Actual amount (USD)',{exact:true}),{target:{value:'25.01'}});
 fireEvent.change(screen.getByLabelText('Valid from',{exact:true}),{target:{value:'2026-09-01T10:00'}});
 fireEvent.change(screen.getByLabelText('Paid through',{exact:true}),{target:{value:'2026-10-01T10:00'}});
 fireEvent.change(screen.getByLabelText('Receipt / reference',{exact:true}),{target:{value:'SYNTHETIC'}});
 fireEvent.change(screen.getByLabelText('Reason / notes',{exact:true}),{target:{value:'Synthetic manual payment proof'}});
 fireEvent.click(screen.getByRole('checkbox'));
 const button=screen.getByRole('button',{name:'Record manual payment',exact:true});fireEvent.click(button);
 await screen.findByText('Commercial command recorded. Repeating the same request returns this result.');
 await waitFor(()=>expect(button.disabled).toBe(false));fireEvent.click(button);
 await waitFor(()=>expect(fetch.mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(2));
 const bodies=fetch.mock.calls.filter(([,init])=>init?.method==='POST').map(([,init])=>JSON.parse(init.body));
 expect(bodies[0]).toEqual(bodies[1]);expect(bodies[0].actual_minor).toBe(2501);expect(bodies[0].idempotency_key).toBeTruthy();expect(bodies[0]).not.toHaveProperty('tenant_id');expect(bodies[0]).not.toHaveProperty('expected_minor');
});
it('does not render the financial form when admin authorization fails',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>json({detail:'Administrator AAL2 required'},403)));
 render(<MemoryRouter initialEntries={['/admin/commercial/7']}><Routes><Route path='/admin/commercial/:tenantId' element={<AdminCommercialAccessPage/>}/></Routes></MemoryRouter>);
 await screen.findByText('Administrator AAL2 required');expect(screen.queryByRole('button',{name:'Record manual payment'})).toBeNull();
});
