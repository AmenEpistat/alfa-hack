import { Button } from 'antd';
import { ArrowRight } from 'lucide-react';
import { router, routes } from '@/shared/routing';
import './placeholder.scss';

export function PlaceholderPage({ title, notFound = false }: { title: string; notFound?: boolean }) {
  return <div className="placeholder-page"><p className="page-eyebrow">Альфа-Бизнес</p><h1>{title}</h1><p>{notFound ? 'Проверьте ссылку или вернитесь к подборке инсайтов.' : 'Этот раздел пока не подключён.'}</p><Button type="text" onClick={() => router.navigate(routes.home)}>На главную <ArrowRight size={16} aria-hidden="true" /></Button></div>;
}
