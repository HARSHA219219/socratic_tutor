/**
 * Focused validation for tutor-reply Markdown (Node 22.6+ runs TS directly):
 *   npm run check:markdown
 */
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import { markdownPlugins } from '../src/services/markdownConfig.ts';

const render = (text: string) => renderToStaticMarkup(createElement(ReactMarkdown, { remarkPlugins: markdownPlugins }, text));

let passed = 0;
const check = (name: string, fn: () => void) => {
  fn();
  passed++;
  console.log(`  ok  ${name}`);
};

check('the reported reply: **...** becomes bold and no asterisks remain', () => {
  const html = render(
    '1. **Why did the bicycle fall over?**  \n   **Because it was two-tired!**\n\n' +
    '2. **What do you call cheese that isn\'t yours?**  \n   **Nacho cheese!**',
  );
  assert.match(html, /<strong>Why did the bicycle fall over\?<\/strong>/);
  assert.match(html, /<strong>Nacho cheese!<\/strong>/);
  assert.match(html, /<ol>/);
  assert.doesNotMatch(html, /\*\*/);
});

check('italic, inline code, code blocks, lists and tables', () => {
  const html = render('_think_ about `x*y`\n\n```\nfor i in range(3): pass\n```\n\n- a\n- b\n\n| x | y |\n|---|---|\n| 1 | 2 |');
  assert.match(html, /<em>think<\/em>/);
  assert.match(html, /<code>x\*y<\/code>/);
  assert.match(html, /<pre><code>for i in range\(3\): pass/);
  assert.match(html, /<ul>\s*<li>a<\/li>/);
  assert.match(html, /<table>/);
});

check('single line breaks are kept', () => {
  assert.match(render('line one\nline two'), /line one<br\/>\s*line two/);
});

check('raw HTML and javascript: links are not rendered as live content', () => {
  const html = render('<script>alert(1)</script> <b>x</b> [click](javascript:alert(1))');
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(html, /<b>x<\/b>/);
  assert.doesNotMatch(html, /href="javascript:/i);
});

check('an unfinished bold marker mid-stream renders without breaking', () => {
  const html = render('Think about **gravi');
  assert.match(html, /Think about \*\*gravi/);
});

console.log(`\n${passed} markdown checks passed`);
