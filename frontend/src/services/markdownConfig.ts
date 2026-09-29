import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

/**
 * Markdown settings for tutor replies:
 * - GitHub-flavoured Markdown: **bold**, _italic_, lists, tables, ~~strike~~, `code`, code blocks
 * - single line breaks are kept (the model often writes line-by-line text)
 * Raw HTML in a reply is never rendered (react-markdown escapes it), and unsafe link
 * protocols such as javascript: are removed by react-markdown's default URL check.
 */
export const markdownPlugins = [remarkGfm, remarkBreaks];
