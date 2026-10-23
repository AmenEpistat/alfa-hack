import { DemoLoginForm } from '@/features/auth-by-demo';
import { Brand } from '@/shared/ui/brand';
import './login.scss';

export function LoginPage({ returningToInsight }: { returningToInsight: boolean }) {
  return <main className="login-page">
    <a className="login-brand" href="#/" aria-label="Альфа-Бизнес — на главную"><Brand /></a>
    <DemoLoginForm returningToInsight={returningToInsight} />
  </main>;
}
