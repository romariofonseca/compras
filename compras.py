# -*- coding: utf-8 -*-
"""
Foto → Onde comprar • Flask
UI com caixa única + câmera + carrossel (1 mapa alternando 3 rotas) + miniatura automática

Recursos:
- Botões do carrossel destacados (texto + setas, tooltip, animação sutil, atalhos ← →).
- "🛒 Onde comprar" lista as MESMAS 3 lojas do mapa (site oficial se houver, senão Google Maps).
- "Outras opções online" fica separada e some para intenções de serviço (ex.: mecânico, cabeleireiro).
- Geolocalização automática ao carregar; sem campo de endereço.
- Intenções para beauty (cabeleireiro/barbearia) e auto_service (mecânico).
- Bloqueio para itens/consultas proibidas (drogas ilícitas) com mensagem de aviso.

Observação: chaves padrão seguem como no código original; em produção use variáveis de ambiente.
"""

import os, io, base64, json, re, math, unicodedata
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import quote_plus

import requests
from flask import Flask, request, render_template_string
from PIL import Image

# === CHAVES (como no seu código; em produção, use variáveis de ambiente) ===
OPENAI_FALLBACK_KEY = ""
SERPAPI_FALLBACK_KEY = ""

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", OPENAI_FALLBACK_KEY).strip()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", SERPAPI_FALLBACK_KEY).strip()
BING_SEARCH_KEY = os.getenv("BING_SEARCH_KEY", "").strip()

SERPAPI_GOOGLE_DOMAIN = os.getenv("SERPAPI_GOOGLE_DOMAIN", "google.com.br").strip() or "google.com.br"
SERPAPI_HL = os.getenv("SERPAPI_HL", "pt-BR").strip() or "pt-BR"

PORT = int(os.getenv("PORT", "11001"))
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

NOMINATIM_EMAIL = os.getenv("NOMINATIM_EMAIL", "").strip()
NOMINATIM_HEADERS = {
    "User-Agent": "foto-onde-comprar/2.6 (+demo)",
    "Accept-Language": "pt-BR"
}

# === App ===
app = Flask(__name__)

