import { useCallback, useEffect, useRef, useState } from "react";

export interface CopyFeedbackHandle {
  copied: boolean;
  copyText: (text: string) => Promise<boolean>;
  triggerCopied: () => void;
}

/**
 * Manage transient "Copied!" UI state and clipboard writes with automatic
 * timer cleanup on unmount or repeated clicks.
 */
export function useCopyFeedback(durationMs = 1500): CopyFeedbackHandle {
  const [copied, setCopied] = useState<boolean>(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  const triggerCopied = useCallback(() => {
    setCopied(true);
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      setCopied(false);
      timerRef.current = null;
    }, durationMs);
  }, [durationMs]);

  const copyText = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text) {
        return false;
      }
      try {
        if (typeof navigator !== "undefined" && navigator.clipboard) {
          await navigator.clipboard.writeText(text);
        }
        triggerCopied();
        return true;
      } catch {
        // Clipboard permission may be unavailable in restricted contexts
        return false;
      }
    },
    [triggerCopied],
  );

  return { copied, copyText, triggerCopied };
}
