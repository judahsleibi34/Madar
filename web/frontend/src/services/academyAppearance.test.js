import { expect, it, vi, afterEach } from 'vitest';
import { getAcademyAppearance } from './academyAppearance';
afterEach(()=>vi.unstubAllEnvs());
it('uses tenant-published branding even when the legacy local preview flag is enabled',()=>{
 vi.stubEnv('VITE_MADAR_LOCAL_LANDING_PREVIEW','true');
 const theme={accent:'#123456'};const site={subdomain:'testing',brand:'Original',theme:{accent:'#ffffff'}};
 expect(getAcademyAppearance(site,{siteChrome:{brand:'Published Academy',logoUrl:'/published-logo.svg'},theme})).toEqual({...site,brand:'Published Academy',logo_url:'/published-logo.svg',theme});
 expect(getAcademyAppearance({...site,subdomain:'another'},null).brand).toBe('Original');
});
