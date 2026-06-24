"""Inventário de Produtos de Limpeza — quadro partilhado de casa.

Aplicação web (Flask) em português para mim e para as empregadas de limpeza
registarem o que está EM FALTA ou foi REPOSTO/COMPRADO, organizado por zonas
(Cozinha, WCs, Roupa, Louça, Geral) + uma Lista de Compras (tudo em falta).

Estado guardado no servidor (volume /data). Corre no porto 8002.
"""

import base64
import json
import os
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, Response

app = Flask(__name__)

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).with_name("data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
ITEMS_FILE = DATA_DIR / "items.json"

CATS = [
    {"key": "cozinha", "label": "Cozinha", "icone": "🍳"},
    {"key": "wc", "label": "WCs", "icone": "🚽"},
    {"key": "roupa", "label": "Roupa", "icone": "👕"},
    {"key": "louca", "label": "Louça", "icone": "🍽️"},
    {"key": "geral", "label": "Geral", "icone": "🧹"},
]
CAT_KEYS = {c["key"] for c in CATS}

# Produtos iniciais (podem ser editados/removidos na app).
SEED = [
    ("cozinha", "Mistolin desengordurante"),
    ("cozinha", "Induclean (placa de indução)"),
    ("cozinha", "Papel de cozinha"),
    ("cozinha", "Spray multiusos cozinha"),
    ("cozinha", "Sacos do lixo"),
    ("cozinha", "Esfregões"),
    ("wc", "Bloco sanitário"),
    ("wc", "Limpa-vidros"),
    ("wc", "Anti-calcário spray (Bang)"),
    ("wc", "Lixívia / desinfetante WC"),
    ("wc", "Papel higiénico"),
    ("wc", "Gel de banho / sabonete"),
    ("roupa", "Detergente máquina roupa"),
    ("roupa", "Amaciador"),
    ("roupa", "Tira-nódoas"),
    ("roupa", "Branqueador / oxi-ativo"),
    ("roupa", "Limpa-máquina (descalcificante)"),
    ("louca", "Pastilhas máquina louça"),
    ("louca", "Sal máquina louça"),
    ("louca", "Abrilhantador"),
    ("louca", "Detergente loiça à mão"),
    ("geral", "Detergente de chão"),
    ("geral", "Lixívia"),
    ("geral", "Multiusos"),
    ("geral", "Limpa-pó / spray móveis"),
    ("geral", "Álcool / desinfetante"),
    ("geral", "Luvas de limpeza"),
    ("geral", "Panos / microfibras"),
    ("geral", "Ambientador"),
]


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


def _migrate(it):
    """Garante os campos de quantidade (stock/uso) em itens antigos."""
    if "stock" not in it:
        # itens antigos tinham só 'estado': falta -> 0 em stock, tem -> 1.
        it["stock"] = 0 if it.get("estado") == "falta" else 1
    if "uso" not in it:
        it["uso"] = 0
    it.pop("estado", None)
    return it


def read_items():
    try:
        data = json.loads(ITEMS_FILE.read_text())
        if isinstance(data, list):
            return [_migrate(it) for it in data]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # primeira utilização -> semear (1 em stock, 0 em uso)
    items = [{"id": uuid.uuid4().hex[:10], "nome": n, "categoria": c,
              "stock": 1, "uso": 0, "atualizado": None, "por": None}
             for c, n in SEED]
    write_items(items)
    return items


def write_items(items):
    with tempfile.NamedTemporaryFile("w", dir=ITEMS_FILE.parent, delete=False) as tmp:
        json.dump(items, tmp, ensure_ascii=False, indent=2)
        tmp_name = tmp.name
    os.replace(tmp_name, ITEMS_FILE)


@app.route("/api/items")
def api_items():
    return jsonify(read_items())


@app.route("/api/items/add", methods=["POST"])
def api_add():
    d = request.get_json(silent=True) or request.form
    nome = (d.get("nome") or "").strip()
    cat = (d.get("categoria") or "").strip()
    if not nome or cat not in CAT_KEYS:
        return jsonify({"ok": False, "erro": "Nome e categoria válidos são obrigatórios."}), 400
    try:
        stock = max(0, int(d.get("stock", 1)))
    except (TypeError, ValueError):
        stock = 1
    items = read_items()
    items.append({"id": uuid.uuid4().hex[:10], "nome": nome, "categoria": cat,
                  "stock": stock, "uso": 0, "atualizado": _now(),
                  "por": (d.get("por") or "").strip() or None})
    write_items(items)
    return jsonify(items)


@app.route("/api/items/qty", methods=["POST"])
def api_qty():
    """Ajusta uma quantidade. campo='stock'|'uso', delta=+1/-1 (ou valor exato)."""
    d = request.get_json(silent=True) or request.form
    item_id = (d.get("id") or "").strip()
    campo = d.get("campo")
    if campo not in ("stock", "uso"):
        return jsonify({"ok": False, "erro": "campo inválido"}), 400
    por = (d.get("por") or "").strip() or None
    try:
        delta = int(d.get("delta", 0))
    except (TypeError, ValueError):
        delta = 0
    items = read_items()
    for it in items:
        if it.get("id") == item_id:
            it[campo] = max(0, int(it.get(campo, 0)) + delta)
            it["atualizado"] = _now()
            it["por"] = por
            break
    write_items(items)
    return jsonify(items)


@app.route("/api/items/delete", methods=["POST"])
def api_delete():
    d = request.get_json(silent=True) or request.form
    item_id = (d.get("id") or "").strip()
    items = [it for it in read_items() if it.get("id") != item_id]
    write_items(items)
    return jsonify(items)


@app.route("/api/items/edit", methods=["POST"])
def api_edit():
    d = request.get_json(silent=True) or request.form
    item_id = (d.get("id") or "").strip()
    nome = (d.get("nome") or "").strip()
    if not nome:
        return jsonify({"ok": False}), 400
    items = read_items()
    for it in items:
        if it.get("id") == item_id:
            it["nome"] = nome
            it["atualizado"] = _now()
            it["por"] = (d.get("por") or "").strip() or None
            break
    write_items(items)
    return jsonify(items)


@app.route("/healthz")
def healthz():
    return {"ok": True}


APPLE_ICON_PNG = base64.b64decode(
    "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")


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-180.png")
def apple_touch_icon():
    return Response(APPLE_ICON_PNG, mimetype="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


PAGE = r"""<!doctype html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Limpeza · Inventário</title>
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon-180.png">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Limpeza">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%232f6fed'/%3E%3Cpath d='M9 24l9-9 2 2-9 9zM19 11l3-3 3 3-3 3z' stroke='%23fff' stroke-width='2.4' fill='none' stroke-linecap='round'/%3E%3C/svg%3E">
  <style>
    :root {
      --bg:#eef1f6; --card:#fff; --text:#16202e; --muted:#67748a; --border:#e2e7ef;
      --shadow:0 1px 3px rgba(20,30,50,.08),0 1px 2px rgba(20,30,50,.04);
      --accent:#2f6fed; --accent-bg:#2f6fed15; --green:#1f9d57; --green-bg:#1f9d5715;
      --red:#d24b3a; --red-bg:#d24b3a16;
    }
    @media (prefers-color-scheme: dark) {
      :root { --bg:#0e131b; --card:#19212c; --text:#e8eef6; --muted:#90a0b6; --border:#28323f;
        --shadow:0 1px 2px rgba(0,0,0,.4); --accent:#5b95ff; --accent-bg:#5b95ff1f; --green:#34c884;
        --green-bg:#34c8841f; --red:#ef6a59; --red-bg:#ef6a591f; }
    }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); line-height:1.5;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
    .wrap { max-width:820px; margin:0 auto; padding:1.1rem 1rem 3rem; }
    header { display:flex; align-items:center; justify-content:space-between; gap:.6rem; flex-wrap:wrap; }
    header h1 { margin:.1rem 0; font-size:1.4rem; }
    .me { display:flex; align-items:center; gap:.35rem; font-size:.82rem; color:var(--muted); }
    .me input, .me select { padding:.4rem .5rem; border-radius:8px; border:1px solid var(--border);
      background:var(--card); color:var(--text); font-weight:700; font-size:.9rem; }
    .modal { position:fixed; inset:0; z-index:100; display:flex; align-items:center; justify-content:center;
      background:rgba(10,15,25,.45); backdrop-filter:blur(7px); -webkit-backdrop-filter:blur(7px); padding:1rem; }
    .modalbox { background:var(--card); border:1px solid var(--border); border-radius:18px; padding:1.4rem 1.4rem 1.2rem;
      box-shadow:0 20px 60px rgba(0,0,0,.4); width:100%; max-width:340px; text-align:center; }
    .modaltitle { font-size:1.3rem; font-weight:800; margin-bottom:1rem; }
    .people { display:flex; flex-direction:column; gap:.5rem; margin-bottom:1rem; }
    .person { padding:.7rem; border-radius:12px; border:1px solid var(--border); background:var(--bg);
      color:var(--text); font-size:1.05rem; font-weight:700; cursor:pointer; }
    .person.sel { background:var(--accent); color:#fff; border-color:var(--accent); }
    .modalbox .btn { width:100%; padding:.7rem; font-size:1.05rem; }
    .btn:disabled { opacity:.5; cursor:default; }
    .tabs { display:flex; gap:.4rem; flex-wrap:wrap; margin:.8rem 0; position:sticky; top:0;
      background:var(--bg); padding:.5rem 0; z-index:5; }
    .tab { font-size:.9rem; font-weight:700; padding:.5rem .8rem; border-radius:999px; cursor:grab;
      border:1px solid var(--border); background:var(--card); color:var(--muted); display:flex; gap:.35rem;
      align-items:center; touch-action:none; user-select:none; -webkit-user-select:none; }
    .tab.on { background:var(--accent); color:#fff; border-color:var(--accent); }
    .tab.dragging { opacity:.55; cursor:grabbing; }
    .grip { opacity:.4; margin-right:.1rem; font-size:.95em; letter-spacing:-2px; }
    .tab.on .grip { opacity:.75; }
    .badge { font-size:.72rem; font-weight:800; min-width:18px; text-align:center; padding:0 .3rem;
      border-radius:999px; background:var(--red); color:#fff; }
    .tab.on .badge { background:#fff; color:var(--red); }
    .hgroup { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; }
    .cart { display:flex; align-items:center; gap:.4rem; padding:.5rem .8rem; border-radius:999px;
      border:1px solid var(--green); background:var(--green); color:#fff; font-weight:800; cursor:pointer; font-size:.9rem; }
    .cart .badge { background:#fff; color:var(--green); }
    .editinput { font-size:1rem; font-weight:700; padding:.25rem .4rem; border-radius:8px; min-width:160px;
      border:1px solid var(--accent); background:var(--bg); color:var(--text); }
    .search { width:100%; padding:.65rem .85rem; font-size:1rem; border-radius:12px;
      border:1px solid var(--border); background:var(--card); color:var(--text); box-shadow:var(--shadow);
      margin-bottom:.9rem; }
    .addbar { display:flex; gap:.5rem; margin-bottom:1rem; }
    .addbar input { flex:1; padding:.6rem .8rem; font-size:1rem; border-radius:10px;
      border:1px solid var(--border); background:var(--card); color:var(--text); }
    .btn { padding:.6rem .9rem; border-radius:10px; border:1px solid var(--accent); background:var(--accent);
      color:#fff; font-weight:700; cursor:pointer; font-size:.92rem; white-space:nowrap; }
    .item { display:flex; align-items:center; gap:.7rem; flex-wrap:wrap; background:var(--card);
      border:1px solid var(--border); border-radius:12px; box-shadow:var(--shadow);
      padding:.6rem .8rem; margin-bottom:.5rem; }
    .item.falta { border-color:var(--red); background:var(--red-bg); }
    .item .info { flex:1; min-width:150px; }
    .steppers { display:flex; gap:.7rem; flex-wrap:wrap; }
    .stp { display:flex; align-items:center; gap:.25rem; }
    .stp .lbl { font-size:.7rem; color:var(--muted); font-weight:700; margin-right:.1rem; }
    .sb { width:30px; height:30px; border-radius:8px; border:1px solid var(--border); background:var(--card);
      color:var(--text); font-size:1.15rem; line-height:1; cursor:pointer; font-weight:700; }
    .sb:hover { border-color:var(--accent); color:var(--accent); }
    .num { min-width:22px; text-align:center; font-weight:800; }
    .num.zero { color:var(--red); }
    .item .nome { font-weight:700; cursor:text; border-radius:6px; padding:.05rem .2rem; }
    .item .nome:hover { background:rgba(127,127,127,.12); }
    .item .meta { font-size:.76rem; color:var(--muted); }
    .pill { font-size:.74rem; font-weight:800; padding:.12rem .55rem; border-radius:999px; }
    .pill.tem { color:var(--green); background:var(--green-bg); border:1px solid var(--green); }
    .pill.falta { color:var(--red); background:var(--red-bg); border:1px solid var(--red); }
    .act { padding:.5rem .7rem; border-radius:10px; cursor:pointer; font-weight:700; font-size:.84rem;
      border:1px solid var(--border); background:var(--card); color:var(--text); white-space:nowrap; }
    .act.falta { border-color:var(--red); color:var(--red); }
    .act.repor { border-color:var(--green); color:#fff; background:var(--green); }
    .x { border:none; background:none; color:var(--muted); cursor:pointer; font-size:1.1rem; padding:.2rem .3rem; }
    .x:hover { color:var(--red); }
    .grouptitle { font-size:.82rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em;
      margin:1rem 0 .5rem; font-weight:700; }
    .empty { color:var(--muted); padding:1.2rem; text-align:center; }
    .hide { display:none; }
    footer { margin-top:2rem; text-align:center; color:var(--muted); font-size:.8rem; }
  </style>
</head>
<body>
<div id="whois" class="modal hide">
  <div class="modalbox">
    <div class="modaltitle">👋 Quem és?</div>
    <div class="people" id="people"></div>
    <button id="whoisok" class="btn" disabled>OK</button>
  </div>
</div>
<div class="wrap">
  <header>
    <h1>🧽 Inventário de Limpeza</h1>
    <div class="hgroup">
      <button id="cartbtn" class="cart">🛒 A comprar <span class="badge" id="cartn">0</span></button>
      <label class="me">👤 <select id="me"></select></label>
    </div>
  </header>

  <div class="tabs" id="tabs">
    {% for c in cats %}
    <div class="tab{% if loop.first %} on{% endif %}" data-tab="{{ c.key }}">
      {{ c.icone }} {{ c.label }} <span class="badge hide" id="b-{{ c.key }}"></span>
    </div>
    {% endfor %}
  </div>

  <input id="q" class="search" type="search" autocomplete="off" placeholder="🔎 Pesquisar produto…">

  <div class="addbar" id="addbar">
    <input id="novo" placeholder="Adicionar produto a esta zona…" autocomplete="off">
    <button class="btn" id="add">＋ Adicionar</button>
  </div>

  <div id="list"></div>

  <footer>Marca <b>Em falta</b> quando algo acaba e <b>Comprei/Repor</b> quando se repõe.<br>
    Atualiza automaticamente. Inventário partilhado de casa.</footer>
</div>

<script>
  const $ = id => document.getElementById(id);
  const fold = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const CATS = {{ cats_json|safe }};
  const LABELS = Object.fromEntries(CATS.map(c => [c.key, c.icone + ' ' + c.label]));
  let items = [], tab = CATS[0].key, mode = 'cat', paused = false;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const PEOPLE = ['Rafael', 'Mariana', 'Cecília', 'Samara'];
  let me = localStorage.getItem('cln_pessoa') || '';
  const sel = $('me');
  sel.innerHTML = PEOPLE.map(p => `<option>${p}</option>`).join('');
  sel.value = me || PEOPLE[0];
  sel.addEventListener('change', () => { me = sel.value; localStorage.setItem('cln_pessoa', me); });
  // pop-up "Quem és?" — escolha guardada no dispositivo (localStorage; funciona atrás do Cloudflare)
  (function () {
    const box = $('people'); let chosen = '';
    box.innerHTML = PEOPLE.map(p => `<button class="person" data-p="${p}">${p}</button>`).join('');
    box.querySelectorAll('.person').forEach(b => b.onclick = () => {
      chosen = b.dataset.p;
      box.querySelectorAll('.person').forEach(x => x.classList.toggle('sel', x === b));
      $('whoisok').disabled = false;
    });
    $('whoisok').onclick = () => {
      if (!chosen) return;
      me = chosen; localStorage.setItem('cln_pessoa', me); sel.value = me; $('whois').classList.add('hide');
    };
    if (!me) $('whois').classList.remove('hide');
  })();

  function rel(iso) {
    if (!iso) return '';
    const d = (Date.now() - new Date(iso)) / 1000;
    if (d < 60) return 'agora'; if (d < 3600) return 'há ' + Math.floor(d / 60) + ' min';
    if (d < 86400) return 'há ' + Math.floor(d / 3600) + ' h'; return 'há ' + Math.floor(d / 86400) + ' dias';
  }
  function meta(it) {
    const parts = [];
    if (it.atualizado) parts.push(rel(it.atualizado));
    if (it.por) parts.push('por ' + it.por);
    return parts.join(' · ');
  }
  async function api(path, body) {
    paused = true;
    try { const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      items = await r.json(); } finally { paused = false; }
    render();
  }
  const load = () => { if (paused) return; fetch('/api/items').then(r => r.json()).then(d => { items = d; render(); }); };
  function startEdit(span, id) {
    const cur = span.textContent;
    const inp = document.createElement('input'); inp.className = 'editinput'; inp.value = cur;
    span.replaceWith(inp); inp.focus(); inp.select(); paused = true;
    let done = false;
    const finish = save => { if (done) return; done = true; paused = false;
      const v = inp.value.trim();
      if (save && v && v !== cur) api('/api/items/edit', { id, nome: v, por: me }); else render(); };
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); finish(true); } else if (e.key === 'Escape') finish(false); });
    inp.addEventListener('blur', () => finish(true));
  }

  const isFalta = it => (it.stock || 0) === 0;
  function stepper(id, campo, label, val) {
    return `<div class="stp"><span class="lbl">${label}</span>
      <button class="sb" data-q="${id}|${campo}|-1">−</button>
      <span class="num ${campo === 'stock' && val === 0 ? 'zero' : ''}">${val}</span>
      <button class="sb" data-q="${id}|${campo}|1">+</button></div>`;
  }
  function row(it) {
    const falta = isFalta(it);
    return `<div class="item ${falta ? 'falta' : ''}">
      <div class="info"><div><span class="nome" data-edit="${it.id}">${esc(it.nome)}</span>${falta ? ' <span class="pill falta">EM FALTA</span>' : ''}</div>
        <div class="meta">${meta(it)}</div></div>
      <div class="steppers">${stepper(it.id, 'stock', 'Stock', it.stock || 0)}${stepper(it.id, 'uso', 'Em uso', it.uso || 0)}</div>
      <button class="x" data-del="${it.id}" title="remover">✕</button></div>`;
  }
  function rowCompra(it) {
    return `<div class="item falta">
      <div class="info"><div class="nome">${esc(it.nome)}</div>
        <div class="meta">em uso: ${it.uso || 0}${meta(it) ? ' · ' + meta(it) : ''}</div></div>
      <button class="act repor" data-buy="${it.id}">✓ Comprei (+1)</button>
      <button class="x" data-del="${it.id}" title="remover">✕</button></div>`;
  }
  function render() {
    let total = 0;
    CATS.forEach(c => {
      const n = items.filter(i => i.categoria === c.key && isFalta(i)).length;
      const b = $('b-' + c.key); b.textContent = n; b.classList.toggle('hide', n === 0); total += n;
    });
    $('cartn').textContent = total;
    document.querySelectorAll('#tabs .tab').forEach(t => t.classList.toggle('on', t.dataset.tab === tab && mode === 'cat'));

    const term = fold($('q').value.trim());
    const box = $('list');
    $('addbar').classList.toggle('hide', mode === 'lista');
    $('tabs').classList.toggle('hide', mode === 'lista');

    if (mode === 'lista') {
      const falta = items.filter(i => isFalta(i) && (!term || fold(i.nome).includes(term)));
      if (!falta.length) box.innerHTML = '<div class="empty">🎉 Nada em falta. Tudo com stock!</div>';
      else box.innerHTML = CATS.map(c => {
        const sub = falta.filter(i => i.categoria === c.key);
        return sub.length ? `<div class="grouptitle">${LABELS[c.key]}</div>` + sub.map(rowCompra).join('') : '';
      }).join('');
    } else {
      let list = items.filter(i => i.categoria === tab && (!term || fold(i.nome).includes(term)));
      list.sort((a, b) => (isFalta(b) - isFalta(a)) || a.nome.localeCompare(b.nome, 'pt'));
      box.innerHTML = list.length ? list.map(row).join('')
        : '<div class="empty">Sem produtos nesta zona. Adiciona acima. 👆</div>';
    }
    box.querySelectorAll('[data-q]').forEach(b => b.onclick = () => {
      const [id, campo, delta] = b.dataset.q.split('|');
      api('/api/items/qty', { id, campo, delta: Number(delta), por: me });
    });
    box.querySelectorAll('[data-buy]').forEach(b => b.onclick = () =>
      api('/api/items/qty', { id: b.dataset.buy, campo: 'stock', delta: 1, por: me }));
    box.querySelectorAll('[data-del]').forEach(b => b.onclick = () => api('/api/items/delete', { id: b.dataset.del }));
    box.querySelectorAll('.nome[data-edit]').forEach(s => s.onclick = () => startEdit(s, s.dataset.edit));
  }

  document.querySelectorAll('#tabs .tab[data-tab]').forEach(t => t.addEventListener('click', () => { tab = t.dataset.tab; mode = 'cat'; render(); }));
  $('cartbtn').onclick = () => { mode = mode === 'lista' ? 'cat' : 'lista'; render(); };
  $('q').addEventListener('input', render);
  function addNovo() {
    const nome = $('novo').value.trim(); if (!nome || mode === 'lista') return;
    $('novo').value = '';
    api('/api/items/add', { nome, categoria: tab, por: me });
  }
  $('add').addEventListener('click', addNovo);
  $('novo').addEventListener('keydown', e => { if (e.key === 'Enter') addNovo(); });

  // Arrastar para reordenar as tabs (guardado por dispositivo)
  function makeSortable(container, key, attr) {
    try {
      const saved = JSON.parse(localStorage.getItem(key) || '[]');
      saved.forEach(k => { const el = container.querySelector('[' + attr + '="' + k + '"]'); if (el) container.appendChild(el); });
    } catch (e) {}
    const save = () => localStorage.setItem(key,
      JSON.stringify([...container.querySelectorAll('[' + attr + ']')].map(e => e.getAttribute(attr))));
    container.querySelectorAll('[' + attr + ']').forEach(el => {
      el.insertAdjacentHTML('afterbegin', '<span class="grip" aria-hidden="true">⠿</span>');
      el.addEventListener('pointerdown', e => {
        if (e.button) return;
        const sx = e.clientX, sy = e.clientY; let moved = false;
        const move = ev => {
          if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 8) return;
          if (!moved) { moved = true; el.classList.add('dragging'); try { el.setPointerCapture(ev.pointerId); } catch (_) {} }
          ev.preventDefault();
          let best = null, bd = Infinity;
          container.querySelectorAll('[' + attr + ']:not(.dragging)').forEach(o => {
            const r = o.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
            const d = Math.hypot(ev.clientX - cx, ev.clientY - cy);
            if (d < bd) { bd = d; best = { o, cx }; }
          });
          if (best) container.insertBefore(el, ev.clientX < best.cx ? best.o : best.o.nextSibling);
        };
        const up = () => {
          document.removeEventListener('pointermove', move);
          document.removeEventListener('pointerup', up);
          if (moved) {
            el.classList.remove('dragging'); save();
            const swallow = c => { c.stopPropagation(); c.preventDefault(); };
            el.addEventListener('click', swallow, { capture: true, once: true });
            setTimeout(() => el.removeEventListener('click', swallow, true), 50);
          }
        };
        document.addEventListener('pointermove', move);
        document.addEventListener('pointerup', up);
      });
    });
  }
  makeSortable($('tabs'), 'cln_taborder', 'data-tab');

  load();
  setInterval(load, 15000);  // mantém o quadro atualizado entre dispositivos
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(PAGE, cats=CATS, cats_json=json.dumps(CATS, ensure_ascii=False))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)
