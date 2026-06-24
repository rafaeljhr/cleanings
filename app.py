"""Inventário de Produtos de Limpeza — quadro partilhado de casa.

Aplicação web (Flask) em português para mim e para as empregadas de limpeza
registarem o que está EM FALTA ou foi REPOSTO/COMPRADO, organizado por zonas
(Cozinha, WCs, Roupa, Louça, Geral) + uma Lista de Compras (tudo em falta).

Estado guardado no servidor (volume /data). Corre no porto 8002.
"""

import json
import os
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

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


def read_items():
    try:
        data = json.loads(ITEMS_FILE.read_text())
        if isinstance(data, list):
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # primeira utilização -> semear
    items = [{"id": uuid.uuid4().hex[:10], "nome": n, "categoria": c,
              "estado": "tem", "atualizado": None, "por": None}
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
    estado = "falta" if (d.get("estado") == "falta") else "tem"
    items = read_items()
    items.append({"id": uuid.uuid4().hex[:10], "nome": nome, "categoria": cat,
                  "estado": estado, "atualizado": _now(), "por": (d.get("por") or "").strip() or None})
    write_items(items)
    return jsonify(items)


@app.route("/api/items/toggle", methods=["POST"])
def api_toggle():
    d = request.get_json(silent=True) or request.form
    item_id = (d.get("id") or "").strip()
    por = (d.get("por") or "").strip() or None
    items = read_items()
    for it in items:
        if it.get("id") == item_id:
            it["estado"] = "tem" if it.get("estado") == "falta" else "falta"
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


@app.route("/healthz")
def healthz():
    return {"ok": True}


PAGE = r"""<!doctype html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Limpeza · Inventário</title>
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
    .me input { padding:.35rem .5rem; border-radius:8px; border:1px solid var(--border);
      background:var(--card); color:var(--text); width:110px; }
    .tabs { display:flex; gap:.4rem; flex-wrap:wrap; margin:.8rem 0; position:sticky; top:0;
      background:var(--bg); padding:.5rem 0; z-index:5; }
    .tab { font-size:.9rem; font-weight:700; padding:.5rem .8rem; border-radius:999px; cursor:pointer;
      border:1px solid var(--border); background:var(--card); color:var(--muted); display:flex; gap:.35rem;
      align-items:center; }
    .tab.on { background:var(--accent); color:#fff; border-color:var(--accent); }
    .badge { font-size:.72rem; font-weight:800; min-width:18px; text-align:center; padding:0 .3rem;
      border-radius:999px; background:var(--red); color:#fff; }
    .tab.on .badge { background:#fff; color:var(--red); }
    .search { width:100%; padding:.65rem .85rem; font-size:1rem; border-radius:12px;
      border:1px solid var(--border); background:var(--card); color:var(--text); box-shadow:var(--shadow);
      margin-bottom:.9rem; }
    .addbar { display:flex; gap:.5rem; margin-bottom:1rem; }
    .addbar input { flex:1; padding:.6rem .8rem; font-size:1rem; border-radius:10px;
      border:1px solid var(--border); background:var(--card); color:var(--text); }
    .btn { padding:.6rem .9rem; border-radius:10px; border:1px solid var(--accent); background:var(--accent);
      color:#fff; font-weight:700; cursor:pointer; font-size:.92rem; white-space:nowrap; }
    .item { display:flex; align-items:center; gap:.7rem; background:var(--card); border:1px solid var(--border);
      border-radius:12px; box-shadow:var(--shadow); padding:.6rem .8rem; margin-bottom:.5rem; }
    .item.falta { border-color:var(--red); background:var(--red-bg); }
    .item .info { flex:1; min-width:0; }
    .item .nome { font-weight:700; }
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
<div class="wrap">
  <header>
    <h1>🧽 Inventário de Limpeza</h1>
    <label class="me">Sou: <input id="me" placeholder="o teu nome" autocomplete="off"></label>
  </header>

  <div class="tabs" id="tabs">
    {% for c in cats %}
    <div class="tab{% if loop.first %} on{% endif %}" data-tab="{{ c.key }}">
      {{ c.icone }} {{ c.label }} <span class="badge hide" id="b-{{ c.key }}"></span>
    </div>
    {% endfor %}
    <div class="tab" data-tab="compras">🛒 Compras <span class="badge hide" id="b-compras"></span></div>
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
  let items = [], tab = CATS[0].key;
  let me = localStorage.getItem('cln_me') || '';
  $('me').value = me;
  $('me').addEventListener('input', () => { me = $('me').value.trim(); localStorage.setItem('cln_me', me); });

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
    const opt = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    const r = await fetch(path, body ? opt : undefined);
    items = await r.json(); render();
  }
  const load = () => fetch('/api/items').then(r => r.json()).then(d => { items = d; render(); });

  function row(it) {
    const falta = it.estado === 'falta';
    return `<div class="item ${falta ? 'falta' : ''}">
      <span class="pill ${falta ? 'falta' : 'tem'}">${falta ? 'EM FALTA' : 'Tem'}</span>
      <div class="info"><div class="nome">${it.nome}</div><div class="meta">${meta(it)}</div></div>
      <button class="act ${falta ? 'repor' : 'falta'}" data-tg="${it.id}">${falta ? '✓ Comprei' : 'Em falta'}</button>
      <button class="x" data-del="${it.id}" title="remover">✕</button></div>`;
  }
  function render() {
    // badges (em falta por zona + total)
    let total = 0;
    CATS.forEach(c => {
      const n = items.filter(i => i.categoria === c.key && i.estado === 'falta').length;
      const b = $('b-' + c.key); b.textContent = n; b.classList.toggle('hide', n === 0); total += n;
    });
    const bc = $('b-compras'); bc.textContent = total; bc.classList.toggle('hide', total === 0);
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.dataset.tab === tab));

    const term = fold($('q').value.trim());
    const box = $('list');
    $('addbar').classList.toggle('hide', tab === 'compras');

    if (tab === 'compras') {
      const falta = items.filter(i => i.estado === 'falta' && (!term || fold(i.nome).includes(term)));
      if (!falta.length) { box.innerHTML = '<div class="empty">🎉 Nada em falta. Tudo reposto!</div>'; return; }
      box.innerHTML = CATS.map(c => {
        const sub = falta.filter(i => i.categoria === c.key);
        if (!sub.length) return '';
        return `<div class="grouptitle">${LABELS[c.key]}</div>` + sub.map(row).join('');
      }).join('');
    } else {
      let list = items.filter(i => i.categoria === tab && (!term || fold(i.nome).includes(term)));
      list.sort((a, b) => (a.estado === b.estado ? 0 : a.estado === 'falta' ? -1 : 1)
        || a.nome.localeCompare(b.nome, 'pt'));
      box.innerHTML = list.length ? list.map(row).join('')
        : '<div class="empty">Sem produtos nesta zona. Adiciona acima. 👆</div>';
    }
    box.querySelectorAll('[data-tg]').forEach(b => b.onclick = () => api('/api/items/toggle', { id: b.dataset.tg, por: me }));
    box.querySelectorAll('[data-del]').forEach(b => b.onclick = () => api('/api/items/delete', { id: b.dataset.del }));
  }

  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => { tab = t.dataset.tab; render(); }));
  $('q').addEventListener('input', render);
  function addNovo() {
    const nome = $('novo').value.trim(); if (!nome || tab === 'compras') return;
    $('novo').value = '';
    api('/api/items/add', { nome, categoria: tab, por: me });
  }
  $('add').addEventListener('click', addNovo);
  $('novo').addEventListener('keydown', e => { if (e.key === 'Enter') addNovo(); });

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
