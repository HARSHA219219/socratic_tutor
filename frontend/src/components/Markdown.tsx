import React from 'react';
import ReactMarkdown from 'react-markdown';
import { markdownPlugins } from '../services/markdownConfig';

/** Renders a tutor reply's Markdown safely (no raw HTML). Re-renders fine while text streams in. */
const Markdown: React.FC<{ text: string; className?: string }> = ({ text, className = '' }) => (
  <div className={`markdown ${className}`}>
    <ReactMarkdown
      remarkPlugins={markdownPlugins}
      components={{
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  </div>
);

export default Markdown;
