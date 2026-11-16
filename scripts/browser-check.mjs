// Real-browser check of a running stack (`docker compose up --build`), using headless Chrome
// through the DevTools protocol. No dependencies beyond Node.js 22+ and an installed Chrome.
//
//   node scripts/browser-check.mjs [frontend-url]          # default http://localhost:3000
//   CHROME_PATH=/usr/bin/google-chrome node scripts/browser-check.mjs
//
// It registers one throwaway user through the real form, creates a project and tasks with that
// browser session, opens every page at 1440px and 390px wide, checks there is no horizontal page
// scroll on phones, signs out from the phone menu, and saves screenshots to /tmp/workdesk-shots.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync } from "node:fs";

const BASE = process.argv[2] ?? "http://localhost:3000";
const OUT = process.env.SHOTS_DIR ?? "/tmp/workdesk-shots";
const CHROME =
  process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const DEBUG = 9333;
rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${DEBUG}`, "--user-data-dir=/tmp/workdesk-chrome-profile",
  "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "about:blank",
], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const check = (ok, label) => { results.push([ok, label]); console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}`); };

let ws;
try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${DEBUG}/json/list`)).json();
      target = list.find((t) => t.type === "page");
    } catch { await sleep(200); }
  }
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  let seq = 0;
  const pending = new Map();
  const events = [];
  ws.addEventListener("message", (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else events.push(msg);
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, (msg) => (msg.error ? reject(new Error(`${method}: ${msg.error.message}`)) : resolve(msg.result)));
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? "evaluate failed");
    return r.result.value;
  };
  const viewport = (width, height, mobile) =>
    send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
  const waitFor = async (expression, label, ms = 15000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) { if (await evaluate(expression).catch(() => false)) return true; await sleep(200); }
    throw new Error(`timed out waiting for ${label}`);
  };
  const go = async (path) => {
    await send("Page.navigate", { url: `${BASE}${path}` });
    await waitFor("document.readyState === 'complete'", `load ${path}`);
    await sleep(1500); // client data loading
  };
  const shot = async (name) => {
    const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(data, "base64"));
  };
  const overflow = () => evaluate("document.documentElement.scrollWidth - window.innerWidth");
  const consoleErrors = [];
  await send("Page.enable");
  await send("Runtime.enable");
  ws.addEventListener("message", (m) => {
    const msg = JSON.parse(m.data);
    if (msg.method === "Runtime.exceptionThrown") consoleErrors.push(msg.params.exceptionDetails.text);
    if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
      consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description).join(" "));
    }
  });

  console.log(`Real browser (headless Chrome) against ${BASE}`);
  await viewport(1440, 900, false);
  await go("/login");
  await shot("01-login-desktop");
  check(await evaluate("!!document.querySelector('aside[aria-label=\"About Finbase Workdesk\"]')"), "sign-in brand panel visible on desktop");
  await viewport(390, 844, true);
  await sleep(500);
  check((await overflow()) <= 0, "sign-in page: no horizontal scroll at 390px");
  await shot("02-login-phone");

  // Register through the real form (React-controlled inputs need the native setter).
  await viewport(1440, 900, false);
  await go("/register");
  const email = `browser-${Date.now()}@example.com`;
  await evaluate(`(() => {
    const set = (id, v) => { const el = document.getElementById(id);
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
      el.dispatchEvent(new Event('input', { bubbles: true })); };
    set('name', 'Browser Check'); set('email', '${email}'); set('password', 'browser-check-password-1');
    document.querySelector('form[aria-label="Create account"] button[type=submit]').click();
    return true; })()`);
  await waitFor("location.pathname === '/dashboard'", "redirect to the dashboard after registering");
  check(true, "registered through the form and landed on the dashboard");
  await sleep(1500);
  check(await evaluate("document.cookie.includes('csrf_token=') && !document.cookie.includes('access_token')"),
    "only the csrf cookie is readable by JavaScript (session cookies are HttpOnly)");

  // Data through the page's own session (same cookies and CSRF rule as the UI uses).
  const ids = await evaluate(`(async () => {
    const csrf = document.cookie.split('; ').find((c) => c.startsWith('csrf_token=')).split('=')[1];
    const post = (path, body) => fetch('/api/v1' + path, { method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': decodeURIComponent(csrf) },
      body: JSON.stringify(body) }).then((r) => r.json());
    const me = (await (await fetch('/api/v1/auth/me')).json()).data;
    const p = (await post('/projects', { name: 'Website relaunch', description: 'Marketing site rebuild for Q4' })).data;
    const t1 = (await post('/projects/' + p.id + '/tasks', { title: 'Write landing copy', description: 'Hero and pricing', priority: 'high', due_date: '2099-03-01', assignee_id: me.id })).data;
    await post('/projects/' + p.id + '/tasks', { title: 'Design the pricing table', priority: 'medium', due_date: '2000-01-01' });
    await post('/projects/' + p.id + '/tasks', { title: 'Set up analytics', priority: 'low' });
    return { project: p.id, task: t1.id };
  })()`);
  check(Boolean(ids.project && ids.task), "created a project and tasks with the browser session (proxy, cookies, CSRF)");

  const pages = [
    ["dashboard", "/dashboard"],
    ["projects", "/projects"],
    ["project", `/projects/${ids.project}`],
    ["tasks", `/projects/${ids.project}/tasks`],
    ["task", `/projects/${ids.project}/tasks/${ids.task}`],
    ["activity", "/activity"],
    ["settings", "/settings"],
  ];
  let n = 3;
  for (const [name, path] of pages) {
    await viewport(1440, 900, false);
    await go(path);
    const h1 = await evaluate("document.querySelector('h1')?.textContent ?? ''");
    check(h1.length > 0, `${name}: renders (h1 "${h1.slice(0, 40)}")`);
    await shot(`${String(n++).padStart(2, "0")}-${name}-desktop`);
    await viewport(390, 844, true);
    await sleep(700);
    const extra = await overflow();
    check(extra <= 0, `${name}: no horizontal page scroll at 390px (${extra}px)`);
    await shot(`${String(n++).padStart(2, "0")}-${name}-phone`);
  }

  // Phone navigation and sign-out from the sidebar.
  await viewport(390, 844, true);
  await go("/dashboard");
  check(await evaluate("getComputedStyle(document.querySelector('aside[aria-label=Sidebar]')).display === 'none'"), "desktop sidebar is hidden on phones");
  await evaluate("document.querySelector('button[aria-label=\"Open navigation\"]').click(), true");
  await waitFor("!!document.querySelector('[role=dialog]')", "phone menu");
  await sleep(500);
  await shot(`${String(n++).padStart(2, "0")}-phone-menu`);
  check(await evaluate("[...document.querySelectorAll('[role=dialog] button')].some((b) => b.textContent.includes('Sign out'))"), "phone menu has the Sign out button");
  await evaluate("[...document.querySelectorAll('[role=dialog] button')].find((b) => b.textContent.includes('Sign out')).click(), true");
  await waitFor("location.pathname === '/login'", "redirect to sign-in after sign-out");
  check(true, "signed out from the sidebar and returned to sign-in");
  await go("/dashboard");
  check(await evaluate("location.pathname === '/login'"), "a protected page redirects to sign-in after sign-out");

  const realErrors = consoleErrors.filter((e) => !/401|Failed to load resource/.test(e));
  check(realErrors.length === 0, `no uncaught browser errors${realErrors.length ? ": " + realErrors.slice(0, 3).join(" | ") : ""}`);
  console.log(`  user: ${email}`);
} catch (error) {
  check(false, `browser run aborted: ${error.message}`);
} finally {
  ws?.close();
  chrome.kill();
}
const failed = results.filter(([ok]) => !ok).length;
console.log(`\n${results.length - failed} of ${results.length} browser checks passed. Screenshots: ${OUT}`);
process.exit(failed ? 1 : 0);
