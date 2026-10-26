import type { ReactNode } from 'react';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { bankProductSections } from './bank-product';

export function safeMarkdownUrl(url: string, allowCitations = false) {
  if (/[\\\u0000-\u0020\u007f]/.test(url)) return '';
  if (allowCitations && /^source:[a-z0-9_-]+$/i.test(url)) return url;
  if (/^(?:https?:|mailto:|tel:)/i.test(url) || /^(?:\/(?!\/)|#|\.\.?\/)/.test(url)) return defaultUrlTransform(url);
  return '';
}

export function MarkdownBody({ children, renderCitation }: { children: string; renderCitation?: (id: string) => ReactNode }) {
  return <div className="markdown-content"><ReactMarkdown remarkPlugins={[remarkGfm, bankProductSections]} skipHtml disallowedElements={['img']}
    urlTransform={url => safeMarkdownUrl(url, Boolean(renderCitation))}
    components={{
      a({ href, children: label }) {
        if (href?.startsWith('source:') && renderCitation) return <>{renderCitation(href.slice(7))}</>;
        return href ? <a href={href} target={/^https?:/i.test(href) ? '_blank' : undefined} rel="noopener noreferrer">{label}</a> : <span>{label}</span>;
      },
      table({ children: rows }) { return <div className="markdown-table-scroll"><table>{rows}</table></div>; },
    }}>{children}</ReactMarkdown></div>;
}
