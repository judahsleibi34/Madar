import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import i18n from '../../i18n';
import LearningFormResponses from './LearningFormResponses';
import LearningFormResponseDetail from './LearningFormResponseDetail';
import {learningFormsApi} from './learningFormsApi';
vi.mock('./learningFormsApi',()=>({learningFormsApi:vi.fn()}));
const schema = fields => ({title:'Feedback',sections:[{id:'page',fields}]});
const row = (id,form_id='form',version=1,answers={}) => ({id,form_id,version,answers,submitted_at:'2026-10-11T10:00:00Z',read_at:null});
const definition = fields => ({name:'Feedback',schema:schema(fields)});
const mount=()=>render(<MemoryRouter><LearningFormResponses/></MemoryRouter>);
beforeEach(async()=>{await i18n.changeLanguage('en');learningFormsApi.mockReset();});
afterEach(cleanup);
it('uses historical field labels as columns rather than relabelling old answers with current schema',async()=>{
 const old=row('old','form',1,{email:'old@example.com'}), current=row('new','form',2,{email:'new@example.com'});
 learningFormsApi.mockImplementation(async path=>!path?{items:[{id:'form',name:'Current form'}]}:path.startsWith('/responses?')?{items:[old,current],has_more:false}:{definition:definition([{id:'email',type:'email',label:path==='/responses/old'?'Original email':'Renamed email'}])});
 mount();const table=await screen.findByRole('table',{name:'Form submissions · Current form'});expect(within(table).getByRole('columnheader',{name:'Original email'})).toBeTruthy();expect(within(table).getByRole('columnheader',{name:'Renamed email'})).toBeTruthy();
 const rows=within(table).getAllByRole('row');expect(rows[1].textContent).toContain('old@example.com');expect(rows[1].textContent).not.toContain('new@example.com');expect(within(rows[1]).getAllByRole('cell')[5].textContent).toBe('—');expect(rows[2].textContent).toContain('new@example.com');
});
it('groups distinct forms into their own tables and downloads per-response private files',async()=>{
 const file={id:'private-file',name:'proof.pdf',size:120,type:'application/pdf'};
 learningFormsApi.mockImplementation(async(path,options)=>options?undefined:!path?{items:[{id:'contact',name:'Contact'},{id:'support',name:'Support'}]}:path.startsWith('/responses?')?{items:[row('contact-response','contact',1,{message:'Hello'}),row('support-response','support',1,{proof:file})],has_more:false}:{definition:definition(path.includes('contact-response')?[{id:'message',label:'Message',type:'paragraph'}]:[{id:'proof',label:'Evidence',type:'file'}])});
 mount();const table=await screen.findByRole('table',{name:'Form submissions · Contact'});expect(within(table).queryByRole('columnheader',{name:'Evidence'})).toBeNull();expect(await screen.findByRole('table',{name:'Form submissions · Support'})).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'proof.pdf'}));await waitFor(()=>expect(learningFormsApi).toHaveBeenCalledWith('/responses/support-response/files/private-file',{download:'proof.pdf'}));expect(screen.queryByText('private-file')).toBeNull();
});
it('loads one schema per version and reuses it while paging, preserving zero and multi-select answers',async()=>{
 const fields=[{id:'score',label:'Score',type:'number'},{id:'choices',label:'Choices',type:'checkboxes'}];
 learningFormsApi.mockImplementation(async path=>!path?{items:[{id:'form',name:'Feedback'}]}:path.startsWith('/responses?')?{items:[row(path.includes('offset=50')?'second-page':'first-page','form',1,{score:0,choices:['Yes','Maybe']})],has_more:!path.includes('offset=50')}:{definition:definition(fields)});
 mount();expect(await screen.findByRole('cell',{name:'0'})).toBeTruthy();expect(screen.getByRole('cell',{name:'Yes, Maybe'})).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Next'}));await screen.findByRole('link',{name:'Open'});await waitFor(()=>expect(learningFormsApi).toHaveBeenCalledWith(expect.stringContaining('offset=50')));expect(learningFormsApi.mock.calls.filter(([path])=>path==='/responses/first-page')).toHaveLength(1);expect(learningFormsApi.mock.calls.filter(([path])=>path==='/responses/second-page')).toHaveLength(0);
});
it('fails clearly when a historical schema cannot be loaded and retries without using today\'s labels',async()=>{
 let failed=true;learningFormsApi.mockImplementation(async path=>!path?{items:[{id:'form',name:'Form'}]}:path.startsWith('/responses?')?{items:[row('response','form',1,{field:'Answer'})],has_more:false}:failed?Promise.reject(new Error('offline')):{definition:definition([{id:'field',label:'Historical field',type:'shortText'}])});
 mount();await screen.findByRole('alert');expect(screen.queryByRole('table')).toBeNull();failed=false;fireEvent.click(screen.getByRole('button',{name:'Try again'}));expect(await screen.findByRole('columnheader',{name:'Historical field'})).toBeTruthy();
});
it('shows response metadata, answers and attachment data in tables while retaining notes and read actions',async()=>{
 const detail={...row('response','form',1,{name:'Ada',count:0}),definition:definition([{id:'name',label:'Name',type:'shortText'},{id:'count',label:'Count',type:'number'},{id:'proof',label:'Evidence',type:'file'}]),owner_notes:'',files:[{id:'file',field_id:'proof',filename:'proof.pdf',size_bytes:1024}]};
 learningFormsApi.mockResolvedValue(detail);render(<MemoryRouter initialEntries={['/e-learning/forms/responses/response']}><Routes><Route path='/e-learning/forms/responses/:responseId' element={<LearningFormResponseDetail/>}/></Routes></MemoryRouter>);
 const answers=await screen.findByRole('table',{name:'Answers'});expect(within(answers).getByRole('rowheader',{name:'Name'})).toBeTruthy();expect(within(answers).getByRole('cell',{name:'Ada'})).toBeTruthy();expect(within(answers).getByRole('cell',{name:'0'})).toBeTruthy();expect(screen.getByRole('table',{name:'Supporting documents'})).toBeTruthy();expect(screen.getByRole('table',{name:'Submitter information'})).toBeTruthy();
 fireEvent.click(screen.getByRole('button',{name:'Download: proof.pdf'}));await waitFor(()=>expect(learningFormsApi).toHaveBeenCalledWith('/responses/response/files/file',{download:'proof.pdf'}));fireEvent.change(screen.getByRole('textbox',{name:/Owner notes/}),{target:{value:'Reviewed'}});fireEvent.click(screen.getByRole('button',{name:'Save notes and mark read'}));await waitFor(()=>expect(learningFormsApi).toHaveBeenCalledWith('/responses/response',{method:'PUT',body:{read:true,owner_notes:'Reviewed'}}));
});
it('reuses the Builder workspace with truthful aggregate counts and no fabricated draft lifecycle',async()=>{
 const fields=[{id:'count',label:'Count',type:'number'},{id:'flag',label:'Flag',type:'shortText'}];
 learningFormsApi.mockImplementation(async path=>!path?{items:[{id:'form',name:'Feedback',responses:81,unread:7,schema:schema(fields)}]}:path.startsWith('/responses?')?{items:[row('response','form',1,{count:0,flag:false})],has_more:true}:{definition:definition(fields)});
 const {container}=mount();await screen.findByRole('table');
 expect(container.querySelector('.results-summary-grid').textContent).toContain('81');
 expect(container.querySelector('.results-summary-grid').textContent).toContain('100%');
 expect(screen.getByRole('heading',{name:'Choose form'})).toBeTruthy();
 expect(screen.getByRole('tab',{name:'Completed'})).toBeTruthy();
 expect(screen.queryByRole('tab',{name:'Incomplete'})).toBeNull();
 expect(screen.getByText(/Saving incomplete drafts is not supported/)).toBeTruthy();
 expect(screen.queryByRole('button',{name:'Edit'})).toBeNull();
 expect(screen.queryByRole('button',{name:'Delete'})).toBeNull();
});
it('selects immutable answers inline and saves only E-Learning owner notes and read state',async()=>{
 const fields=[{id:'name',label:'Historical name',type:'shortText'}];
 const detail={...row('response','form',1,{name:'Ada'}),definition:definition(fields),owner_notes:'Initial',files:[]};
 learningFormsApi.mockImplementation(async(path,options)=>options?{}:!path?{items:[{id:'form',name:'Feedback',responses:1}]}:path.startsWith('/responses?')?{items:[detail],has_more:false}:detail);
 mount();fireEvent.click(await screen.findByRole('button',{name:'Answer details'}));
 const notes=await screen.findByRole('textbox',{name:'Owner notes'});expect(notes.value).toBe('Initial');
 expect(document.querySelector('.responses-answer-grid').textContent).toContain('Historical name');
 fireEvent.change(notes,{target:{value:'Reviewed'}});fireEvent.click(screen.getByRole('button',{name:'Save notes and mark read'}));
 await waitFor(()=>expect(learningFormsApi).toHaveBeenCalledWith('/responses/response',{method:'PUT',body:{read:true,owner_notes:'Reviewed'}}));
 expect(learningFormsApi.mock.calls.every(([path])=>!path || !/builder|draft|project/.test(path))).toBe(true);
});
it('does not fabricate zero field counts when the definitions list omits schemas',async()=>{
 learningFormsApi.mockImplementation(async path=>!path?{items:[{id:'form',name:'No submissions',version:3,responses:0}]}:{items:[],has_more:false});
 mount();const formButton=await screen.findByRole('button',{name:/No submissions/});
 expect(within(formButton).getByText('0 answers / — fields')).toBeTruthy();
 expect(within(formButton).queryByText('0 answers / 0 fields')).toBeNull();
});
it('uses the matching immutable form version for chooser field counts',async()=>{
 const fields=[{id:'name',label:'Name',type:'shortText'},{id:'email',label:'Email',type:'email'}];
 learningFormsApi.mockImplementation(async path=>!path?{items:[{id:'form',name:'Versioned form',version:1,responses:1}]}:path.startsWith('/responses?')?{items:[row('response','form',1,{name:'Ada'})],has_more:false}:{definition:definition(fields)});
 mount();const formButton=await screen.findByRole('button',{name:/Versioned form/});
 await waitFor(()=>expect(within(formButton).getByText('1 answer / 2 fields')).toBeTruthy());
});
