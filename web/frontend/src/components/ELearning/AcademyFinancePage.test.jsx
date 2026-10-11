import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import i18n from '../../i18n';
import AcademyFinancePage from './AcademyFinancePage';
import { apiFetch } from '../../utils/apiClient';
vi.mock('../../utils/apiClient',()=>({apiFetch:vi.fn(),getApiUrl:path=>path}));
beforeEach(async()=>{apiFetch.mockReset();await i18n.changeLanguage('en');});
afterEach(cleanup);
it('finds a reward source transaction beyond the first ledger page using existing pagination',async()=>{
 apiFetch.mockImplementation(async path=>({ok:true,json:async()=>({items:path.includes('offset=0')?Array.from({length:50},(_,i)=>({id:String(i),reference:'other'})):[{id:'source',reference:'checkout',type:'paid',status:'paid',amount:'30.00',currency:'USD',created_at:'2026-10-11T08:00:00Z'}]})}));
 render(<MemoryRouter initialEntries={['/e-learning/finance/transactions?reference=checkout']}><AcademyFinancePage kind='transactions'/></MemoryRouter>);
 await screen.findByText('30.00 USD');await waitFor(()=>expect(apiFetch).toHaveBeenCalledWith('/elearning/programmes/finance/transactions?limit=50&offset=50'));expect(screen.queryByRole('button',{name:'Next'})).toBeNull();expect(screen.getByRole('link',{name:'View all'})).toBeTruthy();
});
it('shows configuration guidance for disabled programme finance',async()=>{
 apiFetch.mockResolvedValue({ok:false,json:async()=>({detail:{code:'academy_programmes_disabled'}})});render(<MemoryRouter><AcademyFinancePage kind='transactions'/></MemoryRouter>);await screen.findByText(/has not enabled programme finance/);expect(screen.getByRole('link',{name:'Open Settings'}).getAttribute('href')).toBe('/e-learning/settings');
});
it('shows attributed referral amounts and resolves readable linked learner names',async()=>{
 apiFetch.mockImplementation(async path=>({ok:true,json:async()=>path.includes('/owner/students')?{learners:[{user_id:8,name:'Referred learner'}],has_more:false}:{items:[{id:'referral',referred_id:8,code:'LEARN',amount:'10.00',currency:'USD',status:'earned',created_at:'2026-10-11T08:00:00Z'}]}}));render(<MemoryRouter><AcademyFinancePage kind='referrals'/></MemoryRouter>);await screen.findByText('Referred learner');expect(screen.getByText('10.00 USD')).toBeTruthy();
});
it('uses the existing dashboard projection for available and reserved rewards',async()=>{
 apiFetch.mockImplementation(async path=>({ok:true,json:async()=>path.includes('/owner/dashboard')?{wallets:[{currency:'USD',available:'40.00',pending:'10.00'}]}:{items:[]}}));render(<MemoryRouter><AcademyFinancePage kind='rewards'/></MemoryRouter>);expect(await screen.findByText('Available balance: 40.00')).toBeTruthy();expect(screen.getByText('Reserved withdrawals: 10.00')).toBeTruthy();
});
