import { Tooltip } from 'antd';
import { Sparkles } from 'lucide-react';
import type { GenerationMethod } from '../model/catalog';

export function GenerationLabel({ method }: { method?: GenerationMethod }) {
  if (method !== 'ai' && method !== 'ai_assisted') return null;
  return <Tooltip title="Текст подготовлен с использованием AI. Источники данных указаны рядом с выводами."><span className="generation-label"><Sparkles size={12} aria-hidden="true" />{method === 'ai' ? 'Создано AI' : 'Подготовлено с AI'}</span></Tooltip>;
}
