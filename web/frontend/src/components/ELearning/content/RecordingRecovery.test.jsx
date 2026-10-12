import {useState} from 'react';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import i18n from '../../../i18n';
import AssessmentQuestions from './AssessmentQuestions';
import {uploadAssessmentRecording} from '../../../services/elearningAssessments';
vi.mock('../../../services/elearningAssessments',()=>({uploadAssessmentRecording:vi.fn()}));
vi.mock('./SpeakingRecorder',()=>({default:({onChange})=><button type="button" onClick={()=>onChange(new Blob(['wav'],{type:'audio/wav'}))}>Capture replacement</button>}));
const id='ac667c0d-2d5f-4822-a5c6-41e1f9ddf001',qid='ac667c0d-2d5f-4822-a5c6-41e1f9ddf002';
const question={id:qid,type:'speaking',prompt:'Explain a choice.',points:5,config:{max_duration_seconds:30,max_size_bytes:100000}};
function Runtime(){const[answers,setAnswers]=useState({});return <AssessmentQuestions attemptId="attempt" questions={[question]} recordings={{[qid]:id}} answers={answers} onChange={(key,value)=>setAnswers(previous=>({...previous,[key]:value}))}/>;}
beforeEach(async()=>{vi.clearAllMocks();await i18n.changeLanguage('en');});afterEach(cleanup);
it('restores a server-owned draft recording after a reload without uploading again',()=>{
 const{container}=render(<Runtime/>);fireEvent.click(screen.getByRole('button',{name:'Use previously saved recording'}));
 expect(container.querySelector('audio').getAttribute('src')).toContain('/elearning/assessment-recordings/'+id);
 expect(screen.getByText('Using the saved recording')).toBeTruthy();expect(uploadAssessmentRecording).not.toHaveBeenCalled();
});
it('retains the previous valid recording when replacement upload fails',async()=>{
 uploadAssessmentRecording.mockRejectedValue(new Error('storage unavailable'));render(<Runtime/>);
 fireEvent.click(screen.getByRole('button',{name:'Capture replacement'}));await screen.findByText('Could not save recording. Please record again.');
 fireEvent.click(screen.getByRole('button',{name:'Use previously saved recording'}));await waitFor(()=>expect(screen.getByText('Using the saved recording')).toBeTruthy());
 expect(uploadAssessmentRecording).toHaveBeenCalledTimes(1);
});