PAGE = r"""
<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Foto → Onde comprar</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<style>
  :root{
    --bg:#F5F8FF; --fg:#142A4D; --mut:#5E6E8C; --card:#FFFFFF; --line:#E3ECF7;
    --accent:#2F6BFF; --accent-2:#00B5FF; --link:#1E66F5; --chip:#F1F6FF; --chip-line:#D6E4FF;
  }
  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial}
  a{color:var(--link);text-decoration:none} a:hover{text-decoration:underline}
  .wrap{max-width:1280px;margin:0 auto;padding:16px 16px 210px}
  .grid{display:grid;gap:16px}
  @media (min-width: 1024px){
    .grid{ grid-template-columns: 1fr 1fr; align-items:start; }
    .col-side .card{ position: sticky; top: 12px; }
  }
  .brand{display:flex;gap:12px;align-items:center;padding:12px 4px}
  .logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,var(--accent),var(--accent-2));}
  h1{font-size:18px;margin:0}
  .hint{color:var(--mut);font-size:13px;margin-top:4px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:0;box-shadow:0 6px 16px rgba(20,42,77,.06)}
  .me{background:linear-gradient(180deg,#FFFFFF 0%, #F9FBFF 100%)}
  .me-row{display:flex;gap:10px;align-items:flex-start}
  .me-thumb{width:56px;height:56px;border-radius:10px;border:1px solid var(--line);object-fit:cover;flex:0 0 auto}
  .pill{display:inline-block;padding:3px 10px;border-radius:999px;border:1px solid var(--chip-line);background:var(--chip);color:#2A4A88;font-size:12px;margin:2px 6px 0 0}
  .shops{display:grid;grid-template-columns:1fr;gap:10px;margin-top:8px}
  @media (min-width: 1024px){ .shops{grid-template-columns:1fr 1fr;} }
  .shop{padding:12px;border-radius:12px;border:1px solid var(--line);background:#FFFFFF}
  .mut{color:var(--mut)}
  .footer{position:fixed;left:0;right:0;bottom:0;background:linear-gradient(180deg, rgba(245,248,255,0) 0%, rgba(245,248,255,.9) 35%, #F5F8FF 75%);padding:12px 10px;border-top:1px solid var(--line);backdrop-filter:saturate(120%) blur(4px)}
  .ft-wrap{max-width:1280px;margin:0 auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .box{display:flex;align-items:center;gap:10px;background:#FFFFFF;border:1px solid var(--line);border-radius:14px;padding:10px 12px;flex:1;min-width:280px}
  .box input[type="text"]{background:transparent;border:0;outline:0;color:var(--fg);font-size:15px}
  .box .q{flex:2;min-width:180px}
  .thumbchip{width:44px;height:44px;border-radius:10px;overflow:hidden;border:1px solid var(--line);display:none}
  .thumbchip img{width:100%;height:100%;object-fit:cover;display:block}
  .btn{display:inline-flex;align-items:center;gap:8px;background:#FFFFFF;border:1px solid var(--line);border-radius:12px;padding:10px 12px;cursor:pointer;transition:.15s ease;color:var(--fg)}
  .btn:hover{border-color:#BFD3FF;box-shadow:0 0 0 2px rgba(47,107,255,.12) inset}
  .send{background:linear-gradient(135deg,var(--accent),var(--accent-2));color:#fff;border:0}
  .send:hover{filter:brightness(1.06)}
  .hidden{display:none}
  .tiny{font-size:12px;color:var(--mut)}
  .modal{position:fixed; inset:0; background:rgba(0,0,0,.5); display:none; align-items:center; justify-content:center; padding:20px;}
  .modal.show{ display:flex; }
  .cam{ background:#fff; border:1px solid var(--line); border-radius:16px; max-width:720px; width:100%; padding:14px; box-shadow:0 10px 30px rgba(20,42,77,.18) }
  .cam video{width:100%;border-radius:12px;border:1px solid var(--line);max-height:70vh;object-fit:contain;background:#F1F4FA}

  /* Mapa + carrossel destacado */
  .mapbox{height:380px;border-radius:12px;border:1px solid var(--line)}
  @media (min-width: 1400px){ .mapbox{height:420px;} }
  .car-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
  .car-ctrl{display:flex;align-items:center;gap:10px}
  .car-btn{
    display:inline-flex;align-items:center;gap:8px;
    border:0; padding:10px 14px; border-radius:12px; cursor:pointer;
    background:linear-gradient(135deg,var(--accent),var(--accent-2)); color:#fff;
    font-weight:600; letter-spacing:.2px; box-shadow:0 6px 14px rgba(47,107,255,.25);
  }
  .car-btn:disabled{opacity:.6;cursor:not-allowed;filter:grayscale(.2)}
  .car-hint{font-size:12px;color:var(--mut);margin-top:6px}

  /* Pontinhos */
  .dots{display:flex;gap:6px;align-items:center}
  .dot{width:10px;height:10px;border-radius:999px;background:#C7D6F7}
  .dot.active{background:#fff;outline:3px solid #2F6BFF}

  /* Chamar atenção (pulso curto no início) */
  @keyframes pulse {
    0%{ box-shadow:0 0 0 0 rgba(47,107,255,.5) }
    70%{ box-shadow:0 0 0 12px rgba(47,107,255,0) }
    100%{ box-shadow:0 0 0 0 rgba(47,107,255,0) }
  }
  .attn{ animation: pulse 1.6s ease-out 3; }

  .leaflet-control-zoom a{background:#fff;color:#27406e;border:1px solid var(--line)}
  .leaflet-control-zoom a:hover{background:#F3F7FF}

  .toast{position:fixed; right:14px; bottom:92px; background:#fff; border:1px solid var(--line); border-radius:12px; padding:10px 12px; box-shadow:0 4px 16px rgba(20,42,77,.12); display:none}
  .toast.show{display:block}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">
    <div class="logo"></div>
    <div>
      <h1>Foto → Onde comprar</h1>
      <div class="hint">Digite o que procura ou use a câmera. A sua localização é solicitada automaticamente.</div>
    </div>
  </div>

  <div class="grid">
    <div class="col-main">
      {% if last_query or me_thumb %}
      <div class="card me">
        <div class="mut tiny">Você</div>
        <div class="me-row" style="margin-top:4px">
          {% if me_thumb %}<img class="me-thumb" src="{{ me_thumb }}" alt="sua foto"/>{% endif %}
          {% if last_query %}<div>{{ last_query }}</div>{% endif %}
        </div>
      </div>
      {% endif %}

      {% if result %}
      <div class="card">
        <div class="mut tiny">Assistente</div>
        <div style="font-size:18px;font-weight:700;margin:4px 0 6px">
          {{ result.product_name or "Produto" }}{% if result.brand %} • {{ result.brand }}{% endif %}{% if result.model %} • {{ result.model }}{% endif %}
        </div>
        {% if result.category %}<div class="mut">Categoria: {{ result.category }}</div>{% endif %}
        {% if result.confidence_pct %}<div style="margin-top:6px"><span class="pill">confiança {{ result.confidence_pct }}%</span></div>{% endif %}
        {% if result.keywords %}
          <div style="margin-top:6px">
            {% for k in result.keywords %}<span class="pill">{{ k }}</span>{% endfor %}
          </div>
        {% endif %}
        {% if result.suggested_query %}<div class="mut" style="margin-top:8px">Consulta sugerida: <code>{{ result.suggested_query }}</code></div>{% endif %}
        <div class="tiny" style="margin-top:10px">Modelo: <b>{{ model_name }}</b></div>
      </div>
      {% endif %}

      {% if policy_msg %}
      <div class="card" style="border-color:#ffd2d2;background:#fff7f7">
        <div style="font-weight:700">⚠️ Solicitação não suportada</div>
        <div class="mut" style="margin-top:6px">{{ policy_msg }}</div>
      </div>
      {% endif %}

      {% if shops is not none %}
      <div class="card">
        <div style="font-weight:700">🛒 Onde comprar — Lojas do mapa</div>
        {% if shops and shops|length > 0 %}
          <div class="shops">
            {% for s in shops %}
              <div class="shop">
                <div style="display:flex;justify-content:space-between;gap:10px;align-items:center">
                  <div style="min-width:0">
                    <b><a href="{{ s.url }}" target="_blank" rel="noopener">{{ s.title }}</a></b>
                    <div class="tiny">{{ s.domain }}</div>
                  </div>
                  <div style="white-space:nowrap">{{ s.right or "" }}</div>
                </div>
                {% if s.snippet %}<div class="mut" style="margin-top:6px">{{ s.snippet }}</div>{% endif %}
              </div>
            {% endfor %}
          </div>
        {% else %}
          <div class="mut">Não encontrei lojas próximas desta categoria.</div>
        {% endif %}
      </div>
      {% endif %}

      {% if extra_shops is not none and extra_shops|length > 0 %}
      <div class="card">
        <div style="font-weight:700">🌐 Outras opções online</div>
        <div class="shops">
          {% for s in extra_shops %}
            <div class="shop">
              <div style="display:flex;justify-content:space-between;gap:10px;align-items:center">
                <div style="min-width:0">
                  <b><a href="{{ s.url }}" target="_blank" rel="noopener">{{ s.title }}</a></b>
                  <div class="tiny">{{ s.domain }}</div>
                </div>
                <div style="white-space:nowrap">{{ s.price or "" }}</div>
              </div>
              {% if s.snippet %}<div class="mut" style="margin-top:6px">{{ s.snippet }}</div>{% endif %}
            </div>
          {% endfor %}
        </div>
        <div class="tiny" style="margin-top:10px">Busca: <b>{{ provider }}</b></div>
      </div>
      {% endif %}
    </div>

    {% if routes and routes|length > 0 %}
    <div class="col-side">
      <div class="card">
        <div class="car-head">
          <div style="font-weight:700">📍 Rotas — {{ routes|length }} lojas próximas</div>
          <div class="car-ctrl">
            <button class="car-btn attn" id="prevBtn" title="Mostrar rota da loja anterior" aria-label="Mostrar rota da loja anterior">◀ Loja anterior</button>
            <div id="dots" class="dots" aria-label="Seleção de loja"></div>
            <button class="car-btn attn" id="nextBtn" title="Mostrar rota da próxima loja" aria-label="Mostrar rota da próxima loja">Próxima loja ▶</button>
          </div>
        </div>
        <div id="routeInfo" class="mut" style="margin:6px 0 8px"></div>
        <div id="map" class="mapbox"></div>
        <div id="openLinks" class="car-hint"></div>
        <div class="car-hint">Dica: use os botões acima ou as teclas ← → para alternar entre as lojas.</div>
      </div>
    </div>
    {% endif %}
  </div>
</div>

<div class="footer">
  <form id="form" class="ft-wrap" method="post" enctype="multipart/form-data" action="{{ url_for('analyze') }}">
    <button type="button" class="btn" id="openCam" title="Abrir câmera" aria-label="Abrir câmera">📷</button>

    <div class="box" style="flex:2">
      <div id="thumbChip" class="thumbchip"><img id="thumbImg" alt="thumb"/></div>
      <input id="q" name="q" type="text" class="q" placeholder="o que procura? (ex.: arroz, dipirona, alicate)" autocomplete="on"/>
      <input id="image_base64" name="image_base64" type="hidden"/>
      <input id="thumb_base64" name="thumb_base64" type="hidden"/>
      <input id="file" name="image" type="file" accept="image/*" capture="environment" class="hidden"/>
      <input id="lat" name="lat" type="hidden"/>
      <input id="lng" name="lng" type="hidden"/>
    </div>

    <button type="submit" class="btn send" id="sendBtn" aria-label="Enviar">Enviar</button>
  </form>
  <div class="ft-wrap" style="margin-top:8px">
    <div class="tiny">Sua localização é usada apenas para as rotas; nada é armazenado.</div>
  </div>
</div>

<!-- Modal da câmera -->
<div class="modal" id="camModal" aria-hidden="true">
  <div class="cam">
    <div class="tiny">Câmera</div>
    <video id="video" autoplay playsinline></video>
    <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
      <button type="button" class="btn" id="btnCapture">Capturar</button>
      <button type="button" class="btn" id="btnClose">Fechar</button>
    </div>
  </div>
</div>

<div id="toast" class="toast">✅ Localização ativada.</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
  const form = document.getElementById('form');
  const q = document.getElementById('q');
  const fileInput = document.getElementById('file');
  const imgB64 = document.getElementById('image_base64');
  const thumbB64 = document.getElementById('thumb_base64');
  const latInput = document.getElementById('lat');
  const lngInput = document.getElementById('lng');
  const chip = document.getElementById('thumbChip');
  const chipImg = document.getElementById('thumbImg');
  const toast = document.getElementById('toast');

  // Geo automática ao carregar
  document.addEventListener('DOMContentLoaded', () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          latInput.value = String(pos.coords.latitude);
          lngInput.value = String(pos.coords.longitude);
          toast.classList.add('show');
          setTimeout(()=>toast.classList.remove('show'), 3000);
        },
        (err) => { console.warn("Geo erro:", err); },
        { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
      );
    }
  });

  // Câmera
  const camModal = document.getElementById('camModal');
  const openCam = document.getElementById('openCam');
  const btnClose = document.getElementById('btnClose');
  const btnCapture = document.getElementById('btnCapture');
  const video = document.getElementById('video');
  let stream = null;

  openCam.addEventListener('click', async () => {
    camModal.classList.add('show'); camModal.setAttribute('aria-hidden','false');
    try{
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      video.srcObject = stream;
    }catch(e){ camModal.classList.remove('show'); camModal.setAttribute('aria-hidden','true'); fileInput.click(); }
  });
  function closeCam(){ camModal.classList.remove('show'); camModal.setAttribute('aria-hidden','true'); if(stream){ stream.getTracks().forEach(t=>t.stop()); stream=null; } }
  btnClose.addEventListener('click', closeCam);

  btnCapture.addEventListener('click', () => {
    if(!stream) return;
    const track = stream.getVideoTracks()[0];
    const s = track.getSettings ? track.getSettings() : {};
    const w = s.width || video.videoWidth || 1280;
    const h = s.height || video.videoHeight || 720;
    const c = document.createElement('canvas'); c.width = w; c.height = h;
    const ctx = c.getContext('2d'); ctx.drawImage(video, 0, 0, w, h);
    const dataUrl = c.toDataURL('image/jpeg', 0.92);
    imgB64.value = dataUrl; thumbB64.value = dataUrl; chipImg.src = du = dataUrl; chip.style.display = 'block';
    closeCam();
  });

  // Upload manual → miniatura também
  fileInput.addEventListener('change', () => {
    imgB64.value = ""; thumbB64.value = "";
    const f = fileInput.files && fileInput.files[0];
    if(!f) { chip.style.display='none'; return; }
    const reader = new FileReader();
    reader.onload = (e)=>{ const du = String(e.target.result); chipImg.src = du; chip.style.display='block'; thumbB64.value = du; imgB64.value = du; };
    reader.readAsDataURL(f);
  });

  // Enviar com Enter
  q.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ e.preventDefault(); form.submit(); } });

  // ===== Carrossel de rotas (um único mapa) =====
  {% if routes and routes|length > 0 %}
    const routes = {{ routes|tojson }};
    const infoEl = document.getElementById('routeInfo');
    const dotsEl = document.getElementById('dots');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const openLinks = document.getElementById('openLinks');

    const map = L.map('map');
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
    }).addTo(map);

    let userMarker = null, storeMarker = null, poly = null, current = 0;

    function renderDots(){
      dotsEl.innerHTML = '';
      routes.forEach((_, i) => {
        const d = document.createElement('div');
        d.className = 'dot' + (i===current?' active':'');
        d.title = 'Ir para a loja ' + String(i+1);
        d.style.cursor = 'pointer';
        d.addEventListener('click', () => { current = i; renderRoute(true); });
        dotsEl.appendChild(d);
      });
    }

    function renderRoute(userAction=false){
      const r = routes[current];
      infoEl.innerHTML = `<b>${current+1}/${routes.length}) ${r.store_name}</b><br/>${r.store_address}<br/>~${r.distance_km} km · ~${r.duration_min} min (estimativa)`;

      if (poly) { map.removeLayer(poly); poly = null; }
      if (userMarker) { map.removeLayer(userMarker); userMarker = null; }
      if (storeMarker) { map.removeLayer(storeMarker); storeMarker = null; }

      const user = [r.user_lat, r.user_lng];
      const store = [r.store_lat, r.store_lng];

      poly = L.polyline(r.geometry.map(p => [p[1], p[0]]), { weight: 5, color:'#2F6BFF' }).addTo(map);
      userMarker = L.marker(user).addTo(map).bindPopup("Você");
      storeMarker = L.marker(store).addTo(map).bindPopup(r.store_name);

      const bounds = L.latLngBounds([user, store, ...poly.getLatLngs()]);
      map.fitBounds(bounds, { padding: [40,40] });

      prevBtn.disabled = (current === 0);
      nextBtn.disabled = (current === routes.length - 1);

      // Links rápidos
      const site = r.website ? `<a href="${r.website}" target="_blank" rel="noopener">Abrir site da loja</a>` : '';
      const maps = r.maps_url ? `<a href="${r.maps_url}" target="_blank" rel="noopener">Abrir no Google Maps</a>` : '';
      openLinks.innerHTML = [site, maps].filter(Boolean).join(" · ");

      if (userAction){
        prevBtn.classList.remove('attn');
        nextBtn.classList.remove('attn');
      }

      renderDots();
      setTimeout(()=>map.invalidateSize(), 50);
    }

    prevBtn.addEventListener('click', () => { if (current > 0) { current--; renderRoute(true); } });
    nextBtn.addEventListener('click', () => { if (current < routes.length-1) { current++; renderRoute(true); } });

    // Atalhos de teclado ← →
    window.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft' && current > 0){ current--; renderRoute(true); }
      if (e.key === 'ArrowRight' && current < routes.length-1){ current++; renderRoute(true); }
    });

    renderRoute();
    setTimeout(()=>{ prevBtn.classList.remove('attn'); nextBtn.classList.remove('attn'); }, 6000);
  {% endif %}
</script>
</body>
</html>
"""

