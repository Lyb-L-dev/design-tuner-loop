/* Scaffold smoke test — 用 jsdom 真实跑一遍 tuner-scaffold.html 的逻辑
 *
 * 跑法：
 *   npm i jsdom
 *   node scaffold.test.js                     # 测同目录上一层的 assets/tuner-scaffold.html
 *   node scaffold.test.js ./my-copy.html      # 测任意一份副本
 *
 * 退出码 0 = 全过，1 = 有失败（可直接接 CI）。
 */
const fs = require('fs');
const path = require('path');

let JSDOM;
try {
  ({ JSDOM } = require('jsdom'));
} catch (e) {
  console.error('缺少依赖 jsdom。先执行：npm i jsdom');
  process.exit(2);
}

const TARGET = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.resolve(__dirname, '..', 'assets', 'tuner-scaffold.html');

if (!fs.existsSync(TARGET)) {
  console.error('找不到目标脚手架文件：' + TARGET);
  process.exit(2);
}
const html = fs.readFileSync(TARGET, 'utf8');

let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log('  PASS  ' + name); }
  else { fail++; console.log('  FAIL  ' + name + (extra ? '  <- ' + extra : '')); }
};

/* ---- 给 jsdom 打桩 getBoundingClientRect，让标注测量有真实数字可算 ---- */
function installRectStub(win) {
  const R = new Map();
  const set = (sel, r) => R.set(sel, r);
  // mock 本体
  set('#mock', { left: 0, top: 0, width: 390, height: 700, right: 390, bottom: 700 });
  const P = win.Element.prototype;
  P.getBoundingClientRect = function () {
    // 用元素在 DOM 中的路径类名做 key（简单起见：class + 序号）
    for (const [sel, r] of R) {
      const el = win.document.querySelector(sel);
      if (el === this) return { ...r, x: r.left, y: r.top, toJSON() {} };
    }
    // 其他元素：给一个稳定的方块，间距 12px
    const idx = [...win.document.querySelectorAll('*')].indexOf(this);
    const top = 100 + idx * 40;
    return { left: 20, top, width: 300, height: 28, right: 320, bottom: top + 28, x: 20, y: top, toJSON() {} };
  };
  return win;
}

function boot(url) {
  const dom = new JSDOM(html, {
    url: url || 'http://localhost/tuner.html',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
  });
  installRectStub(dom.window);
  return dom;
}

/* ================= 1. 控件生成 ================= */
console.log('\n[1] 清单驱动：控件按 MANIFEST 自动生成');
{
  const dom = boot();
  const d = dom.window.document;
  const ranges = d.querySelectorAll('input[type=range]').length;
  const colors = d.querySelectorAll('input[type=color]').length;
  const segs = d.querySelectorAll('.seg[id^="i-"]').length;
  ok('range 控件 7 个', ranges === 7, 'got ' + ranges);
  ok('color 控件 1 个', colors === 1, 'got ' + colors);
  ok('seg 控件 1 个（底色）', segs === 1, 'got ' + segs);
  ok('分组渲染 4 组（颜色/形状/间距/字体+布局=5）',
     d.querySelectorAll('.grp').length === 5, 'got ' + d.querySelectorAll('.grp').length);
  ok('读数值已填充', d.getElementById('v-radius').textContent === '16px',
     'got ' + d.getElementById('v-radius').textContent);
}

/* ================= 2. 改控件 → CSS 变量真的变 ================= */
console.log('\n[2] 改控件 → mock 根上的 CSS 变量同步');
{
  const dom = boot();
  const w = dom.window, d = w.document;
  const mock = d.getElementById('mock');

  const initRadius = mock.style.getPropertyValue('--radius');
  ok('初始 radius = 16px', initRadius === '16px', 'got ' + initRadius);

  const el = d.getElementById('i-space');
  el.value = '28';
  el.dispatchEvent(new w.Event('input', { bubbles: true }));
  ok('拖 space=28 → --space 变 28px',
     mock.style.getPropertyValue('--space') === '28px',
     'got ' + mock.style.getPropertyValue('--space'));
  ok('实时读数同步', d.getElementById('v-space').textContent === '28px',
     'got ' + d.getElementById('v-space').textContent);

  const c = d.getElementById('i-accent');
  c.value = '#c0392b';
  c.dispatchEvent(new w.Event('input', { bubbles: true }));
  ok('改主色 → --accent 变（无 px 后缀）',
     mock.style.getPropertyValue('--accent') === '#c0392b',
     'got ' + mock.style.getPropertyValue('--accent'));
}

