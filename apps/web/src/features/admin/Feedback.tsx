import { PageHeader } from '../../components/ui';
import { FeedbackBoard } from '../client/feedback';

export function Feedback() {
  return <><PageHeader eyebrow="CLIENT VOICE" title="Listen. Improve. Keep moving." subtitle="Review client ideas, prioritize changes and publish clear responses." /><FeedbackBoard admin /></>;
}
