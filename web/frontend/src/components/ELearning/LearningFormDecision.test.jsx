import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import i18n from '../../i18n';
import LearningFormDecision from './LearningFormDecision';
import {learningFormsApi} from './learningFormsApi';
vi.mock('./learningFormsApi',()=>({learningFormsApi:vi.fn()}));
const response={id:'response-id',definition:{schema:{}},review:{status:'submitted',revision:4},decision_history:[]};
beforeEach(async()=>{await i18n.changeLanguage('en');learningFormsApi.mockReset();});
afterEach(cleanup);
it('sends the displayed revision and reason and refreshes only after server acceptance',async()=>{
 const onChanged=vi.fn();learningFormsApi.mockResolvedValue({revision:5});
 render(<LearningFormDecision response={response} onChanged={onChanged}/>);
 fireEvent.change(screen.getByRole('combobox'),{target:{value:'approved'}});
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'Owner reviewed the submission'}});
 fireEvent.click(screen.getByRole('button',{name:'Record decision'}));
 await waitFor(()=>expect(onChanged).toHaveBeenCalledOnce());
 expect(learningFormsApi).toHaveBeenCalledWith('/responses/response-id/decision',{method:'POST',body:{status:'approved',note:'Owner reviewed the submission',revision:4}});
});
it('keeps the existing decision when a stale or unauthorized request fails',async()=>{
 const onChanged=vi.fn();learningFormsApi.mockRejectedValue(new Error('conflict'));
 render(<LearningFormDecision response={response} onChanged={onChanged}/>);
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'Review reason'}});
 fireEvent.click(screen.getByRole('button',{name:'Record decision'}));
 expect(await screen.findByRole('alert')).toBeTruthy();expect(onChanged).not.toHaveBeenCalled();
 expect(screen.getByRole('combobox').value).toBe('under_review');
});
it('offers suspension only for approved Affiliate bindings, never ordinary approvals',()=>{
 const view=render(<LearningFormDecision response={{...response,review:{status:'approved',revision:5}}} onChanged={()=>{}}/>);
 expect(screen.queryByRole('combobox')).toBeNull();view.unmount();
 render(<LearningFormDecision response={{...response,definition:{schema:{workflow:{kind:'affiliate'}}},review:{status:'approved',revision:5}}} onChanged={()=>{}}/>);
 expect(screen.getByRole('combobox').value).toBe('suspended');
});
