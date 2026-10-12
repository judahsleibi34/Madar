import {cleanup,render,screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {afterEach,expect,it,vi} from 'vitest';
import i18n from '../../i18n';
import AcademyStudentsPage from './AcademyStudentsPage';
import {apiFetch} from '../../utils/apiClient';
vi.mock('../../utils/apiClient',()=>({apiFetch:vi.fn(),getApiUrl:path=>path}));afterEach(cleanup);
it('uses backend institution verification and preserves configured classification labels',async()=>{
 await i18n.changeLanguage('ar');apiFetch.mockResolvedValue({ok:true,json:async()=>({learners:[{id:'one',name:'Verified learner',classification:'Institution Student',institution_verified:true,email_verified:true,status:'active'},{id:'two',name:'Custom learner',classification:'Partner students',institution_verified:true,status:'active'}],has_more:false})});render(<MemoryRouter><AcademyStudentsPage/></MemoryRouter>);await screen.findByText('Verified learner');expect(screen.getByRole('row',{name:/Verified learner/}).textContent).toContain('طالب مؤسسة موثّق');expect(screen.getByText(/Partner students/)).toBeTruthy();
});