# ================== Utils ==================

def pil_compress_to_jpeg(fp, max_side=1280, quality=82) -> bytes:
    im = Image.open(fp).convert("RGB")
    w, h = im.size
    scale = min(1.0, float(max_side)/float(max(w,h)))
    if scale < 1.0:
        im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()

def b64_to_bytes(data_url: str) -> bytes:
    if not data_url: return b""
    m = re.match(r"^data:image\/[a-zA-Z0-9+.\-]+;base64,(.+)$", data_url)
    if not m: return b""
    return base64.b64decode(m.group(1))

def parse_domain(url: str) -> str:
    try:
        return re.sub(r"^www\.", "", re.sub(r"^https?://", "", url)).split("/")[0]
    except Exception:
        return ""

# Normalização para política
def _norm_txt(s: str) -> str:
    return unicodedata.normalize("NFD", (s or "").lower()).encode("ascii","ignore").decode("ascii")

# =============== Intenção ===============

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().strip()

FOOD_TERMS = {"arroz","feijao","leite","acucar","cafe","oleo","azeite","farinha","trigo","macarrao","sal","carne","frango","ovo","ovos","refrigerante","suco","agua","mercado","supermercado","hortifruti"}
PHARMACY_TERMS = {"remedio","medicamento","remedios","medicamentos","dipirona","paracetamol","ibuprofeno","antigripal","dorflex","buscopan","antialergico","farmacia","drogaria","xarope"}
TOOLS_TERMS = {"alicate","martelo","chave de fenda","broca","serra","ferramenta","ferramentas","furadeira","parafusadeira","serrote","trena","nivel","marreta","serra circular","home center","materiais de construcao","material de construcao"}
STATIONERY_TERMS = {"caderno","papel a4","caneta","lapis","apontador","cola","papelaria","material escolar","toner","cartucho"}
ELECTRONICS_TERMS = {"tv","celular","smartphone","notebook","tablet","headphone","fone","monitor","ssd","placa de video","mouse","teclado","console","xbox","playstation"}

