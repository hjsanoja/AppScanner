import streamlit as st
import requests
from lxml import html
from urllib.parse import urljoin
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="DepoFit Scanner",
    page_icon="👟",
    layout="centered"
)

# --- DISEÑO MATERIAL 3 EXPRESSIVE (CSS) ---
st.markdown("""
    <style>
    /* Importamos Roboto (Fuente estándar de Android) */
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

    /* Reset básico */
    html, body, [class*="css"] {
        font-family: 'Roboto', sans-serif;
        color: #1F1F1F;
    }

    /* Fondo de la App */
    .stApp {
        background-color: #FFFFFF;
    }

    /* INPUT DE TEXTO (Estilo M3 Filled) */
    div[data-baseweb="input"] {
        background-color: #F3F6FC; /* Surface Container Low */
        border-radius: 28px; /* Extra redondeado */
        border: none;
        padding: 4px 8px;
    }
    div[data-baseweb="input"]:focus-within {
        background-color: #EDF2FA;
        box-shadow: inset 0 0 0 2px #000000;
    }

    /* BOTÓN (Estilo M3 Filled Button) */
    .stButton > button {
        width: 100%;
        background-color: #000000; /* Primary */
        color: #FFFFFF; /* On Primary */
        border-radius: 100px; /* Full Pill Shape */
        height: 56px; /* Altura estándar M3 */
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
    .stButton > button:active {
        transform: scale(0.98);
    }

    /* TARJETAS (Cards M3) */
    .m3-card {
        background-color: #F3F6FC; /* Surface Container */
        border-radius: 24px;
        padding: 24px;
        margin-bottom: 16px;
        transition: background-color 0.3s;
    }
    
    /* TIPOGRAFÍA */
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
        color: #444746; /* On Surface Variant */
    }

    /* CHIPS (Etiquetas) */
    .m3-chip {
        display: inline-flex;
        align-items: center;
        background-color: #C4EED0; /* Success Container */
        color: #072711; /* On Success Container */
        padding: 6px 16px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 16px;
        gap: 8px;
    }
    
    .m3-chip-icon {
        font-size: 16px;
    }

    /* Warning Card */
    .warning-card {
        background-color: #FFEBEE;
        color: #B71C1C;
        padding: 16px;
        border-radius: 16px;
        font-weight: 500;
    }

    /* Ocultar elementos nativos de Streamlit que ensucian */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- HELPER: Limpieza de Texto ---
def normalizar_texto(texto):
    if not texto: return ""
    return str(texto).lower().strip()

# --- LÓGICA DE SCRAPING (Sin Cambios - Funciona Perfecto) ---
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

        # Verificación
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

# Título minimalista
st.markdown("<h2 style='text-align: center; font-weight: 700; margin-bottom: 20px;'>DepoScanner</h2>", unsafe_allow_html=True)

# Input
codigo_input = st.text_input("", placeholder="Escribe el código SKU aquí...", label_visibility="collapsed")

# Espaciador visual
st.write("") 

# Botón
if st.button("Buscar Producto"):
    if not codigo_input:
        st.markdown("<div class='warning-card'>⚠️ Escribe un código primero</div>", unsafe_allow_html=True)
    else:
        with st.spinner(''):
            resultado = buscar_producto(codigo_input)
        
        st.write("") # Margen
        
        if resultado["modo"] == "error":
            st.error(resultado["mensaje"])
            
        elif resultado["modo"] == "busqueda_externa" or resultado["modo"] == "no_encontrado_exacto":
            # Eliminamos sangría para evitar bloque de código
            st.markdown(f"""<div class='m3-card'>
<div class='headline-small'>No hubo match exacto</div>
<div class='body-medium' style='margin-top: 8px;'>El código <b>{codigo_input}</b> no aparece directamente, pero puede estar en recomendados.</div>
<br>
<a href='{resultado["url"]}' target='_blank' style='text-decoration: none; color: #000000; font-weight: 500;'>
🔎 Ver resultados en Depofit &rarr;
</a>
</div>""", unsafe_allow_html=True)
            
        elif resultado["modo"] == "encontrado":
            # --- TARJETA DE RESULTADO PRINCIPAL ---
            # IMPORTANTE: HTML alineado a la izquierda sin sangría
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
            
            # Imagen fuera de la tarjeta de texto, para que luzca grande (estilo Instagram/M3)
            if resultado['imagen']:
                st.image(resultado['imagen'], use_column_width=True)
            
            # Botón flotante simulado (Link final)
            st.markdown(f"""<div style='text-align: center; margin-top: 20px;'>
<a href='{resultado["url"]}' target='_blank' 
style='background-color: #E8DEF8; color: #1D192B; padding: 12px 24px; border-radius: 100px; text-decoration: none; font-weight: 500; font-size: 14px;'>
Abrir en Web Oficial ↗
</a>
</div>""", unsafe_allow_html=True)

st.write("")
st.write("")
st.markdown("<div style='text-align: center; color: #CCC; font-size: 12px;'>M3 Expressive UI • v5.0</div>", unsafe_allow_html=True)
