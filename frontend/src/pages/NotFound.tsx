import { Compass } from 'lucide-react';
import { Container } from '../components/Layout';
import { ButtonLink, EmptyState } from '../components/ui';

export default function NotFound() {
  return (
    <Container>
      <EmptyState icon={<Compass className="h-5 w-5" />} title="Page not found" action={<ButtonLink to="/">Back to home</ButtonLink>}>
        The page you were looking for does not exist.
      </EmptyState>
    </Container>
  );
}