# Salão / Barbearia
BEAUTY_TERMS = {
    "cabeleireiro","cabelereiro","cabeleleiro","cabeleireira","cabelereira",
    "barbearia","barbeiro","salão de beleza","salao de beleza",
    "hair","haircut","hair salon","beauty salon","barber","barber shop"
}

# Serviços automotivos
AUTO_TERMS = {
    "mecânico","mecanico","mecânica","mecanica","oficina","oficina mecanica",
    "centro automotivo","auto center","alinhamento","balanceamento","funilaria",
    "troca de óleo","troca de oleo","revisão","revisao","auto eletrica","auto elétrica",
    "barulho no carro","conserto de carro","car repair","auto repair","mechanic"
}

# Itens/consultas proibidas (ex.: drogas ilícitas)
PROHIBITED_TERMS = {
    "maconha","cannabis","haxixe","skank","cocaína","cocaina","crack","mdma","ecstasy","êxtase",
    "lsd","heroína","heroina","ketamina","metanfetamina","met","meth","gbl","ghb"
}

def is_prohibited(text: str) -> bool:
    bag = _norm_txt(text)
    return any(term in bag for term in (_norm_txt(t) for t in PROHIBITED_TERMS))

INTENT_TABLE = [
    ("auto_service", AUTO_TERMS),      # serviços primeiro
    ("beauty", BEAUTY_TERMS),
    ("pharmacy", PHARMACY_TERMS),
    ("tools", TOOLS_TERMS),
    ("stationery", STATIONERY_TERMS),
    ("electronics", ELECTRONICS_TERMS),
    ("grocery", FOOD_TERMS),
]

