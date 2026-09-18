#!/usr/bin/env python3
"""
browser_verify.py — 在真实 Chromium 里验证 tuner-scaffold.html

为什么需要它：jsdom 不做真实布局、不认 @container、不跑 CSS 过渡，
所以下面这些只有真实浏览器能测出来：
  - 容器查询是否真的把布局从 column 翻成 row
  - 改滑块后 getBoundingClientRect 是否立即反映新尺寸（过渡会骗人）
  - 标注模式量出的间距是否真实、非零、在合理区间
  - 切换暗色后计算样式是否真的变

用法：
    python browser_verify.py                     # 验证 assets/tuner-scaffold.html
    python browser_verify.py path/to/copy.html   # 验证任意副本

退出码：0 全过 / 1 有失败 / 2 环境不可用（找不到浏览器等）
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_TARGET = HERE.parent / "assets" / "tuner-scaffold.html"

PROBE = r"""
<script>
(function(){
  var R = [], errs = [];
  window.addEventListener('error', function(e){ errs.push(String(e.message)); });
  function ok(n, c, x){ R.push((c ? 'PASS' : 'FAIL') + ' :: ' + n + (c ? '' : ' :: got=' + x)); }

  try{
    var d = document, mock = d.getElementById('mock');
    var cs = function(el){ return getComputedStyle(el); };

    ok('启动无异常，mock 存在', !!mock);

    /* 这条必须在动任何内联 transition 之前跑：它守的是「出厂 CSS 不得把 width 纳入过渡」。
       一旦 width 参与过渡，改值后几何会停在旧值 ~150ms，标注就会量错。 */
    ok('出厂 CSS 未把 width 纳入过渡',
       cs(mock).transitionProperty.indexOf('width') === -1, cs(mock).transitionProperty);

    var ranges = d.querySelectorAll('input[type=range]').length;
    var colors = d.querySelectorAll('input[type=color]').length;
    var segs   = d.querySelectorAll('.seg[id^="i-"]').length;
    ok('控件按清单生成 7 滑块 / 1 取色 / 1 分段',
       ranges === 7 && colors === 1 && segs === 1, ranges + '/' + colors + '/' + segs);

    var chips = d.querySelector('.chips');
    var gap0 = parseFloat(cs(chips).columnGap);
    var sp = d.getElementById('i-space');
    sp.value = '30'; sp.dispatchEvent(new Event('input', {bubbles:true}));
    var gap1 = parseFloat(cs(chips).columnGap);
    ok('改间距 → 真实布局 gap 跟着变 (8→15)',
       Math.abs(gap0 - 8) < .6 && Math.abs(gap1 - 15) < .6, gap0 + '→' + gap1);

    var cta = d.querySelector('.cta');
    ok('CTA 按钮有真实高度', cta.getBoundingClientRect().height > 30,
       cta.getBoundingClientRect().height);

    /* —— 回归：改宽度后几何必须「立即」稳定 —— */
    var lay = d.querySelector('.layout');
    var w = d.getElementById('i-mockW');
    w.value = '1100'; w.dispatchEvent(new Event('input', {bubbles:true}));
    var mwWide = mock.getBoundingClientRect().width;
    ok('改宽度后几何立即生效（无过渡残留）', mwWide > 700, Math.round(mwWide));
    ok('容器查询：宽容器 → row', cs(lay).flexDirection === 'row', cs(lay).flexDirection);

    annotOn(d);
    var wide = badges(d);
    var wBadge = wide.filter(function(t){ return t.indexOf('宽') === 0; })[0];
    ok('改宽后标注立即反映新宽度', wBadge && parseInt(wBadge.replace(/\D/g,''), 10) === Math.round(mwWide),
       wBadge + ' vs ' + Math.round(mwWide));
    var hGaps = wide.filter(function(t){ return t.indexOf('↔') === 0; })
                    .map(function(t){ return parseFloat(t.replace(/[^\d.]/g,'')); });
    ok('宽布局下量到横向间距', hGaps.length >= 1, JSON.stringify(hGaps));
    annotOff(d);

    w.value = '390'; w.dispatchEvent(new Event('input', {bubbles:true}));
    var mwNarrow = mock.getBoundingClientRect().width;
    ok('容器查询：窄容器 → column', cs(lay).flexDirection === 'column', cs(lay).flexDirection);
    ok('窄容器下 mock 收窄到 390', Math.abs(mwNarrow - 390) < 2, Math.round(mwNarrow));

    /* —— 标注：真实非零间距 —— */
    annotOn(d);
    var all = badges(d);
    var vGaps = all.filter(function(t){ return t.indexOf('↕') === 0; })
                   .map(function(t){ return parseFloat(t.replace(/[^\d.]/g,'')); });
    ok('标注量出多个纵向间距', vGaps.length >= 3, JSON.stringify(vGaps));
    var sane = vGaps.every(function(n){ return n >= 1 && n <= 200; });
    ok('标注数值全部落在合理区间 1–200', sane, JSON.stringify(vGaps));
    ok('标注含内边距读数', all.some(function(t){ return t.indexOf('padding') === 0; }), JSON.stringify(all.slice(-3)));
    var blocks = d.querySelectorAll('.badge');
    ok('标注徽标不挡点击', [].every.call(blocks, function(b){ return cs(b).pointerEvents === 'none'; }));
    annotOff(d);
    ok('关标注 → 徽标清空', d.querySelectorAll('.badge').length === 0, d.querySelectorAll('.badge').length);

    /* —— 主题与配色 ——
       到这里几何断言已经全部跑完（且是在「出厂过渡设置」下跑的），
       现在才关掉过渡，让颜色读取拿到稳定值而不是动画中间值。 */
    mock.style.transition = 'none';

    var darkBtn = [].slice.call(d.querySelectorAll('#i-theme button'))
                    .filter(function(b){ return b.dataset.v === 'dark'; })[0];
    var bgVarLight = cs(mock).getPropertyValue('--bg').trim();
    darkBtn.click();
    var bgVarDark = cs(mock).getPropertyValue('--bg').trim();
    ok('暗色切换 → --bg 变量真的换', bgVarLight !== bgVarDark, bgVarLight + ' → ' + bgVarDark);
    ok('暗色下背景色实到 rgb(21,23,29)', cs(mock).backgroundColor.replace(/\s/g,'') === 'rgb(21,23,29)',
       cs(mock).backgroundColor);

    var ac = d.getElementById('i-accent'); ac.value = '#c0392b';
    ac.dispatchEvent(new Event('input', {bubbles:true}));
    ok('改主色 → 按钮背景实到 rgb(192,57,43)',
       cs(cta).backgroundColor.replace(/\s/g,'') === 'rgb(192,57,43)', cs(cta).backgroundColor);
    ok('对比度警告有内容', d.getElementById('warn').textContent.length > 5,
       d.getElementById('warn').textContent.slice(0, 30));

    var r = cta.getBoundingClientRect(), mr = mock.getBoundingClientRect();
    ok('CTA 未溢出 mock 边界', r.left >= mr.left - 1 && r.right <= mr.right + 1,
       Math.round(r.left) + '..' + Math.round(r.right) + ' vs ' + Math.round(mr.left) + '..' + Math.round(mr.right));

    /* —— 导出 —— */
    var out = d.getElementById('out');
    d.getElementById('btn-export').click();
    var j = null; try{ j = JSON.parse(out.value); }catch(e){}
    ok('导出 JSON 合法且数值是 number', !!j && typeof j.space === 'number', out.value.slice(0, 40));

    d.getElementById('btn-css').click();
    ok('导出 CSS 是 :root 块且含当前值',
       out.value.indexOf(':root {') === 0 && out.value.indexOf('--space: 30px') > -1, out.value.slice(0, 40));

    d.getElementById('btn-link').click();
    var b64 = String(out.value).split('#p=')[1];
    var back = null; try{ back = JSON.parse(decodeURIComponent(escape(atob(b64)))); }catch(e){}
    ok('链接回解无损（含中文主题与数值）',
       back && back.space === 30 && back.theme === 'dark' && back.accent === '#c0392b', JSON.stringify(back));

    ok('localStorage 可用', (function(){
      try{ localStorage.setItem('__t','1'); var v = localStorage.getItem('__t');
           localStorage.removeItem('__t'); return v === '1'; }catch(e){ return false; }
    })());

    ok('控制面板可见且有宽度', d.querySelector('.panel').getBoundingClientRect().width > 200,
       Math.round(d.querySelector('.panel').getBoundingClientRect().width));

  }catch(e){
    errs.push('EXCEPTION: ' + e.message + ' @ ' + String(e.stack || '').split('\n')[1]);
  }

  R.push('ERRORS :: ' + (errs.length ? errs.join(' ;; ') : 'none'));
  var pre = document.createElement('pre');
  pre.id = '__BROWSER_VERIFY__';
  pre.textContent = R.join('\n');
  document.body.appendChild(pre);

  function annotOn(dd){ var a = dd.getElementById('annot'); a.checked = true;
    a.dispatchEvent(new Event('change', {bubbles:true})); }
  function annotOff(dd){ var a = dd.getElementById('annot'); a.checked = false;
    a.dispatchEvent(new Event('change', {bubbles:true})); }
  function badges(dd){ return [].slice.call(dd.querySelectorAll('.badge'))
    .map(function(b){ return b.textContent; }); }
})();
</script>
"""

# 函数声明会提升，所以上面在定义之前调用 annotOn/badges 是安全的。

BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser():
    for p in BROWSER_CANDIDATES:
        if os.path.isfile(p):
            return p
    for name in ("google-chrome", "chromium", "chromium-browser", "msedge", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def main():
    target = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_TARGET
    if not target.is_file():
        print(f"找不到目标文件：{target}")
        return 2

    browser = find_browser()
    if not browser:
        print("找不到 Chromium 内核浏览器（Edge / Chrome）。跳过真实浏览器验证。")
        return 2

    html = target.read_text(encoding="utf-8")
    if "</body>" not in html:
        print("目标 HTML 里没有 </body>，无法注入探针。")
        return 2

    tmp = tempfile.mkdtemp(prefix="tuner-verify-")
    try:
        harness = pathlib.Path(tmp) / "harness.html"
        harness.write_text(html.replace("</body>", PROBE + "\n</body>"), encoding="utf-8")

        cmd = [
            browser,
            "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
            "--disable-extensions", "--disable-sync", "--mute-audio",
            f"--user-data-dir={os.path.join(tmp, 'profile')}",
            "--virtual-time-budget=5000",
            "--window-size=1600,1000",
            "--dump-dom",
            harness.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=180)
        dom = proc.stdout.decode("utf-8", errors="replace")

        m = re.search(r'<pre id="__BROWSER_VERIFY__">(.*?)</pre>', dom, re.S)
        if not m:
            print("探针没有产出结果 —— 页面可能在脚本执行前就崩了。")
            print("浏览器 stderr（截断）：")
            print(proc.stderr.decode("utf-8", errors="replace")[:1500])
            return 2

        body = m.group(1)
        for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")):
            body = body.replace(a, b)

        lines = [l.strip() for l in body.split("\n")
                 if re.match(r"^(PASS|FAIL|ERRORS) ::", l.strip())]
        passed = sum(1 for l in lines if l.startswith("PASS"))
        failed = sum(1 for l in lines if l.startswith("FAIL"))

        print(f"真实浏览器验证：{target.name}  ({os.path.basename(browser)})")
        print("-" * 62)
        for l in lines:
            if l.startswith("PASS"):
                print("  " + l)
            elif l.startswith("FAIL"):
                print("  >> " + l)
            else:
                print("  " + l)
        print("-" * 62)
        print(f"{passed} passed, {failed} failed")
        return 1 if failed else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
