import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import ChangePasswordPage from './ChangePasswordPage';
import NotificationPreferencesPanel from './NotificationPreferencesPanel';
import { apiFetch } from '../../utils/apiClient';
import { fetchNotificationPreferences, saveNotificationPreference } from '../../services/notificationsApi';
vi.mock('../../utils/apiClient',()=>({apiFetch:vi.fn()}));
vi.mock('../../services/notificationsApi',()=>({fetchNotificationPreferences:vi.fn(),saveNotificationPreference:vi.fn()}));
beforeEach(async()=>{await i18n.changeLanguage('en');});afterEach(()=>{cleanup();vi.clearAllMocks();});
const secret='SQL traceback /srv/backend INTERNAL_SECRET';
it('never renders password API error or success messages supplied by the backend',async()=>{
 apiFetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:secret})}).mockResolvedValueOnce({ok:true,json:async()=>({message:secret})});
 render(<MemoryRouter><ChangePasswordPage/></MemoryRouter>);
 function fill(){for(const [name,value]of [['Current password','OldPassword123!'],['New password','NewPassword123!'],['Confirm new password','NewPassword123!']])fireEvent.change(screen.getByLabelText(name,{exact:true}),{target:{value}});}
 fill();fireEvent.click(screen.getByRole('button',{name:'Update password'}));
 expect((await screen.findByRole('alert')).textContent).toBe('Could not update password.');
 await waitFor(()=>expect(document.querySelector('.ecommerce-toast')).toBeTruthy());expect(document.body.textContent).not.toContain(secret);
 fill();fireEvent.click(screen.getByRole('button',{name:'Update password'}));await screen.findByText('Password updated successfully.');expect(document.body.textContent).not.toContain(secret);
});
it('keeps preferences editable after a failed save and uses a safe error toast',async()=>{
 fetchNotificationPreferences.mockResolvedValue([{category:'learning',channel:'push',enabled:true}]);saveNotificationPreference.mockRejectedValue(new Error(secret));
 const copy={title:'Notification preferences',description:'Choose channels',loading:'Loading',loadError:'Could not load preferences.',saveError:'Could not save preferences.',categories:{learning:'Learning'},channels:{push:'Push'},deviceNote:'Requires browser permission.'};
 render(<NotificationPreferencesPanel copy={copy}/>);
 fireEvent.click(await screen.findByRole('checkbox',{name:'Push'}));
 await screen.findByRole('alert');expect(screen.getByRole('checkbox',{name:'Push'}).checked).toBe(true);await waitFor(()=>expect(document.querySelector('.ecommerce-toast')).toBeTruthy());expect(document.body.textContent).not.toContain(secret);
});
