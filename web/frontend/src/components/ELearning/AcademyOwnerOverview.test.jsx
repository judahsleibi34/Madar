import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import AcademyOwnerOverview from './AcademyOwnerOverview';
import useAcademyCapabilities from '../../hooks/useAcademyCapabilities';
import { academyOwnerApi } from './academyOwnerApi';
vi.mock('../../hooks/useAcademyCapabilities',()=>({default:vi.fn()}));
vi.mock('./academyOwnerApi',()=>({academyOwnerApi:vi.fn()}));
beforeEach(async()=>{await i18n.changeLanguage('en');academyOwnerApi.mockResolvedValue({total_learners:0});});
afterEach(()=>{cleanup();vi.clearAllMocks();});
it('opens enabled programmes for management and directs disabled programmes to their configuration',async()=>{
 useAcademyCapabilities.mockReturnValue({capabilities:{affiliate:true,tuition:true,exchange:true,rewards:true,withdrawal:true},programme_flags:{affiliate:true,tuition:false,exchange:false}});
 render(<MemoryRouter><AcademyOwnerOverview user={{id:1}}/></MemoryRouter>);
 expect((await screen.findByRole('link',{name:'Affiliates'})).getAttribute('href')).toBe('/e-learning/programmes/affiliate');
 expect(screen.getByRole('link',{name:'Support Programme'}).getAttribute('href')).toBe('/e-learning/settings?tab=programmes&section=support_settings');
 expect(screen.getByRole('link',{name:'Exchange Programme'}).getAttribute('href')).toBe('/e-learning/settings?tab=programmes&section=exchange_settings');
 expect(screen.getByRole('link',{name:'Referral rewards'}).getAttribute('href')).toBe('/e-learning/finance/rewards');
 expect(screen.getByRole('link',{name:'Withdrawals'}).getAttribute('href')).toBe('/e-learning/finance/withdrawals');
});
it('hides programme shortcuts without the relevant capabilities',async()=>{
 useAcademyCapabilities.mockReturnValue({capabilities:{}});
 render(<MemoryRouter><AcademyOwnerOverview user={{id:1}}/></MemoryRouter>);
 await screen.findByRole('link',{name:'Create course'});
 for(const name of ['Affiliates','Support Programme','Exchange Programme','Withdrawals','Referral rewards','Programme availability'])expect(screen.queryByRole('link',{name})).toBeNull();
});
it('opens the current academy public landing page separately from the website editor',async()=>{
 useAcademyCapabilities.mockReturnValue({capabilities:{contact:true},academy:{subdomain:'tenant-academy'}});
 render(<MemoryRouter><AcademyOwnerOverview user={{id:1}}/></MemoryRouter>);
 const website=await screen.findByRole('link',{name:'View academy website'});
 expect(website.getAttribute('href')).toBe('/academy/tenant-academy');
 expect(website.getAttribute('target')).toBe('_blank');
 expect(screen.getByRole('link',{name:'Edit Website'}).getAttribute('href')).toBe('/e-learning/landing-page');
});
it('shows a fresh toast when a dismissed load error happens again after retry',async()=>{
 useAcademyCapabilities.mockReturnValue({capabilities:{}});academyOwnerApi.mockRejectedValue(new Error('internal SQL secret'));
 render(<MemoryRouter><AcademyOwnerOverview user={{id:1}}/></MemoryRouter>);
 await screen.findByRole('alert');
 await vi.waitFor(()=>expect(document.querySelector('.ecommerce-toast')).toBeTruthy());
 fireEvent.click(screen.getByRole('button',{name:'Dismiss notification'}));
 await vi.waitFor(()=>expect(document.querySelector('.ecommerce-toast')).toBeNull());
 fireEvent.click(screen.getByRole('button',{name:'Try again'}));
 await vi.waitFor(()=>expect(academyOwnerApi).toHaveBeenCalledTimes(2));
 await vi.waitFor(()=>expect(document.querySelector('.ecommerce-toast')).toBeTruthy());
 expect(document.body.textContent).not.toContain('internal SQL secret');
});