INTENT_ANCHOR = {
    "grocery": "supermercado",
    "pharmacy": "farmácia",
    "tools": "loja de ferramentas",
    "stationery": "papelaria",
    "electronics": "loja de eletrônicos",
    "beauty": "cabeleireiro",
    "auto_service": "oficina mecânica",
}

INTENT_CATS = {
    "grocery": {"supermercado","hipermercado","mercearia","atacado","atacadista","minimercado","loja de conveniencia","mercado","convenience store","grocery store","supermarket"},
    "pharmacy": {"farmacia","drogaria","drugstore","pharmacy"},
    "tools": {"loja de ferramentas","materiais de construcao","home center","ferramentas","material de construcao","hardware store"},
    "stationery": {"papelaria","material de escritorio","loja de material de escritorio","stationery store"},
    "electronics": {"loja de eletronicos","eletronicos","informatica","telefonia","electronics store"},
    "beauty": {"cabeleireiro","salao de beleza","salão de beleza","barbearia","barbeiro","hair salon","barber shop","beauty salon"},
    "auto_service": {
        "oficina mecanica","oficina mecânica","centro automotivo","auto center",
        "auto eletrica","auto elétrica","mecanica","mechanic","auto repair","car repair",
        "funilaria","alinhamento","balanceamento"
    },
}

BLACKLIST_BY_INTENT = {
    "grocery": {"kalunga","kabum","kabu!","magazine luiza","casas bahia","fast shop","americanas","submarino"},
    "pharmacy": {"kalunga","kabum","magazine luiza","casas bahia","fast shop","americanas","submarino","carrefour"},
    "tools": {"kalunga","farmacia","drogaria"},
    "stationery": set(),
    "electronics": {"farmacia","drogaria","supermercado"},
    "beauty": {"supermercado","mercado","farmacia","drogaria","home center","ferramentas"},
    "auto_service": {"supermercado","mercado","farmacia","drogaria","papelaria","loja de eletronicos"},
}

def detect_intent(user_q: str, info: Optional[Dict[str,Any]]) -> str:
    bag = _norm(user_q)
    if info:
        for k in ("product_name","brand","model","category"):
            v = info.get(k)
            if isinstance(v,str): bag += " " + _norm(v)
        for kw in info.get("keywords") or []:
            bag += " " + _norm(kw)
    for name, terms in INTENT_TABLE:
        if any(_norm(t) in bag for t in terms):
            return name
    return "grocery"  # default

# =============== OpenAI (opcional para identificar produto em foto) ===============

