import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

interface Citation {
  index: number;
  url: string;
}

// 轻量渲染:把 [n] 替换为悬浮预览的引用上标,其余按纯文本+换行
export function CitationText({ text, citations }: { text: string; citations: Citation[] | null }) {
  const parts = text.split(/(\[\d+\])/g);
  const citationFor = (label: string) => {
    const index = Number(label.slice(1, -1));
    return citations?.find((c) => c.index === index);
  };

  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[\d+\]$/);
        if (match) {
          const citation = citationFor(part);
          if (citation) {
            return (
              <Popover key={i}>
                <PopoverTrigger asChild>
                  <button
                    type="button"
                    className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-accent/15 px-1 align-super text-[10px] font-bold text-accent transition-colors hover:bg-accent/30"
                    aria-label={`引用 ${citation.index}`}
                  >
                    {citation.index}
                  </button>
                </PopoverTrigger>
                <PopoverContent className="w-80 p-3" side="top">
                  <p className="text-xs font-semibold text-muted-foreground">引用 [{citation.index}]</p>
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 block break-all text-sm text-primary hover:underline"
                  >
                    {citation.url}
                  </a>
                </PopoverContent>
              </Popover>
            );
          }
          return <span key={i}>{part}</span>;
        }
        return (
          <span key={i}>
            {part.split("\n").map((line, j, arr) => (
              <span key={j}>
                {line}
                {j < arr.length - 1 && <br />}
              </span>
            ))}
          </span>
        );
      })}
    </>
  );
}
