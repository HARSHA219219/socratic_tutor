/**
 * Incremental Server-Sent Events parser.
 *
 * Feed it raw text as it arrives from the network; it calls `onData` once per
 * complete event with that event's `data:` payload. Events split across network
 * chunks (even mid-line or mid-"\r\n") are buffered until their blank line arrives.
 */
export function createSseParser(onData: (data: string) => void) {
  let buffer = '';

  const drain = () => {
    buffer = buffer.replace(/\r\n/g, '\n');
    let end = buffer.indexOf('\n\n');
    while (end !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const data = block
        .split('\n')
        .filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).replace(/^ /, ''))
        .join('\n');
      if (data) onData(data);
      end = buffer.indexOf('\n\n');
    }
  };

  return {
    push(text: string) {
      buffer += text;
      // A trailing "\r" may be the first half of "\r\n": wait for the next chunk
      if (!buffer.endsWith('\r')) drain();
    },
    /** Flush a final event that wasn't followed by a blank line. */
    end() {
      if (buffer.trim()) {
        buffer += '\n\n';
        drain();
      }
      buffer = '';
    },
  };
}