def identify_product_with_gpt4omini(image_data_uri: str, user_locale: str = "pt-BR", user_hint: str = "") -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    system_prompt = "Você é um assistente especialista em identificar produtos a partir de imagens para e-commerce. Responda em JSON válido, sem texto fora do JSON."
    hint_txt = f"\nDica do usuário: {user_hint}\n" if user_hint else ""
    user_prompt = (
        "Identifique com precisão o produto da foto (nome, marca, modelo, categoria). "
        "Se houver rótulo/código, considere-o. Devolva JSON com campos:\n"
        "{"
        '"product_name": str, "brand": str|null, "model": str|null, "category": str|null,'
        '"keywords": [str,...], "suggested_query": str, "confidence_pct": int'
        "}\n"
        f"Idioma: {user_locale}.{hint_txt}Responda estritamente em JSON."
    )
    payload = {"model":"gpt-4o-mini","temperature":0.2,"messages":[
        {"role":"system","content":system_prompt},
        {"role":"user","content":[{"type":"text","text":user_prompt},{"type":"image_url","image_url":{"url":image_data_uri}}]},
    ],"max_tokens":400}
    try:
        r = requests.post(OPENAI_CHAT_URL, headers=headers, data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except Exception:
            m = re.search(r"\{.*\}", content, flags=re.S)
            if m: return json.loads(m.group(0))
    except Exception as e:
        print("OPENAI_ERROR:", e)
    return {"product_name":None,"brand":None,"model":None,"category":None,"keywords":[],"suggested_query":None,"confidence_pct":None}

# =============== Online shops (busca geral) ===============

def search_shops_serpapi(query: str, gl: str="br", hl: str="pt-BR") -> List[Dict[str, Any]]:
    if not SERPAPI_API_KEY: return []
    url = "https://serpapi.com/search.json"
    params = {"engine":"google_shopping","q":query,"gl":gl,"hl":hl,"api_key":SERPAPI_API_KEY,"num":"20"}
    try:
        rs = requests.get(url, params=params, timeout=40); rs.raise_for_status(); js = rs.json()
    except Exception as e:
        print("SERPAPI_ERROR:", e); return []
    items = []
    for it in (js.get("shopping_results") or []):
        items.append({"title":it.get("title"),"url":it.get("link"),"price":it.get("price"),
                      "domain":parse_domain(it.get("link","")),"snippet":(it.get("source") or it.get("product_id") or "")})
    seen, uniq = set(), []
    for x in items:
        k = (x.get("domain"), x.get("title"))
        if k in seen: continue
        seen.add(k); uniq.append(x)
    return uniq[:12]

def search_shops_bing(query: str, mkt: str="pt-BR") -> List[Dict[str, Any]]:
    if not BING_SEARCH_KEY: return []
    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": BING_SEARCH_KEY}
    q = f'{query} comprar site:mercadolivre.com.br OR site:magazineluiza.com.br OR site:amazon.com.br OR site:kabum.com.br OR site:submarino.com.br'
    try:
        rs = requests.get(url, headers=headers, params={"q": q, "mkt": mkt, "count": 20, "textDecorations": False}, timeout=40)
        rs.raise_for_status(); js = rs.json()
    except Exception as e:
        print("BING_ERROR:", e); return []
    out = []
    for w in (js.get("webPages") or {}).get("value", []):
        out.append({"title":w.get("name"),"url":w.get("url"),"price":None,"domain":parse_domain(w.get("url","")),"snippet":w.get("snippet")})
    seen, uniq = set(), []
    for x in out:
        k = (x.get("domain"), x.get("title"))
        if k in seen: continue
        seen.add(k); uniq.append(x)
    return uniq[:12]

def build_store_links(query: str) -> List[Dict[str, Any]]:
    q = quote_plus(query.strip())
    bases = [
        ("Mercado Livre", f"https://lista.mercadolivre.com.br/{q}"),
        ("Amazon",        f"https://www.amazon.com.br/s?k={q}"),
        ("Magalu",        f"https://www.magazineluiza.com.br/busca/{q}/"),
        ("KaBuM!",        f"https://www.kabum.com.br/busca/{q}"),
        ("Submarino",     f"https://www.submarino.com.br/busca/{q}"),
        ("Americanas",    f"https://www.americanas.com.br/busca/{q}"),
        ("Casas Bahia",   f"https://www.casasbahia.com.br/{q}/b"),
        ("Shoptime",      f"https://www.shoptime.com.br/busca/{q}"),
        ("Kalunga",       f"https://www.kalunga.com.br/busca/{q}"),
        ("Fast Shop",     f"https://www.fastshop.com.br/web/search?q={q}"),
        ("Carrefour",     f"https://www.carrefour.com.br/busca/{q}"),
    ]
    out = []
    for name, url in bases:
        out.append({"title": f"{name} — resultados para '{query}'","url": url,"price": None,"domain": parse_domain(url),"snippet": "Abrir resultados de busca"})
    return out

def find_shops(query: str, user_locale: str="pt-BR") -> Tuple[List[Dict[str, Any]], str]:
    provider_used = "serpapi" if SERPAPI_API_KEY else ("bing" if BING_SEARCH_KEY else "links")
    q = query.strip()
    if q and "comprar" not in q.lower(): q = "comprar " + q
    if provider_used == "serpapi":
        shops = search_shops_serpapi(q, gl="br", hl=user_locale)
        if not shops: shops = build_store_links(q); provider_used = "links"
    elif provider_used == "bing":
        shops = search_shops_bing(q, mkt="pt-BR")
        if not shops: shops = build_store_links(q); provider_used = "links"
    else:
        shops = build_store_links(q); provider_used = "links"
    return shops, provider_used

# =============== Maps / Geo ===============

def serpapi_maps_search_anchor_only(anchor: str, lat: float, lng: float, allow_cats: Optional[set], blacklist: set) -> List[Dict[str, Any]]:
    """Busca Google Maps via SerpApi usando APENAS a âncora; filtra por categoria e aplica blacklist."""
    if not SERPAPI_API_KEY: return []
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_maps",
        "type": "search",
        "q": anchor,
        "ll": f"@{lat},{lng},14z",
        "hl": SERPAPI_HL,
        "google_domain": SERPAPI_GOOGLE_DOMAIN,
        "api_key": SERPAPI_API_KEY,
        "no_cache": "true",
    }
    try:
        rs = requests.get(url, params=params, timeout=30)
        rs.raise_for_status()
        js = rs.json()
    except Exception as e:
        print("SERPAPI_MAPS_ERROR:", e); return []

    local_results = js.get("local_results") or []
    out = []
    cats_norm = {_norm(x) for x in (allow_cats or set())}
    bl_norm = {_norm(x) for x in (blacklist or set())}

    for it in local_results:
        gps = it.get("gps_coordinates") or {}
        if not gps: continue
        try:
            slat = float(gps.get("latitude")); slng = float(gps.get("longitude"))
        except Exception:
            continue

        title = it.get("title") or anchor
        addr = it.get("address") or ""
        t_norm = _norm(it.get("type") or "")
        c_norm = _norm(it.get("category") or "")
        title_norm = _norm(title)

        if any(b in title_norm for b in bl_norm):
            continue

        if cats_norm:
            joined = f"{t_norm} {c_norm}".strip()
            if joined and not any(cat in joined for cat in cats_norm):
                continue

        place_id = it.get("place_id") or ""
        website = it.get("website") or ""
        gmaps_link = it.get("link") if str(it.get("link","")).startswith("https://www.google.") else ""

        maps_url = gmaps_link or (f"https://www.google.com/maps/search/?api=1&query={slat}%2C{slng}&query_place_id={place_id}" if place_id else f"https://www.google.com/maps/@{slat},{slng},18z")

        out.append({
            "title": title,
            "address": addr,
            "lat": slat, "lng": slng,
            "type": it.get("type"), "category": it.get("category"),
            "place_id": place_id,
            "website": website,
            "maps_url": maps_url
        })

    out.sort(key=lambda p: haversine_km(lat, lng, p["lat"], p["lng"]))
    return out