/* ================= 3. 分段控件 + 暗色切换 ================= */
console.log('\n[3] 底色分段控件 → .dark 类切换');
{
  const dom = boot();
  const w = dom.window, d = w.document;
  const mock = d.getElementById('mock');
  ok('默认无 .dark', !mock.classList.contains('dark'));

  const darkBtn = [...d.querySelectorAll('#i-theme button')].find(b => b.dataset.v === 'dark');
  ok('找到「深色」按钮', !!darkBtn);
  darkBtn.click();
  ok('点深色 → mock 加 .dark', mock.classList.contains('dark'));
  ok('按钮选中态切换', darkBtn.classList.contains('on'));
  ok('浅色按钮取消选中',
     ![...d.querySelectorAll('#i-theme button')].find(b => b.dataset.v === 'light').classList.contains('on'));
}

/* ================= 4. 对比度校验（含负向） ================= */
console.log('\n[4] WCAG 对比度校验');
{
  const dom = boot();
  const w = dom.window, d = w.document;
  const warn = d.getElementById('warn');
  ok('默认 #2f6fed 判为通过 AA', warn.className.includes('ok'), 'got "' + warn.className + '" ' + warn.textContent);

  const c = d.getElementById('i-accent');
  c.value = '#ffe600'; // 亮黄配白字，必然极低对比
  c.dispatchEvent(new w.Event('input', { bubbles: true }));
  ok('亮黄主色 → 报错等级 bad', warn.className.includes('bad'), 'got ' + warn.className);
  ok('提示文案含具体比值', /对比度\D{0,4}\d+\.\d+:1/.test(warn.textContent), warn.textContent);
}

/* ================= 5. 预设按钮 ================= */
console.log('\n[5] 画布宽度预设（手机/平板/桌面）');
{
  const dom = boot();
  const w = dom.window, d = w.document;
  const mock = d.getElementById('mock');
  ok('有 3 个预设', d.querySelectorAll('#preset-mockW button').length === 3);
  const pad = [...d.querySelectorAll('#preset-mockW button')].find(b => b.dataset.v === '768');
  pad.click();
  ok('点平板 → --mock-w = 768px', mock.style.getPropertyValue('--mock-w') === '768px',
     'got ' + mock.style.getPropertyValue('--mock-w'));
  ok('滑块同步到 768', d.getElementById('i-mockW').value === '768',
     'got ' + d.getElementById('i-mockW').value);
}

/* ================= 6. 标注测量 ================= */
console.log('\n[6] 标注模式：量出真实间距/内边距/画布宽');
{
  const dom = boot();
  const w = dom.window, d = w.document;
  const annot = d.getElementById('annot');
  annot.checked = true;
  annot.dispatchEvent(new w.Event('change', { bubbles: true }));
  const badges = [...d.querySelectorAll('.badge')].map(b => b.textContent);
  ok('生成了标注徽标', badges.length > 0, 'count=' + badges.length);
  ok('含纵向间距徽标 ↕', badges.some(t => t.startsWith('↕')), JSON.stringify(badges.slice(0, 12)));
  ok('含内边距读数', badges.some(t => t.startsWith('padding')), JSON.stringify(badges.slice(0, 12)));
  ok('含画布宽度读数', badges.some(t => t.startsWith('宽')), JSON.stringify(badges.slice(0, 12)));

  // 关闭后必须清空（防叠加）
  annot.checked = false;
  annot.dispatchEvent(new w.Event('change', { bubbles: true }));
  ok('关闭标注 → 徽标全部清除', d.querySelectorAll('.badge').length === 0,
     'got ' + d.querySelectorAll('.badge').length);

  // 重复开启两次不应叠加
  annot.checked = true; annot.dispatchEvent(new w.Event('change', { bubbles: true }));
  const n1 = d.querySelectorAll('.badge').length;
  annot.dispatchEvent(new w.Event('change', { bubbles: true }));
  const n2 = d.querySelectorAll('.badge').length;
  ok('重复开启不叠加徽标', n1 === n2, n1 + ' vs ' + n2);
}

