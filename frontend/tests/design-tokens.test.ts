/**
 * Guard for the central palette (src/app/globals.css). Components may use token utilities only:
 * bg-brand-700, text-success, bg-status-completed-soft, shadow-card, bg-brand-gradient, ...
 * This test fails on raw Tailwind palette classes, hex colors and inline color styles anywhere in
 * src/, so a new color can only be added in globals.css.
 *
 * Allowed exceptions (documented in the README, "Design system"):
 *   - src/app/global-error.tsx renders without the app stylesheet, so it must use inline styles.
 *   - Inline `width`, `height` and `transform` for values computed at runtime (progress, charts).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..", "src");
const ALLOWED_FILES = new Set(["app/global-error.tsx"]);
const ALLOWED_STYLE_KEYS = new Set(["width", "height", "transform"]);

const PALETTE = [
  "slate",
  "gray",
  "zinc",
  "neutral",
  "stone",
  "red",
  "orange",
  "amber",
  "yellow",
  "lime",
  "green",
  "emerald",
  "teal",
  "cyan",
  "sky",
  "blue",
  "indigo",
  "violet",
  "purple",
  "fuchsia",
  "pink",
  "rose",
  "black",
  "white",
].join("|");
const PREFIXES = [
  "bg",
  "text",
  "border",
  "border-[trblxyse]",
  "ring",
  "ring-offset",
  "outline",
  "fill",
  "stroke",
  "from",
  "via",
  "to",
  "shadow",
  "decoration",
  "divide",
  "placeholder",
  "caret",
  "accent",
].join("|");

const RAW_CLASS = new RegExp(
  `(?<![\\w-])(?:${PREFIXES})-(?:${PALETTE})(?:-\\d{2,3})?(?:\\/\\d+)?(?![\\w-])`,
  "g",
);
const HEX = /(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])/g;
const STYLE_ATTR = /style=\{([\s\S]*?)\}(?=\s*(?:\/?>|\w+=|\n))/g;

export type Violation = { file: string; line: number; text: string; rule: string };

function lineOf(source: string, index: number): number {
  return source.slice(0, index).split("\n").length;
}

/** Every rule broken by one file's source. Exported for the self-test below. */
export function findViolations(file: string, source: string): Violation[] {
  const found: Violation[] = [];
  for (const match of source.matchAll(RAW_CLASS)) {
    found.push({
      file,
      line: lineOf(source, match.index),
      text: match[0],
      rule: "raw palette class",
    });
  }
  for (const match of source.matchAll(HEX)) {
    found.push({ file, line: lineOf(source, match.index), text: match[0], rule: "hex color" });
  }
  for (const match of source.matchAll(STYLE_ATTR)) {
    const body = match[1].trim();
    const literal = body.startsWith("{") && body.endsWith("}");
    const keys = literal ? [...body.matchAll(/([A-Za-z-]+|"[^"]+")\s*:/g)].map((k) => k[1]) : [];
    const bad = !literal || keys.length === 0 || keys.some((key) => !ALLOWED_STYLE_KEYS.has(key));
    if (bad) {
      found.push({
        file,
        line: lineOf(source, match.index),
        text: match[0].slice(0, 80),
        rule: "inline style other than width, height or transform",
      });
    }
  }
  return found;
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

describe("design tokens guard", () => {
  it("finds no raw palette classes, hex colors or inline color styles in src/", () => {
    const violations = sourceFiles(SRC)
      .map((path) => ({ path, file: relative(SRC, path) }))
      .filter(({ file }) => !ALLOWED_FILES.has(file))
      .flatMap(({ path, file }) => findViolations(file, readFileSync(path, "utf8")));

    const report = violations.map((v) => `${v.file}:${v.line}  ${v.rule}: ${v.text}`).join("\n");
    expect(report, "Use the tokens from src/app/globals.css instead").toBe("");
  });

  it("scans a real source tree", () => {
    expect(sourceFiles(SRC).length).toBeGreaterThan(50);
  });
});

describe("the guard itself", () => {
  const rules = (source: string) => findViolations("x.tsx", source).map((v) => v.text);

  it.each([
    ['<p className="text-red-500">', "text-red-500"],
    ['<div className="hover:bg-slate-100/80">', "bg-slate-100/80"],
    ['cn("border-t-emerald-600")', "border-t-emerald-600"],
    ['<span className="text-white">', "text-white"],
    ['<div className="from-indigo-500 to-pink-500">', "from-indigo-500"],
    ['const c = "#4a0e9a";', "#4a0e9a"],
    ['const c = "#fff";', "#fff"],
  ])("rejects %s", (source, expected) => {
    expect(rules(source)).toContain(expected);
  });

  it.each([
    '<p className="text-brand-700 bg-status-completed-soft shadow-card">',
    '<p className="text-primary-foreground bg-brand-gradient ring-highlight-ring">',
    '<a href="#main-content">',
    "<div style={{ width: `${percent}%` }} />",
    "<div style={{ transform: `translateX(-${100 - value}%)` }} />",
    '<li className="todo-item">',
  ])("allows %s", (source) => {
    expect(rules(source)).toEqual([]);
  });

  it("rejects inline color styles and non-literal style objects", () => {
    expect(rules('<p style={{ color: "red" }}>')).toHaveLength(1);
    expect(rules("<p style={{ backgroundColor: theme.bg }}>")).toHaveLength(1);
    expect(rules("<p style={styles} />")).toHaveLength(1);
  });
});
