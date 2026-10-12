import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import useAcademyCapabilities from './useAcademyCapabilities';
import { apiFetch } from '../utils/apiClient';
vi.mock('../utils/apiClient',()=>({apiFetch:vi.fn(),getApiUrl:path=>path}));
function Probe({user}) {const value=useAcademyCapabilities(user);return <output>{value===undefined?'loading':value?.can_manage&&value.capabilities?.forms?'allowed':'denied'}</output>;}
beforeEach(()=>vi.resetAllMocks());
describe('academy capability authority',()=>{
 it('uses backend membership authority for a signed-in platform-labelled account',async()=>{apiFetch.mockResolvedValue({ok:true,json:async()=>({can_manage:true,capabilities:{forms:true}})});render(<Probe user={{id:7,tenant_id:2,account_kind:'platform'}}/>);await screen.findByText('allowed');expect(apiFetch).toHaveBeenCalledWith('/elearning/programmes/capabilities',{cache:'no-store'});});
 it('does not grant management when the backend denies it',async()=>{apiFetch.mockResolvedValue({ok:true,json:async()=>({can_manage:false,capabilities:{forms:true}})});render(<Probe user={{id:7,tenant_id:2,account_kind:'platform'}}/>);await screen.findByText('denied');});
 it('clears visible authority when tenant identity changes and ignores stale results',async()=>{let resolve;apiFetch.mockResolvedValueOnce({ok:true,json:async()=>({can_manage:true,capabilities:{forms:true}})}).mockImplementationOnce(()=>new Promise(r=>{resolve=r;}));const {rerender}=render(<Probe user={{id:7,tenant_id:2}}/>);await screen.findByText('allowed');rerender(<Probe user={{id:7,tenant_id:3}}/>);expect(screen.getByText('loading')).toBeTruthy();resolve({ok:false});await waitFor(()=>expect(screen.getByText('denied')).toBeTruthy());});
});
