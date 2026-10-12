import {cleanup, fireEvent, render, screen, waitFor, within} from '@testing-library/react';
import {MemoryRouter, Routes, Route} from 'react-router-dom';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import i18n from '../../i18n';
import LearningFormEditor from './LearningFormEditor';
import FormsTab from '../PageBuilder/tabs/FormsTab';
import {learningFormsApi} from './learningFormsApi';
vi.mock('./learningFormsApi', () => ({learningFormsApi:vi.fn()}));
const schema = {title:'Feedback',description:'Introduction',access:'enrolled',pageMode:'single',notifyOwner:true,confirmSubmitter:false,submitLabel:'Send',successMessage:'Thank you',sections:[{id:'page',title:'Questions',fields:[{id:'name',type:'shortText',label:'Your name',helpText:'Write your full name',placeholder:'Name',required:true,options:[],defaultValue:'',validation:{minLength:2}},{id:'choice',type:'radio',label:'Support?',required:false,options:['Yes','No']}]}],logicRules:[]};
const record = {id:'existing',name:'Feedback library',status:'inactive',version:7,schema};
const mount = () => render(<MemoryRouter initialEntries={['/e-learning/forms/existing/edit']}><Routes><Route path='/e-learning/forms/:id/edit' element={<LearningFormEditor/>}/></Routes></MemoryRouter>);
const load = async () => {mount();await screen.findByLabelText('Question 1');};
beforeEach(async()=>{await i18n.changeLanguage('en');learningFormsApi.mockReset();learningFormsApi.mockImplementation(async(path,options)=>options?{...record,schema:options.body.schema,version:8}:path===''?{items:[{...record,responses:3}]}:record);});
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('uses the actual Builder library/document/question cards and settings drawer',async()=>{
 await load();expect(document.querySelector('.forms-simple-shell > .simple-add-question')).toBeTruthy();expect(document.querySelector('.forms-simple-document .simple-question-card')).toBeTruthy();expect(document.querySelector('.elearning-form-inspector')).toBeNull();
 expect(screen.queryByRole('button',{name:'Place form'})).toBeNull();expect(screen.queryByRole('button',{name:'Import form'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Form settings'}));expect(screen.getByRole('dialog')).toBeTruthy();expect(screen.getByLabelText(i18n.t('elearning.forms.access',{ns:'dashboard'}))).toBeTruthy();expect(screen.queryByText('Enable quiz mode')).toBeNull();
});
it('saves inline text and choices to independent schema without Builder metadata',async()=>{
 await load();fireEvent.change(screen.getByLabelText('Question 1'),{target:{value:'Full name'}});fireEvent.change(screen.getByPlaceholderText('Shown under the question'),{target:{value:'Help updated'}});
 fireEvent.change(screen.getByPlaceholderText('Option 1'),{target:{value:'Maybe'}});fireEvent.click(screen.getByRole('button',{name:'Save form'}));
 await waitFor(()=>expect(learningFormsApi).toHaveBeenCalledWith('/existing',expect.objectContaining({method:'PUT'})));
 const body=learningFormsApi.mock.calls.find(([,options])=>options?.method==='PUT')[1].body;
 expect(body.expected_version).toBe(7);expect(body.schema.access).toBe('enrolled');expect(body.schema.pageMode).toBe('single');expect(body.schema.sections[0].fields[0]).toEqual({...schema.sections[0].fields[0],label:'Full name',helpText:'Help updated'});expect(body.schema.sections[0].fields[1].options).toEqual(['Maybe','No']);
 expect(JSON.stringify(body)).not.toMatch(/localized|showDetailsEditor|connectedCollectionId|responses|theme|languageMode/);
});
it('retains drafts in preview without saving or enabling public submission',async()=>{
 await load();fireEvent.change(screen.getByLabelText('Question 1'),{target:{value:'Unsaved label'}});fireEvent.click(screen.getByRole('button',{name:'Preview form'}));expect(await screen.findByRole('textbox',{name:/Unsaved label/})).toBeTruthy();expect(screen.getByRole('button',{name:'Send'}).disabled).toBe(true);
 expect(learningFormsApi.mock.calls.some(([,options])=>options?.method)).toBe(false);fireEvent.click(screen.getByRole('button',{name:'Back to editor'}));expect(screen.getByLabelText('Question 1').value).toBe('Unsaved label');
});
it('edits logic in the shared drawer and preserves source/target references',async()=>{
 await load();fireEvent.click(screen.getByRole('button',{name:'Form settings'}));fireEvent.click(screen.getByRole('button',{name:'Add rule'}));fireEvent.change(screen.getByRole('textbox',{name:'Has answer'}),{target:{value:'Alice'}});fireEvent.click(screen.getByRole('button',{name:'Close',exact:true}));fireEvent.click(screen.getByRole('button',{name:'Save form'}));
 await waitFor(()=>expect(learningFormsApi.mock.calls.some(([,options])=>options?.method==='PUT')).toBe(true));const body=learningFormsApi.mock.calls.find(([,options])=>options?.method==='PUT')[1].body;expect(body.schema.logicRules[0]).toMatchObject({sourceFieldId:'name',targetFieldId:'choice',operator:'equals',value:'Alice',action:'show'});
});
it('saves Arabic inline edits as plain schema text and uses RTL drawer direction',async()=>{
 await i18n.changeLanguage('ar');mount();const question=await screen.findByLabelText('السؤال 1');fireEvent.change(question,{target:{value:'الاسم الكامل'}});
 const settings=i18n.t('elearning.forms.title',{ns:'dashboard'});expect(settings).toBeTruthy();expect(document.querySelector('.forms-simple-workbench').getAttribute('dir')).toBe('rtl');
 // Shared Builder content supplies the localized action labels.
 const actions=document.querySelector('.forms-form-actions-group');fireEvent.click(within(actions).getAllByRole('button')[1]);expect(document.querySelector('.quiz-drawer-backdrop').getAttribute('dir')).toBe('rtl');
 fireEvent.click(screen.getByRole('button',{name:'إغلاق',exact:true}));fireEvent.click(screen.getByRole('button',{name:'حفظ النموذج'}));await waitFor(()=>expect(learningFormsApi.mock.calls.some(([,options])=>options?.method==='PUT')).toBe(true));expect(learningFormsApi.mock.calls.find(([,options])=>options?.method==='PUT')[1].body.schema.sections[0].fields[0].label).toBe('الاسم الكامل');
});
it('keeps Builder-only features available for existing Builder consumers by default',()=>{
 const activeForm={...schema,id:'builder-form',name:'Builder form',mode:'form',responses:[]};
 render(<FormsTab project={{forms:[activeForm],theme:{},pages:[],collections:[]}} activeForm={activeForm} fieldTypes={[{id:'shortText',label:'Short answer'}]} selected={{id:'name'}} getFormSections={form=>form.sections} getFormFields={form=>form.sections.flatMap(section=>section.fields)} getFormPlacements={()=>[]} setSelected={vi.fn()} addForm={vi.fn()} deleteActiveForm={vi.fn()}/>);
 expect(screen.getByRole('button',{name:'Import form'})).toBeTruthy();expect(screen.getByRole('button',{name:'Place form'})).toBeTruthy();expect(screen.getByRole('button',{name:'Delete form'})).toBeTruthy();expect(screen.getByText('Form colors')).toBeTruthy();expect(screen.getByRole('textbox',{name:'Page description'})).toBeTruthy();expect(screen.getByText('Templates')).toBeTruthy();expect(document.querySelector('.question-card-toolbar')).toBeTruthy();
});
