export const insightValidity = {
  preparedAt: '2026-10-22T09:00:00+03:00',
  // Editorial review deadline for this demo, not an expiry date supplied by worldsteel.
  expiresAt: '2026-10-30T00:00:00+03:00',
  reviewTrigger: 'Пересмотреть раньше, если изменятся цены поставщика, договоры или план закупок.',
  policy: 'Пересмотр — через неделю после подготовки. Это срок проверки вывода, а не обещание неизменности цен.',
} as const;

const dateFormatter = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', timeZone: 'Europe/Moscow' });

export function getInsightValidity(now: Date = new Date(), metadata: { preparedAt: string; expiresAt: string } = insightValidity) {
  const expired = now.getTime() >= new Date(metadata.expiresAt).getTime();
  const reviewDate = dateFormatter.format(new Date(new Date(metadata.expiresAt).getTime() - 1));
  return {
    expired,
    reviewDate,
    preparedDate: dateFormatter.format(new Date(metadata.preparedAt)),
    label: expired ? 'Срок актуальности истёк' : `Актуально до ${reviewDate}`,
  };
}
