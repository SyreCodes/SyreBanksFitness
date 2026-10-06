import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthPage } from './AuthPage';

const mocks = vi.hoisted(() => ({ login: vi.fn(), register: vi.fn(), api: vi.fn() }));
vi.mock('../../services/api', () => ({ api: mocks.api }));
vi.mock('../../services/auth', () => ({ useAuth: () => ({ user: null, loading: false, login: mocks.login, register: mocks.register }) }));

function renderAuth(path = '/login') {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={query}><MemoryRouter initialEntries={[path]}><Routes><Route path="/admin" element={<div>Coach workspace</div>} /><Route path="/app/onboarding" element={<div>Your onboarding</div>} /><Route path="*" element={<AuthPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe('account experience', () => {
  beforeEach(() => { mocks.api.mockReset(); mocks.api.mockResolvedValue({}); mocks.login.mockReset(); mocks.register.mockReset(); });
  afterEach(cleanup);

  it('validates login details, exposes password visibility and routes a coach after authentication', async () => {
    mocks.login.mockResolvedValue({ id: 'coach', role: 'COACH', name: 'Coach', email: 'coach@example.com' });
    renderAuth();
    fireEvent.click(screen.getByRole('button', { name: 'Log in to your account' }));
    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument(); expect(mocks.login).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'coach@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-secure-passphrase' } });
    fireEvent.click(screen.getByRole('button', { name: 'Show password' })); expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'text');
    fireEvent.click(screen.getByRole('button', { name: 'Log in to your account' }));
    expect(await screen.findByText('Coach workspace')).toBeInTheDocument(); expect(mocks.login).toHaveBeenCalledWith('coach@example.com', 'a-secure-passphrase');
  });

  it('prevents registration when password confirmation differs', async () => {
    renderAuth('/register');
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Aline Example' } });
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'aline@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-secure-passphrase' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'a-different-passphrase' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create your account' }));
    expect(await screen.findByText('Your passwords do not match.')).toBeInTheDocument(); expect(mocks.register).not.toHaveBeenCalled();
  });

  it('explains a missing reset token instead of submitting an invalid reset', () => {
    renderAuth('/reset-password');
    expect(screen.getByText('You need a reset link.')).toBeInTheDocument(); expect(screen.getByRole('link', { name: /Request a reset link/ })).toHaveAttribute('href', '/forgot-password');
    expect(screen.queryByRole('button', { name: 'Set your new password' })).not.toBeInTheDocument();
  });
});
