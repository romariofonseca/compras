# -*- coding: utf-8 -*-
"""
Flask • UI com caixa única + câmera + mapa (50/50) + miniatura automática
Tema claro inspirado na Tray: cards brancos, texto navy, botões em gradiente azul→ciano.
"""

import os, io, base64, json, re, math
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import quote_plus

import requests
from flask import Flask, request, render_template_string, redirect, url_for
from PIL import Image

# --- CHAVES DE FALLBACK (use variáveis de ambiente em produção) ---
OPENAI_FALLBACK_KEY = ""
SERPAPI_FALLBACK_KEY = ""

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", OPENAI_FALLBACK_KEY).strip()
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", SERPAPI_FALLBACK_KEY).strip()
BING_SEARCH_KEY = os.getenv("BING_SEARCH_KEY", "").strip()

_shop_env = os.getenv("SHOP_PROVIDER", "").strip().lower()
if _shop_env in ("serpapi", "bing", "links"):
    SHOP_PROVIDER = _shop_env
else:
    SHOP_PROVIDER = "serpapi" if SERPAPI_API_KEY else ("bing" if BING_SEARCH_KEY else "links")

PORT = int(os.getenv("PORT", "11001"))
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

NOMINATIM_EMAIL = os.getenv("NOMINATIM_EMAIL", "").strip()
NOMINATIM_HEADERS = {
    "User-Agent": "foto-onde-comprar/1.6 (+demo)",
    "Accept-Language": "pt-BR"
}

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
  /* ===== Paleta clara — “cara Tray” =====
     Base clara, cartões brancos, navy para textos,
     acento azul→ciano nos botões/realces.
  */
  :root{
    --bg:#F5F8FF;          /* fundo claro azulado */
    --fg:#142A4D;          /* texto principal (navy) */
    --mut:#5E6E8C;         /* texto secundário */
    --card:#FFFFFF;        /* cartões brancos */
    --line:#E3ECF7;        /* bordas suaves */
    --accent:#2F6BFF;      /* azul forte */
    --accent-2:#00B5FF;    /* ciano */
    --link:#1E66F5;        /* links */
    --chip:#F1F6FF;        /* chip claro */
    --chip-line:#D6E4FF;   /* borda do chip */
  }

  *{box-sizing:border-box}
  html,body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial}
  a{color:var(--link);text-decoration:none} a:hover{text-decoration:underline}

  .wrap{max-width:1280px;margin:0 auto;padding:16px 16px 160px}
  .grid{display:grid;gap:16px}
  @media (min-width: 1024px){
    .grid{ grid-template-columns: 1fr 1fr; align-items:start; }
    .col-side .card{ position: sticky; top: 12px; }
  }

  .brand{display:flex;gap:12px;align-items:center;padding:12px 4px}
  .logo{width:36px;height:36px;border-radius:10px;
        background:linear-gradient(135deg,var(--accent),var(--accent-2));}
  h1{font-size:18px;margin:0}
  .hint{color:var(--mut);font-size:13px;margin-top:4px}

  .card{
    background:var(--card);
    border:1px solid var(--line);
    border-radius:16px;
    padding:16px;margin:0;
    box-shadow:0 6px 16px rgba(20,42,77,.06);
  }
  .me{background:linear-gradient(180deg,#FFFFFF 0%, #F9FBFF 100%);}

  .me-row{display:flex;gap:10px;align-items:flex-start}
  .me-thumb{width:56px;height:56px;border-radius:10px;border:1px solid var(--line);object-fit:cover;flex:0 0 auto}

  .pill{
    display:inline-block;padding:3px 10px;border-radius:999px;
    border:1px solid var(--chip-line); background:var(--chip);
    color:#2A4A88; font-size:12px; margin:2px 6px 0 0
  }

  .shops{display:grid;grid-template-columns:1fr;gap:10px;margin-top:8px}
  @media (min-width: 1024px){ .shops{grid-template-columns:1fr 1fr;} }
  .shop{padding:12px;border-radius:12px;border:1px solid var(--line);background:#FFFFFF}

  .mut{color:var(--mut)}

  /* ----- Rodapé fixo ----- */
  .footer{
    position:fixed;left:0;right:0;bottom:0;
    background:linear-gradient(180deg, rgba(245,248,255,0) 0%, rgba(245,248,255,.9) 35%, #F5F8FF 75%);
    padding:12px 10px;border-top:1px solid var(--line);
    backdrop-filter:saturate(120%) blur(4px)
  }
  .ft-wrap{max-width:1280px;margin:0 auto;display:flex;gap:8px;align-items:center}
  .box{
    display:flex;align-items:center;gap:10px;
    background:#FFFFFF;border:1px solid var(--line);
    border-radius:14px;padding:10px 12px;flex:1
  }
  .box input[type="text"]{flex:1;background:transparent;border:0;outline:0;color:var(--fg);font-size:15px}
  .thumbchip{width:44px;height:44px;border-radius:10px;overflow:hidden;border:1px solid var(--line);display:none}
  .thumbchip img{width:100%;height:100%;object-fit:cover;display:block}

  .btn{
    display:inline-flex;align-items:center;gap:8px;
    background:#FFFFFF;border:1px solid var(--line);
    border-radius:12px;padding:10px 12px;cursor:pointer;transition:.15s ease;
    color:var(--fg)
  }
  .btn:hover{border-color:#BFD3FF;box-shadow:0 0 0 2px rgba(47,107,255,.12) inset}
  .send{
    background:linear-gradient(135deg,var(--accent),var(--accent-2));
    color:#fff;border:0
  }
  .send:hover{filter:brightness(1.06)}
  .hidden{display:none}
  .tiny{font-size:12px;color:var(--mut)}

  /* ----- Modal da câmera ----- */
  .modal{position:fixed; inset:0; background:rgba(0,0,0,.5); display:none; align-items:center; justify-content:center; padding:20px;}
  .modal.show{ display:flex; }
  .cam{ background:#fff; border:1px solid var(--line); border-radius:16px; max-width:720px; width:100%; padding:14px; box-shadow:0 10px 30px rgba(20,42,77,.18) }
  .cam video{width:100%;border-radius:12px;border:1px solid var(--line);max-height:70vh;object-fit:contain;background:#F1F4FA}

  /* ----- Mapa (Leaflet) ----- */
  #map_card{margin-top:0}
  #map{height:420px;border-radius:12px;border:1px solid var(--line)}
  @media (min-width: 1400px){ #map{height:520px;} }
  .leaflet-control-zoom a{background:#fff;color:#27406e;border:1px solid var(--line)}
  .leaflet-control-zoom a:hover{background:#F3F7FF}
</style>
</head>
<body>
<div class="wrap">
  <div class="brand">
    <div class="logo"></div>
    <div>
      <h1>Foto → Onde comprar</h1>
      <div class="hint">Digite ou toque no ícone de câmera para tirar a foto. Use 📍 para a rota até a loja física mais próxima.</div>
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

      {% if shops is not none %}
      <div class="card">
        <div style="font-weight:700">🛒 Onde comprar</div>
        {% if shops and shops|length > 0 %}
          <div class="shops">
            {% for s in shops %}
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
        {% else %}
          <div class="mut">Não encontrei lojas com a consulta atual. Tente outra foto ou ajuste a descrição.</div>
        {% endif %}
        <div class="tiny" style="margin-top:10px">Busca: <b>{{ provider }}</b></div>
      </div>
      {% endif %}
    </div>

    {% if route %}
    <div class="col-side">
      <div id="map_card" class="card">
        <div style="font-weight:700">📍 Rota até a loja mais próxima</div>
        <div class="mut" style="margin:6px 0 10px">
          {{ route.store_name }} — ~{{ route.distance_km }} km · ~{{ route.duration_min }} min (estimativa)
        </div>
        <div id="map"></div>
      </div>
    </div>
    {% endif %}
  </div>
</div>

<!-- Rodapé -->
<div class="footer">
  <form id="form" class="ft-wrap" method="post" enctype="multipart/form-data" action="{{ url_for('analyze') }}">
    <button type="button" class="btn" id="openCam" title="Abrir câmera" aria-label="Abrir câmera">📷</button>
    <div class="box" style="flex:1">
      <div id="thumbChip" class="thumbchip"><img id="thumbImg" alt="thumb"/></div>
      <input id="q" name="q" type="text" placeholder="o que procura?" autocomplete="on"/>
      <input id="image_base64" name="image_base64" type="hidden"/>
      <input id="thumb_base64" name="thumb_base64" type="hidden"/>
      <input id="file" name="image" type="file" accept="image/*" capture="environment" class="hidden"/>
      <input id="lat" name="lat" type="hidden"/>
      <input id="lng" name="lng" type="hidden"/>
    </div>
    <button type="button" class="btn" id="useLoc" title="Usar minha localização">📍</button>
    <button type="submit" class="btn send" id="sendBtn" aria-label="Enviar">Enviar</button>
  </form>
  <div class="ft-wrap" style="margin-top:8px">
    <div class="tiny">Sua localização é usada apenas para calcular distância/rota; nada é armazenado.</div>
  </div>
</div>

<!-- Modal da câmera (sem pré-visualização) -->
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

  // Geolocalização
  document.getElementById('useLoc').addEventListener('click', () => {
    if (!navigator.geolocation) { alert("Geolocalização não suportada."); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => { latInput.value = String(pos.coords.latitude); lngInput.value = String(pos.coords.longitude); alert("Localização adicionada! Envie sua busca para ver a rota."); },
      (err) => { alert("Não foi possível obter a localização."); console.error(err); },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );
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
    imgB64.value = dataUrl; thumbB64.value = dataUrl; chipImg.src = dataUrl; chip.style.display = 'block';
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

  // Mapa
  {% if route %}
    const route = {{ route|tojson }};
    const map = L.map('map');
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
    }).addTo(map);
    const user = [route.user_lat, route.user_lng];
    const store = [route.store_lat, route.store_lng];
    const poly = L.polyline(route.geometry.map(p => [p[1], p[0]]), { weight: 5, color:'#2F6BFF' }).addTo(map);
    L.marker(user).addTo(map).bindPopup("Você");
    L.marker(store).addTo(map).bindPopup(route.store_name);
    const bounds = L.latLngBounds([user, store, ...poly.getLatLngs()]);
    map.fitBounds(bounds, { padding: [40,40] });
  {% endif %}
</script>
</body>
</html>
"""

# ================== Lado Python (igual ao anterior) ==================

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

def identify_product_with_gpt4omini(image_data_uri: str, user_locale: str = "pt-BR", user_hint: str = "") -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    system_prompt = ("Você é um assistente especialista em identificar produtos a partir de imagens para e-commerce. "
                     "Responda em JSON válido, sem texto fora do JSON.")
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
    r = requests.post(OPENAI_CHAT_URL, headers=headers, data=json.dumps(payload), timeout=60)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, flags=re.S)
        if m:
            try: return json.loads(m.group(0))
            except Exception: pass
    return {"product_name":None,"brand":None,"model":None,"category":None,"keywords":[],"suggested_query":None,"confidence_pct":None}

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
    provider_used = SHOP_PROVIDER
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

PHYSICAL_RETAILERS = {
    "magazineluiza.com.br": "Magazine Luiza",
    "casasbahia.com.br": "Casas Bahia",
    "kalunga.com.br": "Kalunga",
    "fastshop.com.br": "Fast Shop",
    "carrefour.com.br": "Carrefour",
}
def domain_to_brand(domain: str) -> Optional[str]:
    return PHYSICAL_RETAILERS.get((domain or "").lower())

def bbox_from_point(lat: float, lng: float, delta_deg: float = 0.7) -> Tuple[float, float, float, float]:
    return (lng - delta_deg, lat - delta_deg, lng + delta_deg, lat + delta_deg)

def nominatim_search(name: str, lat: float, lng: float, limit: int = 10) -> List[Dict[str, Any]]:
    minx, miny, maxx, maxy = bbox_from_point(lat, lng, 0.7)
    params = {"format":"jsonv2","q":name,"limit":str(limit),"viewbox":f"{minx},{maxy},{maxx},{miny}","bounded":1,"countrycodes":"br","addressdetails":1,"extratags":1}
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

def compute_nearest_route(lat: float, lng: float, shops: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    brands = {domain_to_brand(s.get("domain")) for s in (shops or []) if domain_to_brand(s.get("domain"))}
    if not brands: brands = {"Magazine Luiza","Casas Bahia","Kalunga","Fast Shop","Carrefour"}
    candidates = []
    for name in brands:
        for place in nominatim_search(name, lat, lng, limit=8):
            try: slat = float(place.get("lat")); slng = float(place.get("lon"))
            except Exception: continue
            dist_guess = haversine_km(lat, lng, slat, slng)
            candidates.append({"store_name": place.get("display_name") or name,"brand": name,"lat": slat,"lng": slng,"dist_guess": dist_guess})
    if not candidates: return None
    candidates.sort(key=lambda x: x["dist_guess"])
    best = None
    for c in candidates[:4]:
        r = osrm_route(lat, lng, c["lat"], c["lng"])
        if not r: continue
        item = {"store_name": c["brand"],"store_lat": c["lat"],"store_lng": c["lng"],"user_lat": lat,"user_lng": lng,
                "distance_km": r["distance_km"],"duration_min": int(r["duration_min"]),"geometry": r["geometry"]}
        if (best is None) or (item["duration_min"] < best["duration_min"]): best = item
    return best

@app.route("/", methods=["GET"])
def index():
    return render_template_string(PAGE,
        model_name="gpt-4o-mini",
        provider=SHOP_PROVIDER,
        last_query=None, me_thumb=None, result=None, shops=None, route=None
    )

@app.route("/analyze", methods=["POST"])
def analyze():
    user_q = (request.form.get("q") or "").strip()
    img_b64 = (request.form.get("image_base64") or "").strip()
    thumb_b64 = (request.form.get("thumb_base64") or "").strip()
    f = request.files.get("image")
    lat = request.form.get("lat"); lng = request.form.get("lng")

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
        if not user_q: return redirect(url_for("index"))
        query = user_q

    shops, provider_used = find_shops(query, user_locale="pt-BR")

    route = None
    try:
        if lat and lng:
            route = compute_nearest_route(float(lat), float(lng), shops)
    except Exception as e:
        print("ROUTE_ERROR:", e); route = None

    return render_template_string(PAGE,
        model_name="gpt-4o-mini",
        provider=provider_used,
        last_query=user_q if user_q else query,
        me_thumb=me_thumb_dataurl,
        result=info,
        shops=shops,
        route=route
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
