export interface HtmlMinifyOptions {
  /** Remove `<script>`, `<style>`, and `<noscript>` blocks. */
  stripScriptsAndStyles: boolean;
  /** Remove inline `<svg>...</svg>` blocks. */
  stripSvg: boolean;
  /** Remove `<head>...</head>` block. */
  stripHead: boolean;
  /** Remove `<!-- ... -->` HTML comments. */
  stripComments: boolean;
  /** Collapse inter-tag and repeated whitespace (`>\s+<` -> `><`). */
  collapseWhitespace: boolean;
}

export const DEFAULT_HTML_MINIFY_OPTIONS: HtmlMinifyOptions = {
  stripScriptsAndStyles: true,
  stripSvg: true,
  stripHead: false,
  stripComments: true,
  collapseWhitespace: true,
};

const VOID_HTML_TAGS: ReadonlySet<string> = new Set([
  "area",
  "base",
  "br",
  "col",
  "embed",
  "hr",
  "img",
  "input",
  "link",
  "meta",
  "param",
  "source",
  "track",
  "wbr",
]);

const RAW_TEXT_TAGS: ReadonlySet<string> = new Set([
  "script",
  "style",
  "pre",
  "textarea",
]);

/**
 * Minify HTML before packing it into a shareable URL `#state=...` payload
 * according to user-selected filter options.
 */
export function minifyHtmlForShare(
  html: string,
  options?: Partial<HtmlMinifyOptions>,
): string {
  if (!html) {
    return "";
  }
  const opts: HtmlMinifyOptions = {
    ...DEFAULT_HTML_MINIFY_OPTIONS,
    ...options,
  };

  let out = html;

  if (opts.stripComments) {
    out = out.replace(/<!--[\s\S]*?-->/g, "");
  }

  if (opts.stripScriptsAndStyles) {
    out = out
      .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
      .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, "")
      .replace(/<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi, "");
  }

  if (opts.stripSvg) {
    out = out.replace(/<svg\b[^>]*>[\s\S]*?<\/svg>/gi, "");
  }

  if (opts.stripHead) {
    out = out.replace(/<head\b[^>]*>[\s\S]*?<\/head>/gi, "");
  }

  if (opts.collapseWhitespace) {
    out = out
      .replace(/>\s+</g, "><")
      .replace(/\s{2,}/g, " ")
      .trim();
  }

  return out;
}

interface HtmlToken {
  type: "open" | "close" | "void" | "comment" | "doctype" | "text";
  raw: string;
  tagName?: string;
}

function tokenizeHtml(html: string): HtmlToken[] {
  const tokens: HtmlToken[] = [];
  const tagRegex =
    /<!--[\s\S]*?-->|<!DOCTYPE[^>]*>|<\/?[a-zA-Z][a-zA-Z0-9:-]*(?:\s+[^<>]*?)?\s*\/?>/gi;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tagRegex.exec(html)) !== null) {
    if (match.index > lastIndex) {
      const textSlice = html.slice(lastIndex, match.index);
      const normalized = textSlice.replace(/\s+/g, " ").trim();
      if (normalized) {
        tokens.push({ type: "text", raw: normalized });
      }
    }

    const rawTag = match[0];
    if (rawTag.startsWith("<!--")) {
      tokens.push({ type: "comment", raw: rawTag.trim() });
    } else if (/^<!doctype/i.test(rawTag)) {
      tokens.push({ type: "doctype", raw: rawTag.trim() });
    } else if (rawTag.startsWith("</")) {
      const nameMatch = /^<\/\s*([a-zA-Z0-9:-]+)/.exec(rawTag);
      const tagName = nameMatch ? nameMatch[1].toLowerCase() : "";
      tokens.push({
        type: "close",
        raw: `</${tagName}>`,
        tagName,
      });
    } else {
      const nameMatch = /^<\s*([a-zA-Z0-9:-]+)/.exec(rawTag);
      const tagName = nameMatch ? nameMatch[1].toLowerCase() : "";
      const selfClosing =
        rawTag.endsWith("/>") || VOID_HTML_TAGS.has(tagName);
      const cleanedTag = rawTag.replace(/\s+/g, " ").trim();

      if (RAW_TEXT_TAGS.has(tagName) && !selfClosing) {
        const closeRe = new RegExp(`<\\/\\s*${tagName}\\s*>`, "gi");
        closeRe.lastIndex = tagRegex.lastIndex;
        const closeMatch = closeRe.exec(html);
        if (closeMatch) {
          const fullBlock = html.slice(
            match.index,
            closeMatch.index + closeMatch[0].length,
          );
          tokens.push({
            type: "void",
            raw: fullBlock.trim(),
            tagName,
          });
          tagRegex.lastIndex = closeMatch.index + closeMatch[0].length;
          lastIndex = tagRegex.lastIndex;
          continue;
        }
      }

      tokens.push({
        type: selfClosing ? "void" : "open",
        raw: cleanedTag,
        tagName,
      });
    }

    lastIndex = tagRegex.lastIndex;
  }

  if (lastIndex < html.length) {
    const trailing = html.slice(lastIndex).replace(/\s+/g, " ").trim();
    if (trailing) {
      tokens.push({ type: "text", raw: trailing });
    }
  }

  return tokens;
}

/**
 * Format HTML with readable multi-line indentation.
 * Keeps short leaf elements (`<h1>Title</h1>`, `<span class="x">val</span>`)
 * on a single line so expanded minified HTML is compact and easy to inspect.
 */
export function formatHtml(html: string, indentSize = 2): string {
  const trimmed = html.trim();
  if (!trimmed || !trimmed.includes("<")) {
    return html;
  }

  const tokens = tokenizeHtml(trimmed);
  if (tokens.length === 0) {
    return html;
  }

  const indentUnit = " ".repeat(Math.max(1, indentSize));
  const lines: string[] = [];
  let depth = 0;

  for (let i = 0; i < tokens.length; i += 1) {
    const tok = tokens[i];

    if (tok.type === "open") {
      const next1 = tokens[i + 1];
      const next2 = tokens[i + 2];

      // Collapse `<tag>short text</tag>` onto a single line
      if (
        next1 &&
        next1.type === "text" &&
        next1.raw.length <= 80 &&
        next2 &&
        next2.type === "close" &&
        next2.tagName === tok.tagName
      ) {
        lines.push(
          `${indentUnit.repeat(depth)}${tok.raw}${next1.raw}${next2.raw}`,
        );
        i += 2;
        continue;
      }

      // Collapse empty `<tag></tag>` onto a single line
      if (next1 && next1.type === "close" && next1.tagName === tok.tagName) {
        lines.push(`${indentUnit.repeat(depth)}${tok.raw}${next1.raw}`);
        i += 1;
        continue;
      }

      lines.push(`${indentUnit.repeat(depth)}${tok.raw}`);
      depth += 1;
      continue;
    }

    if (tok.type === "close") {
      depth = Math.max(0, depth - 1);
      lines.push(`${indentUnit.repeat(depth)}${tok.raw}`);
      continue;
    }

    lines.push(`${indentUnit.repeat(depth)}${tok.raw}`);
  }

  return lines.join("\n");
}
