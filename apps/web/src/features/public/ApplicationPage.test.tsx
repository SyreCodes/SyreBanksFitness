import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { api } from '../../services/api';
import { ApplicationPage } from './ApplicationPage';
import { applicationDraftKey, initialApplicationValues } from './applicationSchema';
import { PublicContentContext } from './content';

vi.mock('../../services/api', () => ({ api: vi.fn() }));
const apiMock = vi.mocked(api);

function renderApplication(legalVersion = '2026-01') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={query}><MemoryRouter initialEntries={['/apply']}><PublicContentContext.Provider value={{ legal_version: legalVersion }}><ApplicationPage /></PublicContentContext.Provider></MemoryRouter></QueryClientProvider>);
}

const fill = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
const continueStep = () => fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

describe('coaching application', () => {
  beforeEach(() => { sessionStorage.clear(); apiMock.mockReset(); apiMock.mockImplementation(async path => path === '/products' ? { items: [], total: 0 } : { id: 'saved-lead' }); });
  afterEach(cleanup);

  it('blocks invalid identity and preserves a session draft', async () => {
    renderApplication();
    continueStep();
    expect(await screen.findByText('Enter your full name.')).toBeInTheDocument();
    expect(screen.getByText('STEP 01')).toBeInTheDocument();
    fill('Full name', 'Aline Example');
    await waitFor(() => expect(JSON.parse(sessionStorage.getItem(applicationDraftKey) || '{}').name).toBe('Aline Example'));
    expect(apiMock).not.toHaveBeenCalledWith('/leads', expect.anything());
  });

  it('submits the full application with the current policy version and clears its saved draft', async () => {
    renderApplication('2026-07');
    fill('Full name', 'Aline Example'); fill('Email address', 'aline@example.com'); fill('Phone / WhatsApp', '+250780000000'); fill('Country', 'Rwanda'); fill('Age', '28');
    continueStep();
    fireEvent.click(await screen.findByLabelText('Muscle building'));
    fill('What would success look like for you?', 'Build a sustainable strength training routine.'); fill('Your target timeframe', 'Next 6 months'); continueStep();
    fill('Your training experience', 'Some experience'); fill('How often do you train now?', '1–2 days per week'); fireEvent.click(screen.getByLabelText('At a gym')); fill('What equipment can you use?', 'Full gym'); continueStep();
    fill('Occupation / daily routine', 'Desk-based work'); fill('Your daily activity', 'Mostly seated'); fill('Average sleep (hours)', '7.5'); fill('Your usual stress level', 'Moderate'); fireEvent.click(screen.getByLabelText('Mon')); fill('Your preferred training time', 'Evening'); continueStep();
    fireEvent.click(screen.getByLabelText(/Remote coaching/)); continueStep();
    fill('Why is now the right time for you?', 'I want to become more consistent and stronger.'); fill('What is your biggest obstacle?', 'Keeping a consistent schedule'); fill('What have you tried before?', 'Self-directed workouts'); fill('What usually causes you to stop?', 'An unclear training plan'); continueStep();
    fireEvent.click(screen.getByLabelText(/Let’s discuss the right plan/)); continueStep();
    fireEvent.click(screen.getByRole('button', { name: 'Send application' }));
    expect(await screen.findByText('Please agree before submitting your application.')).toBeInTheDocument();
    expect(apiMock).not.toHaveBeenCalledWith('/leads', expect.anything());
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Send application' }));
    expect(await screen.findByText(/Thanks, Aline/)).toBeInTheDocument();
    const call = apiMock.mock.calls.find(([path]) => path === '/leads');
    const body = JSON.parse(call?.[1]?.body as string);
    expect(body).toMatchObject({ name: 'Aline Example', age: 28, sleep_hours: 7.5, goal: 'Muscle building', training_days: ['Monday'], consent: true, consent_version: '2026-07', source: 'WEBSITE' });
    expect(sessionStorage.getItem(applicationDraftKey)).toBeNull();
  });

  it('restores only known draft fields and asks for consent again', () => {
    sessionStorage.setItem(applicationDraftKey, JSON.stringify({ name: 'Aline', training_days: ['Monday'], consent: true, role: 'ADMIN' }));
    const draft = initialApplicationValues(new URLSearchParams());
    expect(draft.name).toBe('Aline'); expect(draft.training_days).toEqual(['Monday']); expect(draft.consent).toBe(false); expect(draft).not.toHaveProperty('role');
  });
});
