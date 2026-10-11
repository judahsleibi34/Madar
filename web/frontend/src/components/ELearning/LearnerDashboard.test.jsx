import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import LearnerDashboard from './LearnerDashboard';
import { fetchMyLearning } from '../../services/elearningPlayer';
vi.mock('../../services/elearningPlayer',()=>({fetchMyLearning:vi.fn()}));
afterEach(()=>{cleanup();vi.resetAllMocks();});
beforeEach(async()=>{await i18n.changeLanguage('en');});
const mount=()=>render(<MemoryRouter><LearnerDashboard /></MemoryRouter>);
it('resumes the exact server lesson or assessment without completing anything',async()=>{
 fetchMyLearning.mockResolvedValue({courses:[{course:{id:'course',name:'Course'},continue_assessment_id:'assessment',progress:{progress_percent:100,completed_lessons:2,total_lessons:2}}]});
 mount();expect((await screen.findByRole('link',{name:'Continue Learning'})).getAttribute('href')).toBe('/my-learning/courses/course/assessments/assessment');
 expect(screen.getByRole('link',{name:'My Certificates'})).toBeTruthy();
});
it('shows no invented next action for an empty enrollment list',async()=>{
 fetchMyLearning.mockResolvedValue({courses:[]});mount();await screen.findByText('No enrolled courses yet.');
 expect(screen.queryByRole('link',{name:'Continue Learning'})).toBeNull();
 expect(screen.getByRole('link',{name:'My Learning'})).toBeTruthy();
});
it('does not infer completion from missing resume targets or 100 percent lesson progress',async()=>{
 fetchMyLearning.mockResolvedValue({courses:[{course:{id:'blocked',name:'Final review pending'},progress:{progress_percent:100,completed_lessons:2,total_lessons:2,completion:{completed:false}}}]});
 mount();expect((await screen.findByRole('link',{name:'Review course'})).getAttribute('href')).toBe('/my-learning/courses/blocked');
 expect(screen.queryByText(i18n.t('elearning.player.completed',{ns:'dashboard'}))).toBeNull();
});
it('shows completion only when the server supplies a completed course fact',async()=>{
 fetchMyLearning.mockResolvedValue({courses:[{course:{id:'finished',name:'Finished'},progress:{progress_percent:100,completed_lessons:2,total_lessons:2,completion:{completed:true}}}]});
 mount();expect(await screen.findByText(i18n.t('elearning.player.completed',{ns:'dashboard'}))).toBeTruthy();
 expect(screen.queryByRole('link',{name:'Review course'})).toBeNull();
});
