import {afterEach, beforeEach, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import {MemoryRouter, Route, Routes} from "react-router-dom";
import i18n from "../../i18n";
import AcademyExchangeOpportunities from "./AcademyExchangeOpportunities";
import LearnerExchange from "./LearnerExchange";
import ExchangeResponseDecision from "./ExchangeResponseDecision";
import {academyOwnerApi} from "./academyOwnerApi";
import {learningFormsApi} from "./learningFormsApi";
import {apiFetch} from "../../utils/apiClient";
vi.mock('./academyOwnerApi',()=>({academyOwnerApi:vi.fn()}));
vi.mock('./learningFormsApi',()=>({learningFormsApi:vi.fn()}));
vi.mock('../../utils/apiClient',()=>({apiFetch:vi.fn(),getApiUrl:value=>value}));
const opportunityId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',formId='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const schema={title:'Application questions',access:'public',sections:[{id:'page',title:'Background',fields:[{id:'motivation',type:'shortText',label:'Motivation',required:true}]}],logicRules:[]};
beforeEach(async()=>{await i18n.changeLanguage('en');vi.clearAllMocks();learningFormsApi.mockResolvedValue({items:[]});});
afterEach(cleanup);
it('owner selects a Form and the application shortcut reaches the same Forms inbox',async()=>{
 academyOwnerApi.mockResolvedValue({items:[{id:opportunityId,title:'Exchange',application_form_id:formId,status:'published'}]});
 render(<MemoryRouter><AcademyExchangeOpportunities/></MemoryRouter>);
 expect((await screen.findByRole('link',{name:'Applications'})).getAttribute('href')).toBe(`/e-learning/forms/responses?form_id=${formId}&opportunity_id=${opportunityId}`);
});
it('owner has a clear empty Form state and reuses the existing editor',async()=>{
 academyOwnerApi.mockResolvedValue({items:[]});render(<MemoryRouter><AcademyExchangeOpportunities editing/></MemoryRouter>);
 expect(await screen.findByText('No forms available. Create an application form first.')).toBeTruthy();
 expect(screen.getByRole('link',{name:'Create form'}).getAttribute('href')).toMatch(/^\/e-learning\/forms\/new\?returnTo=/);
});
it.each(['en','ar'])('learner %s detail applies through the existing Forms renderer only',async language=>{
 await i18n.changeLanguage(language);academyOwnerApi.mockResolvedValue({opportunity:{id:opportunityId,title:'Exchange'},form:{id:formId,version:1,schema},can_apply:true,application:null});apiFetch.mockResolvedValue({ok:true,json:async()=>({id:'response'})});
 render(<MemoryRouter initialEntries={[`/exchange/${opportunityId}`]}><Routes><Route path='/exchange/:opportunityId' element={<LearnerExchange detail/>}/></Routes></MemoryRouter>);
 fireEvent.click(await screen.findByRole('button',{name:i18n.t('elearning.exchange.apply',{ns:'dashboard'})}));fireEvent.change(screen.getByLabelText('Motivation *'),{target:{value:'Learn abroad'}});fireEvent.submit(screen.getByRole('button',{name:i18n.t('elearning.forms.submit',{ns:'dashboard'})}).closest('form'));
 await waitFor(()=>expect(apiFetch).toHaveBeenCalled());expect(apiFetch.mock.calls[0][0]).toBe(`/elearning/owner/exchange/opportunities/${opportunityId}/responses`);
 const payload=JSON.parse(apiFetch.mock.calls[0][1].body.get('payload'));expect(payload.answers).toEqual({motivation:'Learn abroad'});expect(payload).not.toHaveProperty('tenant_id');
 expect(document.querySelector('.learning-form-runtime')?.getAttribute('dir') || i18n.dir()).toBe(language==='ar'?'rtl':'ltr');
});
it('Exchange review posts a revisioned decision and never writes answers or Forms read status',async()=>{
 academyOwnerApi.mockResolvedValue({status:'approved'});const changed=vi.fn();render(<MemoryRouter><ExchangeResponseDecision context={{title:'Exchange',decision:{status:'submitted',revision:3},history:[]}} responseId='response' onChanged={changed}/></MemoryRouter>);
 fireEvent.change(screen.getByLabelText('Status'),{target:{value:'approved'}});fireEvent.change(screen.getByLabelText(i18n.t('elearning.programmes.note',{ns:'dashboard'})),{target:{value:'Reviewed'}});fireEvent.submit(screen.getByRole('button',{name:'Save Changes'}).closest('form'));
 await waitFor(()=>expect(changed).toHaveBeenCalled());expect(academyOwnerApi).toHaveBeenCalledWith('/exchange/responses/response/decision',{method:'PUT',body:{status:'approved',note:'Reviewed',revision:3}});
});

it('returning from the shared Form editor preserves unsaved opportunity values and selects that Form',async()=>{
 const otherForm='dddddddd-dddd-4ddd-8ddd-dddddddddddd';
 academyOwnerApi.mockResolvedValue({items:[{id:opportunityId,title:'Saved opportunity',deadline:'2026-11-01T10:00:00Z',application_form_id:formId,status:'draft'}]});learningFormsApi.mockResolvedValue({items:[{id:otherForm,name:'New application',status:'active'}]});
 render(<MemoryRouter initialEntries={[{pathname:`/e-learning/exchange-opportunities/${opportunityId}/edit`,state:{exchangeDraft:{title:'Unsaved title',deadline:'2026-12-01T12:00'},selectedForm:otherForm}}]}><Routes><Route path='/e-learning/exchange-opportunities/:id/edit' element={<AcademyExchangeOpportunities editing/>}/></Routes></MemoryRouter>);
 expect(await screen.findByDisplayValue('Unsaved title')).toBeTruthy();expect(screen.getByLabelText('Application form').value).toBe(otherForm);expect(screen.getByLabelText('Application deadline').value).toBe('2026-12-01T12:00');
});
