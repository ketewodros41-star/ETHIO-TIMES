/**
 * ETHIOTIMES Headline Highlighter Engine
 *
 * Provides intelligent, versatile text highlighting across Instagram templates:
 * 1. Syntax markup: `{phrase}` or `[phrase]` anywhere in the headline.
 * 2. Keyword & Action Verb AI detection (Amharic & English action verbs, metrics, currencies).
 * 3. Position modes: "auto", "middle", "start", "end", "none".
 * 4. Micro-tuning via customIndices (interactive chips in Studio).
 */

export type HighlightMode = "auto" | "end" | "middle" | "start" | "syntax" | "none";

export interface HeadlineSegment {
  text: string;
  isHighlight: boolean;
  wordIndex: number;
}

export interface ParseHeadlineResult {
  cleanHeadline: string;
  segments: HeadlineSegment[];
  highlightedWords: string[];
  highlightIndices: number[];
  detectedMode: HighlightMode;
}

export interface ParseHeadlineOptions {
  mode?: HighlightMode;
  customIndices?: number[];
}

/** Amharic high-impact action verbs and financial/metric triggers */
const AMHARIC_ACTION_VERBS = new Set([
  "ተፈራረመ", "ተፈራረሙ", "ፈረመ", "ፈረሙ",
  "አፀደቀ", "አፀደቁ", "አጸደቀ", "አጸደቁ",
  "ወሰነ", "ወሰኑ", "አስተላለፈ", "አስተላለፉ",
  "ጨመረ", "ጨመሩ", "ቀነሰ", "ቀነሱ",
  "አረጋገጠ", "አረጋገጡ", "አገደ", "አገዱ",
  "አስጠነቀቀ", "አስጠነቀቁ", "ተጀመረ", "ጀመረ", "ጀመሩ",
  "ተመረቀ", "ተመረቁ", "አሸነፈ", "አሸነፉ",
  "ተሸጠ", "ገዛ", "ገዙ", "ተከሰተ", "ደረሰ",
  "አዘዘ", "አዘዙ", "ተቃወመ", "ተቃወሙ",
  "ተገኘ", "ተለቀቀ", "ወጣ", "ገባ",
]);

const AMHARIC_COMPOUND_VERBS: string[][] = [
  ["ይፋ", "አደረገ"],
  ["ይፋ", "አደረጉ"],
  ["ስምምነት", "ተፈራረመ"],
  ["ስምምነት", "ተፈራረሙ"],
  ["ውል", "ተፈራረመ"],
  ["ውል", "ተፈራረሙ"],
  ["ስራ", "ጀመረ"],
  ["ስራ", "ጀመሩ"],
];

const AMHARIC_METRIC_KEYWORDS = new Set([
  "ቢሊዮን", "ሚሊዮን", "ሺህ", "ብር", "ዶላር", "በመቶ",
  "ታሪፍ", "ተመን", "ዋጋ", "ዋንጫ", "ሪከርድ", "ታሪካዊ",
]);

/** English high-impact action verbs and financial triggers */
const ENGLISH_ACTION_VERBS = new Set([
  "signed", "signs", "signing", "sign",
  "approved", "approves", "approving", "approve",
  "unveiled", "unveils", "unveiling", "unveil",
  "slashed", "slashes", "slashing", "slash",
  "surged", "surges", "surging", "surge",
  "confirmed", "confirms", "confirming", "confirm",
  "banned", "bans", "banning", "ban",
  "warned", "warns", "warning", "warn",
  "launched", "launches", "launching", "launch",
  "won", "wins", "winning",
  "agreed", "agrees", "agreeing", "agree",
  "revealed", "reveals", "revealing", "reveal",
  "arrested", "arrests", "arresting", "arrest",
  "ordered", "orders", "ordering", "order",
  "halted", "halts", "halting", "halt",
  "rallies", "rally", "rallied",
  "crashes", "crashed", "crashing", "crash",
  "scouted", "scouts", "scouting",
  "defeated", "defeats", "defeating",
  "record", "historic",
]);