/* ================= 7. 导出三件套 ================= */
console.log('\n[7] 导出：JSON / CSS / 链接');
{
  const dom = boot();
  const w = dom.window, d = w.document;
  const out = d.getElementById('out');

  const el = d.getElementById('i-radius'); el.value = '24';
  el.dispatchEvent(new w.Event('input', { bubbles: true }));

  d.getElementById('btn-export').click();
  let j = null;
  try { j = JSON.parse(out.value); } catch (e) {}
  ok('导出 JSON 可解析', !!j, out.value.slice(0, 80));
  ok('JSON 里是数字不是字符串', j && j.radius === 24, 'got ' + (j && j.radius));
  ok('JSON 含 theme', j && j.theme === 'light', 'got ' + (j && j.theme));

  d.getElementById('btn-css').click();
  ok('CSS 导出是 :root 块', out.value.startsWith(':root {'), out.value.slice(0, 20));
  ok('CSS 含 --radius: 24px', out.value.includes('--radius: 24px;'), out.value);
  ok('CSS 不含 theme（无 css 映射的项被跳过）', !out.value.includes('theme'), out.value);

  d.getElementById('btn-link').click();
  ok('链接含 #p=', out.value.includes('#p='), out.value.slice(0, 60));
  ok('导出框是 readonly', out.readOnly === true);
}

/* ================= 8. URL hash 回放（分享链接必须无损） ================= */
console.log('\n[8] 链接回放 + localStorage 持久化');
{
  const state = { accent: '#7a3ff2', theme: 'dark', radius: 24, space: 30, cardPad: 32,
                  titleSize: 34, bodySize: 16, coverH: 200, mockW: 1100 };
  const b64 = Buffer.from(JSON.stringify(state), 'utf8').toString('base64');
  const dom = boot('http://localhost/tuner.html#p=' + b64);
  const d = dom.window.document;
  const mock = d.getElementById('mock');
  ok('hash 回放 --radius=24px', mock.style.getPropertyValue('--radius') === '24px',
     'got ' + mock.style.getPropertyValue('--radius'));
  ok('hash 回放 --accent', mock.style.getPropertyValue('--accent') === '#7a3ff2',
     'got ' + mock.style.getPropertyValue('--accent'));
  ok('hash 回放 theme=dark → 有 .dark', mock.classList.contains('dark'));
  ok('hash 回放后滑块位置同步', d.getElementById('i-radius').value === '24',
     'got ' + d.getElementById('i-radius').value);
}
{
  // localStorage：第一次调参，第二次打开应记住
  const dom1 = boot();
  const w1 = dom1.window, d1 = w1.document;
  const el = d1.getElementById('i-space'); el.value = '33';
  el.dispatchEvent(new w1.Event('input', { bubbles: true }));
  const saved = w1.localStorage.getItem('design-tuner-v2');
  ok('调参写入 localStorage', !!saved && JSON.parse(saved).space === 33, String(saved).slice(0, 60));
}
{
  // 重置按钮要清干净
  const dom = boot();
  const w = dom.window, d = w.document;
  const el = d.getElementById('i-space'); el.value = '33';
  el.dispatchEvent(new w.Event('input', { bubbles: true }));
  d.getElementById('btn-reset').click();
  ok('重置 → --space 回 16px', d.getElementById('mock').style.getPropertyValue('--space') === '16px',
     'got ' + d.getElementById('mock').style.getPropertyValue('--space'));
  ok('重置 → localStorage 清空', !w.localStorage.getItem('design-tuner-v2'));
}

console.log('\n================ ' + pass + ' passed, ' + fail + ' failed ================');
process.exit(fail ? 1 : 0);
