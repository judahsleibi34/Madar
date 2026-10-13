import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it } from 'vitest';
import i18n from '../../i18n';
import OwnerNavigation from './OwnerNavigation';
import LearningFormsNavigation from './LearningFormsNavigation';
import { OwnerPage } from './OwnerUI';
const mount=node=>render(<MemoryRouter>{node}</MemoryRouter>);
beforeEach(async()=>{await i18n.changeLanguage('en');});
afterEach(cleanup);
it('requires both capability and programme enablement for optional application navigation',()=>{
 mount(<OwnerNavigation capabilities={{affiliate:true,tuition:true,exchange:true}} programmeFlags={{affiliate:false,tuition:false,exchange:false}}/>);
 expect(screen.queryByRole('link',{name:'Affiliates'})).toBeNull();expect(screen.queryByRole('link',{name:'Support Programme'})).toBeNull();expect(screen.queryByRole('link',{name:'Exchange Programme'})).toBeNull();expect(screen.queryByRole('button',{name:'Applications'})).toBeNull();
});
it('retains core learning pages and discovers entitled Forms with zero definitions',()=>{
 mount(<OwnerNavigation capabilities={{forms:true}} forms={{visible:false,items:[]}}/>);
 fireEvent.click(screen.getByRole('button',{name:'Learning',exact:true}));expect(screen.getByRole('link',{name:'Courses'})).toBeTruthy();fireEvent.click(screen.getByRole('button',{name:'Forms',exact:true}));expect(screen.getByRole('link',{name:'Manage forms'})).toBeTruthy();expect(screen.getByRole('link',{name:'Form submissions'})).toBeTruthy();expect(screen.queryByRole('link',{name:'Transactions'})).toBeNull();
});
it('collapses groups with accessible expanded state',()=>{
 mount(<OwnerNavigation/>);const group=screen.getByRole('button',{name:'Learning',exact:true});fireEvent.click(group);expect(group.getAttribute('aria-expanded')).toBe('true');fireEvent.click(group);expect(group.getAttribute('aria-expanded')).toBe('false');expect(screen.queryByRole('link',{name:'Courses'})).toBeNull();fireEvent.click(group);expect(screen.getByRole('link',{name:'Courses'})).toBeTruthy();
});
it('keeps submissions active on filtered and response detail routes without listing forms',()=>{
 render(<MemoryRouter initialEntries={['/e-learning/forms/responses/response?form_id=two']}><LearningFormsNavigation discover forms={{items:[{id:'one',name:'First form'},{id:'two',name:'Second form'}]}}/></MemoryRouter>);
 expect(screen.queryByRole('link',{name:'Second form'})).toBeNull();expect(screen.queryByRole('link',{name:'First form'})).toBeNull();expect(screen.getByRole('link',{name:'Form submissions'}).getAttribute('aria-current')).toBe('page');expect(screen.getByRole('link',{name:'Manage forms'}).getAttribute('aria-current')).toBeNull();
});
it('uses real Arabic strings and direction on owner layouts',async()=>{
 await i18n.changeLanguage('ar');const {container}=mount(<OwnerPage><OwnerNavigation capabilities={{forms:true}}/></OwnerPage>);expect(container.querySelector('main').getAttribute('dir')).toBe('rtl');expect(container.querySelector('main').getAttribute('lang')).toBe('ar');fireEvent.click(screen.getByRole('button',{name:i18n.t('elearning.forms.title',{ns:'dashboard'}),exact:true}));expect(screen.getByRole('link',{name:i18n.t('elearning.forms.manage',{ns:'dashboard'})})).toBeTruthy();
});

it('keeps only one section expanded, including Forms, and allows closing it',()=>{
 mount(<OwnerNavigation capabilities={{forms:true,contact:true,reports:true}}/>);
 for(const name of ['Learning','Forms','Website','Insights','Configuration']) {
 fireEvent.click(screen.getByRole('button',{name,exact:true}));
 expect(screen.getAllByRole('button').filter(button=>button.getAttribute('aria-expanded')==='true')).toHaveLength(1);
 }
 fireEvent.click(screen.getByRole('button',{name:'Configuration',exact:true}));
 expect(screen.getAllByRole('button').filter(button=>button.getAttribute('aria-expanded')==='true')).toHaveLength(0);
});
it('makes Academy overview a direct active link without an Overview group',()=>{
 render(<MemoryRouter initialEntries={['/e-learning/dashboard']}><OwnerNavigation/></MemoryRouter>);
 const overview=screen.getByRole('link',{name:'Academy overview'});
 expect(overview.getAttribute('href')).toBe('/e-learning/dashboard');
 expect(overview.getAttribute('aria-current')).toBe('page');
 expect(overview.closest('.admin-sidebar-subnav')).toBeNull();
 expect(screen.queryByRole('button',{name:'Overview',exact:true})).toBeNull();
});