/** Helper to clean punctuation around words for matching */
function cleanWordForMatch(word: string): string {
  return word.replace(/^[^\w\u1200-\u137F]+|[^\w\u1200-\u137F]+$/gu, "").toLowerCase();
}

/** Check if a word looks like a number, currency, or metric */
function isMetricOrNumber(word: string): boolean {
  const clean = cleanWordForMatch(word);
  if (/^[$€£¥]?\d+(?:[.,]\d+)?(?:%|bn|m|k|b|x)?$/i.test(clean)) return true;
  if (/^\d+/.test(clean)) return true;
  return false;
}

/**
 * Main parser: takes a headline string and returns segmented words with highlight flags.
 */
export function parseHeadlineSegments(
  rawHeadline?: string | null,
  options: ParseHeadlineOptions = {}
): ParseHeadlineResult {
  const input = (rawHeadline || "").trim();
  if (!input) {
    return {
      cleanHeadline: "",
      segments: [],
      highlightedWords: [],
      highlightIndices: [],
      detectedMode: options.mode || "auto",
    };
  }

  // 1. Check for explicit inline syntax: `{phrase}` or `[phrase]`
  const syntaxRegex = /[{[](.*?)[}\]]/g;
  const hasSyntax = syntaxRegex.test(input);

  if (hasSyntax) {
    // Parse syntax segments
    const cleanHeadline = input.replace(/[{[\]}]/g, "").replace(/\s+/g, " ").trim();
    const cleanWords = cleanHeadline.split(/\s+/).filter(Boolean);

    // Track which words were inside brackets
    const highlightedIndicesSet = new Set<number>();
    let match: RegExpExecArray | null;
    const bracketRegex = /[{[](.*?)[}\]]/g;

    while ((match = bracketRegex.exec(input)) !== null) {
      const phrase = match[1].trim();
      const phraseWords = phrase.split(/\s+/).filter(Boolean);
      if (phraseWords.length === 0) continue;

      // Find matching word sequence in cleanWords
      for (let i = 0; i <= cleanWords.length - phraseWords.length; i++) {
        let matched = true;
        for (let j = 0; j < phraseWords.length; j++) {
          if (cleanWords[i + j].replace(/[{[\]}]/g, "") !== phraseWords[j]) {
            matched = false;
            break;
          }
        }
        if (matched) {
          for (let j = 0; j < phraseWords.length; j++) {
            highlightedIndicesSet.add(i + j);
          }
          break;
        }
      }
    }

    const highlightIndices = Array.from(highlightedIndicesSet).sort((a, b) => a - b);
    const segments: HeadlineSegment[] = cleanWords.map((word, idx) => ({
      text: word,
      isHighlight: highlightedIndicesSet.has(idx),
      wordIndex: idx,
    }));

    return {
      cleanHeadline,
      segments,
      highlightedWords: highlightIndices.map((i) => cleanWords[i]),
      highlightIndices,
      detectedMode: "syntax",
    };
  }

  // Clean raw headline (no brackets)
  const words = input.split(/\s+/).filter(Boolean);
  const totalWords = words.length;
  const mode = options.mode || "auto";

  let targetIndices = new Set<number>();

  // 2. Custom indices (manual click-to-highlight chips)
  if (options.customIndices && options.customIndices.length > 0) {
    targetIndices = new Set(options.customIndices.filter((idx) => idx >= 0 && idx < totalWords));
  } else if (mode === "none") {
    // All white
    targetIndices = new Set();
  } else if (mode === "start") {
    // Start / Actor Focus
    if (totalWords <= 2) {
      targetIndices.add(0);
    } else if (totalWords <= 5) {
      targetIndices.add(0);
      targetIndices.add(1);
    } else {
      targetIndices.add(0);
      targetIndices.add(1);
    }
  } else if (mode === "middle") {
    // Middle Pivot Focus
    if (totalWords <= 2) {
      targetIndices.add(0);
    } else if (totalWords === 3) {
      targetIndices.add(1); // Exact center
    } else if (totalWords === 4) {
      targetIndices.add(1);
      targetIndices.add(2); // Center 2
    } else if (totalWords === 5) {
      targetIndices.add(2); // Center 1
    } else if (totalWords <= 7) {
      const mid = Math.floor(totalWords / 2);
      targetIndices.add(mid - 1);
      targetIndices.add(mid);
    } else {
      const mid = Math.floor(totalWords / 2);
      targetIndices.add(mid - 1);
      targetIndices.add(mid);
      targetIndices.add(mid + 1);
    }
  } else if (mode === "end") {
    // Classic End Punchline
    if (totalWords <= 2) {
      targetIndices.add(totalWords - 1);
    } else if (totalWords <= 4) {
      targetIndices.add(totalWords - 1);
    } else if (totalWords <= 8) {
      targetIndices.add(totalWords - 2);
      targetIndices.add(totalWords - 1);
    } else {
      targetIndices.add(totalWords - 3);
      targetIndices.add(totalWords - 2);
      targetIndices.add(totalWords - 1);
    }
  } else {
    // 3. Mode is "auto" (Smart AI / Keyword & Grammar Detection)
    // First, scan for compound Amharic verbs (e.g. "ይፋ አደረገ")
    let foundCompound = false;
    for (let i = 0; i < words.length - 1; i++) {
      const w1 = cleanWordForMatch(words[i]);
      const w2 = cleanWordForMatch(words[i + 1]);
      for (const compound of AMHARIC_COMPOUND_VERBS) {
        if (w1 === compound[0] && w2 === compound[1]) {
          targetIndices.add(i);
          targetIndices.add(i + 1);
          foundCompound = true;
          break;
        }
      }
      if (foundCompound) break;
    }

    // Next, scan for high-impact action verbs or financial metrics
    if (!foundCompound) {
      const matchedVerbIndices: number[] = [];
      const matchedMetricIndices: number[] = [];

      words.forEach((w, idx) => {
        const clean = cleanWordForMatch(w);
        if (AMHARIC_ACTION_VERBS.has(clean) || ENGLISH_ACTION_VERBS.has(clean)) {
          matchedVerbIndices.push(idx);
        } else if (AMHARIC_METRIC_KEYWORDS.has(clean) || isMetricOrNumber(w)) {
          matchedMetricIndices.push(idx);
        }
      });

      if (matchedVerbIndices.length > 0) {
        // If an action verb is present, highlight it
        matchedVerbIndices.forEach((idx) => targetIndices.add(idx));
      } else if (matchedMetricIndices.length > 0) {
        // Highlight critical metrics / money
        matchedMetricIndices.forEach((idx) => targetIndices.add(idx));
      } else {
        // Fallback to classic end punchline
        if (totalWords <= 2) {
          targetIndices.add(totalWords - 1);
        } else if (totalWords <= 4) {
          targetIndices.add(totalWords - 1);
        } else if (totalWords <= 8) {
          targetIndices.add(totalWords - 2);
          targetIndices.add(totalWords - 1);
        } else {
          targetIndices.add(totalWords - 3);
          targetIndices.add(totalWords - 2);
          targetIndices.add(totalWords - 1);
        }
      }
    }
  }

  const highlightIndices = Array.from(targetIndices).sort((a, b) => a - b);
  const segments: HeadlineSegment[] = words.map((word, idx) => ({
    text: word,
    isHighlight: targetIndices.has(idx),
    wordIndex: idx,
  }));

  return {
    cleanHeadline: input,
    segments,
    highlightedWords: highlightIndices.map((i) => words[i]),
    highlightIndices,
    detectedMode: mode,
  };
}
