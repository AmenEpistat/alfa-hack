type Node = { type: string; value?: string; depth?: number; children?: Node[]; data?: Record<string, unknown> };
const text = (node: Node): string => node.value ?? node.children?.map(text).join('') ?? '';
const isProductTitle = (node: Node) => ['paragraph', 'heading'].includes(node.type) && /^(решение|предложение) от альфа-банка$/i.test(text(node).trim());

// Recognize the standalone marker emitted by insides/markdown.py, not every bank link.
export function bankProductSections() {
  return (root: Node) => {
    const input = root.children ?? [];
    const output: Node[] = [];
    for (let i = 0; i < input.length; i++) {
      if (!isProductTitle(input[i])) { output.push(input[i]); continue; }
      const depth = input[i].depth ?? 2;
      const children: Node[] = [{ type: 'paragraph', data: { hProperties: { className: ['bank-product-label'] } }, children: [{ type: 'text', value: 'Предложение Альфа-Банка' }] }];
      while (i + 1 < input.length && !(input[i + 1].type === 'heading' && (input[i + 1].depth ?? 1) <= depth) && !isProductTitle(input[i + 1])) children.push(input[++i]);
      output.push({ type: 'bankProduct', data: { hName: 'aside', hProperties: { className: ['bank-product'], role: 'note', 'aria-label': 'Предложение Альфа-Банка' } }, children });
    }
    root.children = output;
  };
}

export function articleBody(markdown: string, hasSourcePanel = false) {
  // Header metadata already has a title, category and AI badge; retain all claims below it.
  const body = markdown.replace(/^# [^\n]+\n+/, '').replace(/^> \*\*Сгенерировано ИИ\*\*\s*\n+/, '').replace(/^\*\*Категория:\*\* [^\n]+\n+/, '');
  return hasSourcePanel ? body.replace(/\n## Источники\s*\n[\s\S]*$/, '') : body;
}