def nominatim_search(name: str, lat: float, lng: float, limit: int = 10) -> List[Dict[str, Any]]:
    minx, miny, maxx, maxy = (lng-0.7, lat-0.7, lng+0.7, lat+0.7)
    params = {"format":"jsonv2","q":name,"limit":str(limit),"viewbox":f"{minx},{maxy},{maxx},{miny}","bounded":1,"countrycodes":"br","addressdetails":1}
    if NOMINATIM_EMAIL: params["email"] = NOMINATIM_EMAIL
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=NOMINATIM_HEADERS, timeout=20)
        r.raise_for_status(); return r.json() or []
    except Exception as e:
        print("NOMINATIM_ERROR:", e); return []

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0; p = math.pi/180.0
    dlat = (lat2-lat1)*p; dlon = (lon2-lon1)*p
    a = (math.sin(dlat/2)**2) + math.cos(lat1*p)*math.cos(lat2*p)*(math.sin(dlon/2)**2)
    return 2*R*math.asin(math.sqrt(a))

def osrm_route(user_lat: float, user_lng: float, store_lat: float, store_lng: float) -> Optional[Dict[str, Any]]:
    url = f"https://router.project-osrm.org/route/v1/driving/{user_lng},{user_lat};{store_lng},{store_lat}"
    params = {"overview":"full","geometries":"geojson"}
    try:
        r = requests.get(url, params=params, timeout=25)
        r.raise_for_status(); js = r.json(); routes = js.get("routes") or []
        if not routes: return None
        route = routes[0]
        return {"distance_km": round(route.get("distance",0)/1000.0, 1),
                "duration_min": round(route.get("duration",0)/60.0),
                "geometry": route.get("geometry", {}).get("coordinates") or []}
    except Exception as e:
        print("OSRM_ERROR:", e); return None

def compute_top_routes(lat: float, lng: float, user_query: str, info: Optional[Dict[str,Any]], topn: int = 3) -> List[Dict[str, Any]]:
    """Retorna até topn rotas p/ lojas mais próximas; inclui site/maps_url das lojas do mapa."""
    intent = detect_intent(user_query, info)
    anchor = INTENT_ANCHOR[intent]
    allow_cats = INTENT_CATS[intent]
    blacklist = BLACKLIST_BY_INTENT[intent]

    routes: List[Dict[str, Any]] = []

    try:
        res = serpapi_maps_search_anchor_only(anchor, lat, lng, allow_cats, blacklist)
    except Exception as e:
        print("MAPS_SEARCH_ERROR:", e); res = []

    for hit in res[:max(topn*3, topn)]:
        if len(routes) >= topn: break
        r = osrm_route(lat, lng, hit["lat"], hit["lng"])
        if not r: continue
        routes.append({
            "store_name": hit["title"],
            "store_address": hit.get("address") or "",
            "store_lat": hit["lat"], "store_lng": hit["lng"],
            "user_lat": lat, "user_lng": lng,
            "distance_km": r["distance_km"], "duration_min": int(r["duration_min"]),
            "geometry": r["geometry"],
            "website": hit.get("website") or "",
            "maps_url": hit.get("maps_url") or ""
        })

    if len(routes) < topn:
        try:
            cands = []
            for place in nominatim_search(anchor, lat, lng, limit=10):
                try:
                    slat = float(place["lat"]); slng = float(place["lon"])
                except Exception:
                    continue
                cands.append({"name": place.get("display_name") or anchor, "lat": slat, "lng": slng,
                              "d": haversine_km(lat, lng, slat, slng)})
            cands.sort(key=lambda x: x["d"])
            for c in cands:
                if len(routes) >= topn: break
                r = osrm_route(lat, lng, c["lat"], c["lng"])
                if not r: continue
                maps_url = f"https://www.google.com/maps/search/?api=1&query={c['lat']}%2C{c['lng']}"
                routes.append({
                    "store_name": c["name"], "store_address": c["name"],
                    "store_lat": c["lat"], "store_lng": c["lng"],
                    "user_lat": lat, "user_lng": lng,
                    "distance_km": r["distance_km"], "duration_min": int(r["duration_min"]),
                    "geometry": r["geometry"],
                    "website": "",
                    "maps_url": maps_url
                })
        except Exception as e:
            print("FALLBACK_OSM_ERROR:", e)

    routes.sort(key=lambda x: x["distance_km"])
    return routes[:topn]

