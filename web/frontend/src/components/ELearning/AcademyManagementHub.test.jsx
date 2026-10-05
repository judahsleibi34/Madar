import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import i18n from '../../i18n';
import AcademyManagementHub from './AcademyManagementHub';
import { fetchELearningSettings, saveELearningSettings } from '../../services/elearningSettings';
import { initializeAcademyLanding } from '../../services/elearningAcademy';
vi.mock('../../services/elearningSettings', () => ({ fetchELearningSettings: vi.fn(), saveELearningSettings: vi.fn() }));
vi.mock('../../services/elearningAcademy', () => ({ initializeAcademyLanding: vi.fn() }));
const settings = { enabled: true, academy_enabled: true, academy_registration: 'invitation_only', academy_email_domains: [], academy_hero_title: 'Preserved hero', academy_cta_label: 'Preserved CTA', academy_featured_courses: ['course-id'] };
const data = { available: true, settings, academy_management: { subdomain: 'testing', landing_project: null } };
function Destination() { const location = useLocation(); return <p>{location.pathname + location.search}</p>; }
function mount() { return render(<MemoryRouter><Routes><Route path="/" element={<AcademyManagementHub user={{ id: 1, tenant_id: 3 }} />} /><Route path="*" element={<Destination />} /></Routes></MemoryRouter>); }
beforeEach(async () => { await i18n.changeLanguage('en'); fetchELearningSettings.mockResolvedValue(data); saveELearningSettings.mockImplementation(async settings => ({ available: true, settings })); initializeAcademyLanding.mockResolvedValue({ id: 'landing-id' }); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it('offers distinct public and actual student entries without duplicate landing authoring', async () => {
  mount(); await screen.findByRole('button', { name: 'Edit Academy' });
  expect(screen.getByRole('link', { name: 'Open Academy' }).getAttribute('href')).toBe('/academy/testing');
  expect(screen.getByRole('link', { name: 'Open Academy' }).getAttribute('target')).toBe('_blank');
  expect(screen.getByRole('link', { name: 'Open Academy' }).getAttribute('rel')).toBe('noopener noreferrer');
  expect(screen.getByRole('link', { name: 'Open Student Platform' }).getAttribute('href')).toBe('/my-learning');
  expect(screen.getByRole('link', { name: 'Manage Plans' }).getAttribute('href')).toBe('/e-learning/plans');
  expect(screen.queryByLabelText('Hero title')).toBeNull(); expect(screen.queryByText('Preserved hero')).toBeNull();
  expect(initializeAcademyLanding).not.toHaveBeenCalled();
  expect(screen.getByRole('link', { name: 'Open Student Platform' }).getAttribute('target')).toBe('_blank');
});
it('opens the existing visual component workspace directly and initializes only on explicit edit', async () => {
  mount(); fireEvent.click(await screen.findByRole('button', { name: 'Edit Academy' }));
  await screen.findByText('/e-learning/landing-page/projects/landing-id/pages'); expect(initializeAcademyLanding).toHaveBeenCalledTimes(1);
});
it('opens Preview in a new Student Platform tab without initializing a Builder', async () => {
  mount(); const preview = await screen.findByRole('link', { name: 'Preview', exact: true });
  expect(preview.getAttribute('href')).toBe('/my-learning');
  expect(preview.getAttribute('target')).toBe('_blank');
  expect(preview.getAttribute('rel')).toBe('noopener noreferrer');
  expect(initializeAcademyLanding).not.toHaveBeenCalled();
});
it('changes platform access while preserving legacy presentation data and navigation', async () => {
  mount(); fireEvent.change(await screen.findByRole('combobox'), { target: { value: 'open' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save Changes' })); await screen.findByRole('status');
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, academy_registration: 'open' });
  expect(screen.getByRole('link', { name: 'Open Academy' }).getAttribute('href')).toBe('/academy/testing');
});
it('reports changes unpublished using the existing Builder publication comparison', async () => {
  fetchELearningSettings.mockResolvedValue({ ...data, academy_management: { subdomain: 'testing', published_project_id: 'landing-id', landing_project: { id: 'landing-id', draft_schema: { pages: [{ id: 'new' }] }, published_schema: { pages: [{ id: 'old' }] } } } });
  mount(); await screen.findByText('Changes unpublished'); await screen.findByText('Published');
});
it('supports loading failures, retry and Arabic direction', async () => {
  await i18n.changeLanguage('ar'); fetchELearningSettings.mockRejectedValueOnce(new Error('private SQL'));
  const { container } = mount(); await screen.findByRole('alert'); expect(document.body.textContent).not.toContain('private SQL');
  fireEvent.click(screen.getByRole('button')); await screen.findByRole('combobox'); expect(container.querySelector('main').getAttribute('dir')).toBe('rtl');
});

it.each([[404, "The Academy project is unavailable. Open Edit Academy again to recover its binding."], [403, "You need Academy management permission and an active Builder plan to edit the Academy."], [400, "The Academy configuration is invalid. Review its settings and try again."]])("distinguishes Builder error %s from settings save failures", async (status, message) => {
 initializeAcademyLanding.mockRejectedValueOnce({ status }); mount(); fireEvent.click(await screen.findByRole("button", { name: "Edit Academy" }));
 expect((await screen.findByRole("alert")).textContent).toBe(message);
});

it('offers direct email-domain registration and preserves domains while toggling settings', async () => {
  mount(); fireEvent.change(await screen.findByRole('combobox'), { target: { value: 'email_domain' } });
  fireEvent.change(screen.getByLabelText('Allowed email domains'), { target: { value: 'University.edu, college.edu' } });
  fireEvent.click(screen.getByRole('switch'));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'open' } });
  expect(screen.queryByLabelText('Allowed email domains')).toBeNull();
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'email_domain' } });
  expect(screen.getByLabelText('Allowed email domains').value).toBe('University.edu, college.edu');
  expect(screen.getByText(/without an invitation/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Save Changes' })); await screen.findByRole('status');
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, academy_enabled: false, academy_registration: 'email_domain', academy_email_domains: ['University.edu', 'college.edu'] });
});

it('shows a useful domain validation error without backend details', async () => {
  saveELearningSettings.mockRejectedValueOnce({ status: 422, message: 'private internal error' });
  mount(); fireEvent.change(await screen.findByRole('combobox'), { target: { value: 'email_domain' } });
  fireEvent.change(screen.getByLabelText('Allowed email domains'), { target: { value: 'https://university.edu' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
  expect((await screen.findByRole('alert')).textContent).toMatch(/valid domains or example emails/);
  expect(document.body.textContent).not.toContain('private internal error');
});


it('accepts example emails and displays the normalized domain rules returned by the server', async () => {
  saveELearningSettings.mockImplementationOnce(async values => ({ available: true, settings: { ...values, academy_email_domains: ['university.edu', 'college.edu'] } }));
  mount(); fireEvent.change(await screen.findByRole('combobox'), { target: { value: 'email_domain' } });
  fireEvent.change(screen.getByLabelText('Allowed email domains'), { target: { value: 'jack@University.edu, university.edu, college.edu' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));
  await screen.findByRole('status');
  expect(saveELearningSettings).toHaveBeenCalledWith({ ...settings, academy_registration: 'email_domain', academy_email_domains: ['jack@University.edu', 'university.edu', 'college.edu'] });
  expect(screen.getByLabelText('Allowed email domains').value).toBe('university.edu, college.edu');
});
