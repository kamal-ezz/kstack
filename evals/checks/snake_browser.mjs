// Independent real-browser preflight. Never copied into the evaluated workspace.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

const server = spawn('python3', ['-m', 'http.server', '5173', '--bind', '127.0.0.1'], { stdio: 'ignore' });
const chrome = spawn('chromium', [
  '--headless', '--no-sandbox', '--disable-dev-shm-usage',
  '--remote-debugging-port=9222', '--user-data-dir=/tmp/snake-browser-profile', 'about:blank',
], { stdio: 'ignore' });
let socket;
const pending = new Map();
let sequence = 0;

async function eventually(action) {
  let lastError;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { return await action(); } catch (error) { lastError = error; }
    await delay(100);
  }
  throw lastError;
}

function send(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out`)); }, 5000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

async function click(selector) {
  const point = await evaluate(`(() => {
    const rectangle = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
    return { x: rectangle.x + rectangle.width / 2, y: rectangle.y + rectangle.height / 2 };
  })()`);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 });
}

async function space() {
  const key = { key: ' ', code: 'Space', windowsVirtualKeyCode: 32, nativeVirtualKeyCode: 32 };
  await send('Input.dispatchKeyEvent', { type: 'keyDown', ...key, text: ' ' });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', ...key });
}

const state = () => evaluate(`({ status: document.getElementById('status').textContent,
  focus: { tag: document.activeElement.tagName, id: document.activeElement.id,
    speed: document.activeElement.dataset.speed }, events: window.inputEvidence.slice() })`);

try {
  await eventually(async () => assert.equal((await fetch('http://127.0.0.1:5173')).status, 200));
  const targets = await eventually(async () => {
    const pages = await (await fetch('http://127.0.0.1:9222/json/list')).json();
    assert.ok(pages.some(page => page.type === 'page'));
    return pages;
  });
  socket = new WebSocket(targets.find(page => page.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  socket.addEventListener('message', message => {
    const result = JSON.parse(message.data);
    const entry = pending.get(result.id);
    if (!entry) return;
    pending.delete(result.id);
    clearTimeout(entry.timer);
    if (result.error) entry.reject(new Error(JSON.stringify(result.error)));
    else entry.resolve(result.result);
  });
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 1400, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://127.0.0.1:5173' });
  await eventually(async () => assert.equal(await evaluate("document.getElementById('status')?.textContent"), 'READY TO PLAY'));
  await evaluate(`window.inputEvidence = []; for (const type of ['click', 'keydown', 'keyup']) {
    document.addEventListener(type, event => window.inputEvidence.push({
      type, key: event.key, target: event.target.tagName, speed: event.target.dataset?.speed,
      trusted: event.isTrusted
    }), true);
  }`);
  await click('h1');
  await space();
  assert.equal((await state()).status, 'IN THE GROOVE');
  await space();
  const bodyPause = await state();
  assert.equal(bodyPause.status, 'TAKE A BREATHER');
  await space();
  await click('[data-speed="chill"]');
  const selectedSpeed = await state();
  await space();
  const speedSpace = await state();
  assert.equal(speedSpace.status, 'IN THE GROOVE');
  assert.equal(speedSpace.focus.speed, 'chill');
  assert.ok(speedSpace.events.every(event => event.trusted));
  assert.ok(speedSpace.events.some(event => event.type === 'keydown' && event.key === ' ' && event.speed === 'chill'));
  assert.ok(speedSpace.events.filter(event => event.type === 'click' && event.speed === 'chill').length >= 2);
  console.log(JSON.stringify({ bodyPause, selectedSpeed, speedSpace }, null, 2));
} finally {
  for (const entry of pending.values()) clearTimeout(entry.timer);
  socket?.close();
  chrome.kill('SIGKILL');
  server.kill('SIGKILL');
}
