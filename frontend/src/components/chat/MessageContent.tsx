import { Fragment, type ReactNode } from 'react'


interface MessageContentProps {
  content: string
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /\*\*([^*]+)\*\*/g
  let cursor = 0
  let match: RegExpExecArray | null

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) nodes.push(text.slice(cursor, match.index))
    nodes.push(<strong key={`${keyPrefix}-strong-${match.index}`}>{match[1]}</strong>)
    cursor = match.index + match[0].length
  }
  if (cursor < text.length) nodes.push(text.slice(cursor))
  return nodes
}

export function MessageContent({ content }: MessageContentProps) {
  const lines = content.replace(/\r\n?/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let paragraph: string[] = []

  function flushParagraph() {
    if (paragraph.length === 0) return
    const text = paragraph.join(' ')
    blocks.push(<p key={`paragraph-${blocks.length}`}>{renderInline(text, `p-${blocks.length}`)}</p>)
    paragraph = []
  }

  for (let index = 0; index < lines.length;) {
    const line = lines[index].trim()
    if (!line) {
      flushParagraph()
      index += 1
      continue
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line)
    if (heading) {
      flushParagraph()
      blocks.push(<h3 key={`heading-${blocks.length}`}>{renderInline(heading[2], `h-${blocks.length}`)}</h3>)
      index += 1
      continue
    }

    if (/^[-*]\s+/.test(line)) {
      flushParagraph()
      const items: string[] = []
      while (index < lines.length) {
        const item = /^[-*]\s+(.+)$/.exec(lines[index].trim())
        if (!item) break
        items.push(item[1])
        index += 1
      }
      blocks.push(
        <ul key={`list-${blocks.length}`}>
          {items.map((item, itemIndex) => (
            <li key={`${itemIndex}-${item}`}>{renderInline(item, `li-${blocks.length}-${itemIndex}`)}</li>
          ))}
        </ul>,
      )
      continue
    }

    paragraph.push(line)
    index += 1
  }
  flushParagraph()

  return <div className="chat-message-content">{blocks.map((block, index) => <Fragment key={index}>{block}</Fragment>)}</div>
}