# =============== Flask ===============

@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE,
        model_name="gpt-4o-mini",
        provider="serpapi" if SERPAPI_API_KEY else ("bing" if BING_SEARCH_KEY else "links"),
        last_query=None, me_thumb=None, result=None,
        shops=None, extra_shops=None, routes=[], policy_msg=None
    )

@app.route("/analyze", methods=["POST"])
def analyze():
    user_q = (request.form.get("q") or "").strip()
    img_b64 = (request.form.get("image_base64") or "").strip()
    thumb_b64 = (request.form.get("thumb_base64") or "").strip()
    f = request.files.get("image")
    lat_str = request.form.get("lat"); lng_str = request.form.get("lng")

    # localização do usuário (geolocalização automática)
    resolved = None
    if lat_str and lng_str:
        try: resolved = (float(lat_str), float(lng_str), "Minha localização")
        except: resolved = None

    info = None
    query = ""
    me_thumb_dataurl = None

    if img_b64 or f:
        if img_b64:
            raw = b64_to_bytes(img_b64)
            jpeg = pil_compress_to_jpeg(io.BytesIO(raw), max_side=1280, quality=82)
            thumb = pil_compress_to_jpeg(io.BytesIO(raw), max_side=360, quality=70)
        else:
            raw_file = f.read()
            jpeg = pil_compress_to_jpeg(io.BytesIO(raw_file), max_side=1280, quality=82)
            thumb = pil_compress_to_jpeg(io.BytesIO(raw_file), max_side=360, quality=70)

        data_uri = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        me_thumb_dataurl = "data:image/jpeg;base64," + base64.b64encode(thumb).decode("ascii")
        if thumb_b64.startswith("data:image/"): me_thumb_dataurl = thumb_b64

        info = identify_product_with_gpt4omini(data_uri, user_locale="pt-BR", user_hint=user_q)

        q_parts = []
        for k in ("product_name","brand","model","category","suggested_query"):
            v = (info or {}).get(k)
            if v and isinstance(v, str): q_parts.append(v)
        if (info or {}).get("keywords"): q_parts.extend(info["keywords"][:5])
        if user_q: q_parts.insert(0, user_q)
        query = " ".join(dict.fromkeys([p for p in q_parts if p])) or ("comprar " + datetime.now().strftime("produto %Y"))
    else:
        query = user_q or ""

    # Bloqueio para itens proibidos
    if is_prohibited(user_q or query):
        return render_template_string(PAGE,
            model_name="gpt-4o-mini",
            provider="",
            last_query=user_q if user_q else query,
            me_thumb=me_thumb_dataurl,
            result=info,
            shops=None, extra_shops=None, routes=[], policy_msg="Não posso ajudar a localizar, comprar ou traçar rotas para itens ilegais ou perigosos."
        )

    # lojas online gerais (ficam em "Outras opções online")
    extra_shops, provider_used = find_shops(query or "produto", user_locale="pt-BR")
    intent_now = detect_intent(query, info)
    if intent_now in {"auto_service","beauty"}:
        extra_shops = None  # para serviços locais, não faz sentido listar shopping

    # rotas + lojas do mapa
    routes = []
    shops_from_routes = []
    try:
        if resolved:
            u_lat, u_lng, _ = resolved
            routes = compute_top_routes(float(u_lat), float(u_lng), user_query=query, info=info, topn=3)
            for r in routes:
                r["user_lat"] = float(u_lat)
                r["user_lng"] = float(u_lng)
                # "Onde comprar" a partir das lojas do mapa (garante correspondência)
                url = (r.get("website") or "").strip() or (r.get("maps_url") or "").strip()
                shops_from_routes.append({
                    "title": r["store_name"],
                    "url": url,
                    "right": f"~{r['distance_km']} km",
                    "domain": parse_domain(url),
                    "snippet": f"~{r['duration_min']} min (rota)"
                })
    except Exception as e:
        print("ROUTES_ERROR:", e); routes = []

    return render_template_string(PAGE,
        model_name="gpt-4o-mini",
        provider=provider_used,
        last_query=user_q if user_q else query,
        me_thumb=me_thumb_dataurl,
        result=info,
        shops=shops_from_routes,
        extra_shops=extra_shops,
        routes=routes,
        policy_msg=None
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
