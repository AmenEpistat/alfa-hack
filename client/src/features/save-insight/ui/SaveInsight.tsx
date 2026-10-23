import { Bookmark } from 'lucide-react';
import { Button } from 'antd';
import { observer } from 'mobx-react-lite';
import { insightPreferencesStore as insights, insightId } from '@/entities/insight';

export const SaveInsight = observer(function SaveInsight({ id = insightId, iconOnly = false }: { id?: string; iconOnly?: boolean }) {
  const saved = insights.isSaved(id);
  return <Button type="text" aria-label={saved ? 'Удалить из сохранённых' : 'Сохранить инсайт'}
    icon={<Bookmark size={17} fill={saved ? 'currentColor' : 'none'} aria-hidden="true" />}
    aria-pressed={saved} onClick={() => insights.toggleSavedFor(id)}>
    {iconOnly ? null : saved ? 'Сохранено' : 'Сохранить'}
  </Button>;
});
