import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ExerciseDemonstration } from './ExerciseDemonstration';

afterEach(() => { cleanup(); vi.unstubAllEnvs(); });

describe('exercise demonstrations', () => {
  it('plays an uploaded video in the page', () => {
    vi.stubEnv('VITE_API_URL', 'https://api.example.test/api/v1');
    render(<ExerciseDemonstration name="Squat" videoUrl="/api/v1/media/video-one/file" videoMediaId="video-one" />);
    const video = screen.getByLabelText('Squat video demonstration');
    expect(video.tagName).toBe('VIDEO');
    expect(video).toHaveAttribute('controls');
    expect(video).toHaveAttribute('src', 'https://api.example.test/api/v1/media/video-one/file');
  });

  it('keeps linked demonstrations as links', () => {
    render(<ExerciseDemonstration name="Squat" videoUrl="https://www.youtube.com/watch?v=squat" />);
    expect(screen.queryByLabelText('Squat video demonstration')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open video demonstration/i })).toHaveAttribute('href', 'https://www.youtube.com/watch?v=squat');
  });
});
