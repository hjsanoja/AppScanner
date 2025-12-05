import streamlit as st
import requests
from lxml import html
from urllib.parse import urljoin
import re
from PIL import Image
from pyzbar.pyzbar import decode
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="DepoFit Scanner",
    page_icon="👟",
    layout="centered"
)

# --- DISEÑO MATERIAL 3 EXPRESSIVE (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Roboto', sans-serif;
        color: #1F1F1F;
    }
    .stApp {
        background-color: #FFFFFF;
    }
    div[data-baseweb="input"] {
        background-color: #F3F6FC;
        border-radius: 28px;
        border: none;
        padding: 4px 8px;
    }
    div[data-baseweb="input"]:focus-within {
        background-color: #EDF2FA;
        box-shadow: inset 0 0 0 2px #000000;
    }
    .stButton > button {
        width: 100%;
        background-color: #000000;
        color: #FFFFFF;
        border-radius: 100px;
        height: 56px;
        font-weight: 500;
        font-size: 16px;
        letter-spacing: 0.5px;
        border: none;
        transition: transform 0.1s, box-shadow 0.2s;
    }
    .stButton > button:hover {
        background-color: #333333;
        box-shadow: 0px 4px 8px rgba(0,0,0,0.2);
        transform: translateY(-1px);
    }
    .m3-card {
        background-color: #F3F6FC;
        border-radius: 24px;
        padding: 24px;
        margin-bottom: 16px;
    }
    .display-large {
        font-size: 57px;
        line-height: 64px;
        font-weight: 400;
        color: #1F1F1F;
        letter-spacing: -0.25px;
        margin: 10px 0 20px 0;
    }
    .headline-small {
        font-size: 24px;
        line-height: 32px;
        font-weight: 500;
        color: #1F1F1F;
    }
    .body-medium {
        font-size: 14px;
        line-height: 20px;
        color: #444746;
    }
    .m3-chip {
        display: inline-flex;
        align-items: center;
        background-color: #C4EED0;
        color: #072711;
        padding: 6px 16px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 16px;
        gap: 8px;
    }
    .warning-card {
        background-color: #FFEBEE;
        color: #B71C1C;
        padding: 16px;
        border-radius: 16px;
        font-weight: 500;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- HELPER: Limpieza de Texto ---
def normalizar_texto(texto):
    if not texto: return ""
    return str(texto).lower().strip()

# --- HELPER: Decodificar Imagen ---
def leer_codigo_de_imagen(image_file):
    try:
        # Abrir imagen con Pillow
        image = Image.open(image_file)
        # Decodificar códigos (QR o Barras)
        codigos = decode(image)
        if codigos:
            # Retornamos el primer código encontrado
            # .data viene en bytes, lo decodificamos a string
            return codigos[0].data.decode("utf-8")
    except Exception as e:
        st.error(f"Error leyendo imagen: {e}")
    return None

# --- LÓGICA DE SCRAPING ---
def buscar_producto(sku):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    base_url = "https://depofit.com"
    sku_buscado = normalizar_texto(sku)
    url_busqueda = f"https://depofit.com/search?q={sku}"
    
    try:
        response_busqueda = requests.get(url_busqueda, headers=headers)
        tree_busqueda = html.fromstring(response_busqueda.content)
        
        candidatos = tree_busqueda.xpath('//main//a[contains(@href, "/products/")]/@href')
        if not candidatos:
            candidatos = tree_busqueda.xpath('//body//a[contains(@href, "/products/")]/@href')

        urls_unicas = []
        seen = set()
        for link in candidatos:
            full_url = urljoin(base_url, link)
            if full_url not in seen:
                urls_unicas.append(full_url)
                seen.add(full_url)
        
        if not urls_unicas:
            return {"modo": "busqueda_externa", "url": url_busqueda}

        for i, url_producto in enumerate(urls_unicas[:3]):
            page = requests.get(url_producto, headers=headers)
            tree = html.fromstring(page.content)
            
            titulo = tree.xpath('//h1/text()')
            titulo_texto = titulo[0].strip() if titulo else ""
            
            modelo_nodo = tree.xpath('//li[contains(., "Modelo")]//text()')
            modelo_texto = "".join(modelo_nodo).replace("Modelo:", "").replace("Modelo", "").strip() if modelo_nodo else ""
            texto_pagina = page.text.lower()
            
            es_match = False
            if sku_buscado in normalizar_texto(modelo_texto): es_match = True
            elif sku_buscado in normalizar_texto(titulo_texto): es_match = True
            elif sku_buscado in normalizar_texto(url_producto): es_match = True
            elif texto_pagina.count(sku_buscado) > 0: es_match = True
            
            if es_match:
                return extraer_precio_e_imagen(tree, url_producto, titulo_texto, modelo_texto, sku)
        
        return {"modo": "no_encontrado_exacto", "url": url_busqueda}

    except Exception as e:
        return {"modo": "error", "mensaje": f"Error técnico: {str(e)}"}

def extraer_precio_e_imagen(tree, url, titulo, modelo, sku_original):
    datos = {"modo": "encontrado", "url": url, "titulo": titulo, "modelo": modelo}
    
    precio_encontrado = None
    meta_precio = tree.xpath('//meta[@property="og:price:amount"]/@content | //meta[@property="product:price:amount"]/@content')
    meta_moneda = tree.xpath('//meta[@property="og:price:currency"]/@content')
    
    if meta_precio:
        simbolo = meta_moneda[0] if meta_moneda else "$"
        precio_encontrado = f"{simbolo} {meta_precio[0]}"
    
    if not precio_encontrado:
        precios_oferta = tree.xpath('//span[contains(@class, "price-item--sale")]/text()')
        if precios_oferta: precio_encontrado = precios_oferta[0].strip()
            
    if not precio_encontrado:
        precios = tree.xpath('//span[contains(@class, "price")]/text()')
        precios_limpios = [p.strip() for p in precios if "$" in p]
        precio_encontrado = precios_limpios[0] if precios_limpios else "---"

    datos['precio'] = precio_encontrado
    imagen = tree.xpath('//meta[@property="og:image"]/@content')
    datos['imagen'] = imagen[0] if imagen else None
    return datos

# --- INTERFAZ DE USUARIO (UI) ---

st.markdown("<h2 style='text-align: center; font-weight: 700; margin-bottom: 20px;'>DepoScanner</h2>", unsafe_allow_html=True)

# --- SECCIÓN DE CÁMARA ---
# Usamos un expander para que la cámara no estorbe si no se usa
with st.expander("📸 Abrir Escáner de Cámara"):
    imagen_camara = st.camera_input("Toma una foto clara del código")

codigo_detectado = None

# Si hay foto, intentamos leerla
if imagen_camara:
    with st.spinner("Analizando código..."):
        codigo_leido = leer_codigo_de_imagen(imagen_camara)
        if codigo_leido:
            st.success(f"¡Código detectado! {codigo_leido}")
            codigo_detectado = codigo_leido
        else:
            st.warning("No se detectó ningún código legible en la imagen.")

# --- SECCIÓN DE BÚSQUEDA ---
# Si la cámara detectó algo, lo usamos por defecto. Si no, campo vacío.
valor_inicial = codigo_detectado if codigo_detectado else ""

# Input manual (se llena solo si la cámara detecta algo)
# key="sku_input" es importante para manejar el estado
codigo_input = st.text_input("", value=valor_inicial, placeholder="Escribe el SKU o escanea...", label_visibility="collapsed")

st.write("") 

# Botón de búsqueda (automático si viene de cámara)
boton_presionado = st.button("Buscar Producto")

# Lógica de disparo: Si apretó botón O si la cámara acaba de detectar algo
debe_buscar = boton_presionado or (codigo_detectado is not None)

if debe_buscar:
    if not codigo_input:
        st.markdown("<div class='warning-card'>⚠️ Escribe o escanea un código</div>", unsafe_allow_html=True)
    else:
        with st.spinner('Buscando información...'):
            resultado = buscar_producto(codigo_input)
        
        st.write("") 
        
        if resultado["modo"] == "error":
            st.error(resultado["mensaje"])
            
        elif resultado["modo"] == "busqueda_externa" or resultado["modo"] == "no_encontrado_exacto":
            st.markdown(f"""<div class='m3-card'>
<div class='headline-small'>No hubo match exacto</div>
<div class='body-medium' style='margin-top: 8px;'>El código <b>{codigo_input}</b> no aparece directamente.</div>
<br>
<a href='{resultado["url"]}' target='_blank' style='text-decoration: none; color: #000000; font-weight: 500;'>
🔎 Ver resultados en Depofit &rarr;
</a>
</div>""", unsafe_allow_html=True)
            
        elif resultado["modo"] == "encontrado":
            st.markdown(f"""<div class='m3-card'>
<div class='m3-chip'>
<span class='m3-chip-icon'>✓</span> Verificado
</div>
<div class='headline-small'>{resultado['titulo']}</div>
<div class='display-large'>{resultado['precio']}</div>
<div style='background-color: #FFFFFF; padding: 16px; border-radius: 12px; margin-top: 16px;'>
<div class='body-medium'><b>Modelo:</b> {resultado['modelo']}</div>
<div class='body-medium' style='color: #999;'>SKU: {codigo_input}</div>
</div>
</div>""", unsafe_allow_html=True)
            
            if resultado['imagen']:
                st.image(resultado['imagen'], use_column_width=True)
            
            st.markdown(f"""<div style='text-align: center; margin-top: 20px;'>
<a href='{resultado["url"]}' target='_blank' 
style='background-color: #E8DEF8; color: #1D192B; padding: 12px 24px; border-radius: 100px; text-decoration: none; font-weight: 500; font-size: 14px;'>
Abrir en Web Oficial ↗
</a>
</div>""", unsafe_allow_html=True)

st.write("")
st.write("")
st.markdown("<div style='text-align: center; color: #CCC; font-size: 12px;'>M3 Expressive UI • v6.0 Camera Enabled</div>", unsafe_allow_html=True)
