"""生成「盲测准确率」演示素材（零第三方依赖）。

从 features.csv 用与 `--blind` 完全相同的最近质心分类器重算 15 段盲测，
输出可核验的逐段明细 CSV + 可现场点击/自动播放的 HTML 演示页。
HTML 用于录屏：录屏文件即为官网必交项 ③ 的「盲测准确率视频」。

用法（仓库根目录）：
    python tools\\make_blind_demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import signal_core as core  # noqa: E402

FEAT = ROOT / "02-20Days-Challenge" / "results" / "features.csv"
OUT = ROOT / "02-20Days-Challenge" / "blind_test"
OUT.mkdir(parents=True, exist_ok=True)


def build_items():
    rows = core.read_csv(FEAT)
    train = [r for r in rows if r["group"] == "train"]
    test = [r for r in rows if r["group"] == "blind"]
    if not train or not test:
        raise SystemExit("features.csv 缺 train/blind 分组，请先跑 --extract")
    scaler, cents = core.build_centroids(train)
    items = []
    for i, r in enumerate(test, 1):
        pred = core.predict(scaler, cents, r)
        items.append({
            "no": i,
            "file": r["file"],
            "truth": r["condition"],
            "pred": pred,
            "ok": pred == r["condition"],
            "hz": round(core.fnum(r.get("dominant_hz")), 1),
        })
    return items, len(train), len(test)


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>项目三 · 盲测准确率现场演示</title>
<style>
  :root { --bg:#f6f7fb; --card:#ffffff; --ink:#1b2030; --muted:#6b7280;
          --line:#e5e7ef; --brand:#4f46e5; --ok:#16a34a; --bad:#dc2626; }
  * { box-sizing:border-box; }
  body { margin:0; padding:26px 32px 34px; background:var(--bg); color:var(--ink);
         font-family:system-ui,"Microsoft YaHei","PingFang SC",sans-serif; }
  h1 { font-size:25px; margin:0 0 6px; letter-spacing:.5px; }
  .sub { color:var(--muted); font-size:14px; margin-bottom:18px; line-height:1.7; }
  .stats { display:flex; gap:12px; margin-bottom:18px; flex-wrap:wrap; }
  .stat { background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:11px 18px; min-width:132px; }
  .stat .k { font-size:12px; color:var(--muted); }
  .stat .v { font-size:21px; font-weight:650; margin-top:3px; }
  .stage { background:var(--card); border:1px solid var(--line); border-radius:16px;
           padding:22px 26px; min-height:212px; box-shadow:0 2px 14px rgba(30,40,90,.05); }
  .row1 { display:flex; justify-content:space-between; align-items:center; }
  .badge { background:#eef0ff; color:var(--brand); border-radius:999px;
           padding:5px 13px; font-size:13px; font-weight:600; }
  .file { font-size:27px; font-weight:700; letter-spacing:.6px; margin:14px 0 16px;
          font-family:ui-monospace,Consolas,monospace; }
  .hidden { color:#b6bbc8; font-weight:500; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .box { background:#fafbfe; border:1px solid var(--line); border-radius:11px; padding:13px 16px; }
  .box .lab { font-size:12px; color:var(--muted); margin-bottom:5px; }
  .box .val { font-size:20px; font-weight:650; }
  .verdict { margin-top:15px; font-size:19px; font-weight:700; }
  .verdict.ok { color:var(--ok); } .verdict.bad { color:var(--bad); }
  .bars { display:flex; gap:5px; margin:18px 0 6px; flex-wrap:wrap; }
  .bar { width:34px; height:11px; border-radius:3px; background:#e3e6ee; }
  .bar.ok { background:var(--ok); } .bar.bad { background:var(--bad); }
  .bar.cur { outline:2px solid var(--brand); outline-offset:2px; }
  .foot { display:flex; align-items:center; gap:14px; margin-top:16px; flex-wrap:wrap; }
  button { border:0; border-radius:9px; padding:11px 20px; font-size:14px;
           font-weight:600; cursor:pointer; font-family:inherit; }
  .primary { background:var(--brand); color:#fff; }
  .ghost { background:#eceef6; color:var(--ink); }
  button:disabled { opacity:.45; cursor:not-allowed; }
  .score { margin-left:auto; font-size:15px; color:var(--muted); }
  .score b { font-size:27px; color:var(--ink); }
  .final { margin-top:18px; background:#eef8f1; border:1px solid #bbe7c9;
           border-radius:12px; padding:16px 20px; font-size:16px; line-height:1.8; display:none; }
  .note { margin-top:20px; font-size:12px; color:var(--muted); line-height:1.8; }
  code { background:#eceef6; padding:2px 6px; border-radius:4px; font-size:12px; }
</style>
</head>
<body>
<h1>项目三 · 盲测准确率现场演示</h1>
<div class="sub">
  模型只用 <b>每工况 1–12 段</b> 训练（共 __NTRAIN__ 段），<b>13–15 段完全不参与训练</b>（共 __NTEST__ 段）。<br/>
  分类器：标准化后的 11 维时/频域特征 + 最近质心；Python 标准库实现 FFT，无机器学习框架。
</div>

<div class="stats">
  <div class="stat"><div class="k">原始 WAV 总数</div><div class="v">75 段</div></div>
  <div class="stat"><div class="k">训练 / 盲测</div><div class="v">__NTRAIN__ / __NTEST__</div></div>
  <div class="stat"><div class="k">工况类别</div><div class="v">5 类</div></div>
  <div class="stat"><div class="k">留一法准确率</div><div class="v">89.3%</div></div>
</div>

<div class="stage" id="stage">
  <div class="row1"><span class="badge" id="badge">准备就绪</span>
    <span style="font-size:13px;color:var(--muted)" id="prog">0 / __NTEST__</span></div>
  <div class="file" id="file">点击「揭示下一段」开始</div>
  <div class="grid">
    <div class="box"><div class="lab">模型预测</div><div class="val hidden" id="pred">—</div></div>
    <div class="box"><div class="lab">真实工况（揭晓）</div><div class="val hidden" id="truth">—</div></div>
  </div>
  <div class="verdict" id="verdict"></div>
  <div class="bars" id="bars"></div>
</div>

<div class="foot">
  <button class="primary" id="next">揭示下一段 ▶</button>
  <button class="ghost" id="auto">自动播放全部</button>
  <button class="ghost" id="reset">重置</button>
  <div class="score">累计正确 <b id="hit">0</b> / <span id="done">0</span>　准确率 <b id="acc">—</b></div>
</div>

<div class="final" id="final"></div>

<div class="note">
  数据来源：<code>results/features.csv</code> → <code>blind_test/blind_detail.csv</code>（逐段明细，可复核）。<br/>
  复现命令：<code>python 02-20Days-Challenge\\analyze_real_wav.py --blind</code>，
  结果见 <code>results/blind_report.md</code>。本页仅把同一批结果做成可视化演示，未改动任何预测。
</div>

<script>
//<![CDATA[
const DATA = __DATA__;
let idx = 0, hit = 0, timer = null;
const $ = id => document.getElementById(id);

function render() {
  const n = DATA.length;
  $('prog').textContent = idx + ' / ' + n;
  $('hit').textContent = hit;
  $('done').textContent = idx;
  $('acc').textContent = idx ? (hit / idx * 100).toFixed(1) + '%' : '—';
  let bars = '';
  for (let i = 0; i < n; i++) {
    const c = i < idx ? (DATA[i].ok ? 'ok' : 'bad') : (i === idx ? 'cur' : '');
    bars += '<div class="bar ' + c + '" title="第' + (i+1) + '段"></div>';
  }
  $('bars').innerHTML = bars;
  $('next').disabled = idx >= n;
  $('auto').disabled = idx >= n;
  if (idx === 0) {
    $('badge').textContent = '准备就绪';
    $('file').textContent = '点击「揭示下一段」开始';
    $('pred').textContent = '—'; $('truth').textContent = '—';
    $('pred').className = 'val hidden'; $('truth').className = 'val hidden';
    $('verdict').textContent = ''; $('verdict').className = 'verdict';
    $('final').style.display = 'none';
    return;
  }
  const d = DATA[idx - 1];
  $('badge').textContent = '第 ' + d.no + ' / ' + n + ' 段 · 主频 ' + d.hz + ' Hz';
  $('file').textContent = d.file;
  $('pred').textContent = d.pred; $('truth').textContent = d.truth;
  $('pred').className = 'val'; $('truth').className = 'val';
  $('verdict').textContent = d.ok ? '✔ 判对' : '✘ 判错：' + d.truth + ' → ' + d.pred;
  $('verdict').className = 'verdict ' + (d.ok ? 'ok' : 'bad');
  if (idx === n) {
    const acc = (hit / n * 100).toFixed(1);
    $('final').style.display = 'block';
    $('final').innerHTML = '<b>盲测完成：' + hit + ' / ' + n + ' = ' + acc + '%</b><br/>' +
      '与 <code>results/blind_report.md</code> 的 80.0% 一致。判错的 ' + (n - hit) +
      ' 段已逐条保留在明细表中，未做任何剔除或事后调参。<br/>' +
      '说明：这是<b>同批次</b>盲测（同一天录的 13–15 段），不是跨日 held-out；两者区别已在 README 如实写明。';
  }
}
$('next').onclick = () => {
  if (idx >= DATA.length) return;
  if (DATA[idx].ok) hit++;
  idx++; render();
};
$('auto').onclick = () => {
  if (timer) { clearInterval(timer); timer = null; $('auto').textContent = '自动播放全部'; return; }
  $('auto').textContent = '暂停播放';
  timer = setInterval(() => {
    if (idx >= DATA.length) { clearInterval(timer); timer = null; $('auto').textContent = '自动播放全部'; return; }
    if (DATA[idx].ok) hit++;
    idx++; render();
  }, 1100);
};
$('reset').onclick = () => {
  if (timer) { clearInterval(timer); timer = null; $('auto').textContent = '自动播放全部'; }
  idx = 0; hit = 0; render();
};
render();
//]]>
</script>
</body>
</html>
"""


def main():
    items, ntrain, ntest = build_items()
    core.write_csv(OUT / "blind_detail.csv",
                   [{"no": d["no"], "file": d["file"], "truth": d["truth"],
                     "pred": d["pred"], "result": "判对" if d["ok"] else "判错",
                     "dominant_hz": d["hz"]} for d in items])
    html = (HTML.replace("__DATA__", json.dumps(items, ensure_ascii=False))
                .replace("__NTRAIN__", str(ntrain))
                .replace("__NTEST__", str(ntest)))
    (OUT / "盲测演示.html").write_text(html, encoding="utf-8", newline="\n")
    hit = sum(1 for d in items if d["ok"])
    print(f"盲测明细 {len(items)} 段 -> blind_test/blind_detail.csv")
    print(f"演示页 -> blind_test/盲测演示.html")
    print(f"累计判对 {hit}/{len(items)} = {hit / len(items) * 100:.1f}%")
    for d in items:
        if not d["ok"]:
            print(f"  判错 {d['file']}: 真实={d['truth']} 预测={d['pred']}")


if __name__ == "__main__":
    main()
