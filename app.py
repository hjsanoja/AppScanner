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

# Estilos CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        width: 100%;
        background-color: #000000;
        color: white;
        height: 3em;
        border-radius: 10px;
        font-weight: bold;
    }
    .price-tag {
        font-size: 2.5em;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 10px;
        margin-bottom: 10px;
    }
    .info-box {
        background-color: #e9ecef;
        padding: 15px;
        border-radius: 10px;
        margin-top: 10px;
    }
    .success-badge {
        background-color: #d4edda;
        color: #155724;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 0.8em;
        margin-bottom: 10px;
        display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER: Limpieza de Texto ---
def normalizar_texto(texto):
    """Quita espacios y convierte a minúsculas para comparar mejor"""
    if not texto: return ""
    return str(texto).lower().strip()

# --- LÓGICA DE SCRAPING (Cerebro v4.0 - Verificación Anti-Falsos Positivos) ---
def buscar_producto(sku):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    base_url = "https://depofit.com"
    sku_buscado = normalizar_texto(sku)
    
    # URL de búsqueda
    url_busqueda = f"https://depofit.com/search?q={sku}"
    
    try:
        response_busqueda = requests.get(url_busqueda, headers=headers)
        tree_busqueda = html.fromstring(response_busqueda.content)
        
        # ESTRATEGIA: Obtener VARIOS candidatos, no solo el primero
        # Buscamos enlaces dentro de 'main' para evitar menú/footer
        candidatos = tree_busqueda.xpath('//main//a[contains(@href, "/products/")]/@href')
        
        # Si no hay 'main', fallback al body
        if not candidatos:
            candidatos = tree_busqueda.xpath('//body//a[contains(@href, "/products/")]/@href')

        # Limpiamos duplicados manteniendo el orden
        urls_unicas = []
        seen = set()
        for link in candidatos:
            full_url = urljoin(base_url, link)
            if full_url not in seen:
                urls_unicas.append(full_url)
                seen.add(full_url)
        
        if not urls_unicas:
            return {"modo": "busqueda_externa", "url": url_busqueda}

        # --- BUCLE DE VERIFICACIÓN ---
        # Revisamos los primeros 3 productos encontrados para ver cuál es el correcto.
        # Esto evita que tomemos una "Recomendación" por error.
        
        for i, url_producto in enumerate(urls_unicas[:3]):
            # Descargar página del producto candidato
            page = requests.get(url_producto, headers=headers)
            tree = html.fromstring(page.content)
            
            # Extraer datos básicos para verificar
            titulo = tree.xpath('//h1/text()')
            titulo_texto = titulo[0].strip() if titulo else ""
            
            modelo_nodo = tree.xpath('//li[contains(., "Modelo")]//text()')
            modelo_texto = "".join(modelo_nodo).replace("Modelo:", "").replace("Modelo", "").strip() if modelo_nodo else ""
            
            texto_pagina = page.text.lower() # Todo el HTML para búsqueda bruta si falla lo demás
            
            # --- CRITERIO DE VERDAD: ¿Es este el producto que busca el usuario? ---
            es_match = False
            
            # 1. Coincidencia en Modelo (La más fuerte)
            if sku_buscado in normalizar_texto(modelo_texto):
                es_match = True
            # 2. Coincidencia en Título
            elif sku_buscado in normalizar_texto(titulo_texto):
                es_match = True
            # 3. Coincidencia en URL
            elif sku_buscado in normalizar_texto(url_producto):
                es_match = True
            # 4. Fallback: ¿Aparece el código varias veces en el cuerpo de la página?
            elif texto_pagina.count(sku_buscado) > 0:
                # Es un match débil, pero válido si no hay nada mejor
                es_match = True
            
            if es_match:
                # ¡ENCONTRADO! Extraemos el resto de datos y retornamos
                return extraer_precio_e_imagen(tree, url_producto, titulo_texto, modelo_texto, sku)
        
        # Si terminamos el bucle y ninguno coincidió
        return {"modo": "no_encontrado_exacto", "url": url_busqueda}

    except Exception as e:
        return {"modo": "error", "mensaje": f"Error técnico: {str(e)}"}

def extraer_precio_e_imagen(tree, url, titulo, modelo, sku_original):
    """Función auxiliar para limpiar el código principal"""
    datos = {"modo": "encontrado", "url": url, "titulo": titulo, "modelo": modelo}
    
    # --- PRECIO (Lógica Meta Data) ---
    precio_encontrado = None
    
    # 1. Metadatos (Prioridad Alta)
    meta_precio = tree.xpath('//meta[@property="og:price:amount"]/@content | //meta[@property="product:price:amount"]/@content')
    meta_moneda = tree.xpath('//meta[@property="og:price:currency"]/@content')
    
    if meta_precio:
        simbolo = meta_moneda[0] if meta_moneda else "$"
        precio_encontrado = f"{simbolo} {meta_precio[0]}"
    
    # 2. Fallback visual
    if not precio_encontrado:
        precios_oferta = tree.xpath('//span[contains(@class, "price-item--sale")]/text()')
        if precios_oferta:
            precio_encontrado = precios_oferta[0].strip()
            
    if not precio_encontrado:
        # Último recurso: buscar cualquier precio
        precios = tree.xpath('//span[contains(@class, "price")]/text()')
        precios_limpios = [p.strip() for p in precios if "$" in p]
        precio_encontrado = precios_limpios[0] if precios_limpios else "Consultar Web"

    datos['precio'] = precio_encontrado
    
    # --- IMAGEN ---
    imagen = tree.xpath('//meta[@property="og:image"]/@content')
    datos['imagen'] = imagen[0] if imagen else None
    
    return datos

# --- INTERFAZ DE USUARIO ---

st.title("DepoScanner 👟")
st.write("Escanear o ingresar código de producto:")

codigo_input = st.text_input("SKU / Código", placeholder="Ej: HV6341-702")

if st.button("BUSCAR PRODUCTO"):
    if not codigo_input:
        st.warning("⚠️ Por favor ingresa un código.")
    else:
        with st.spinner(f'Analizando catálogo para "{codigo_input}"...'):
            resultado = buscar_producto(codigo_input)
        
        if resultado["modo"] == "error":
            st.error(resultado["mensaje"])
            
        elif resultado["modo"] == "busqueda_externa" or resultado["modo"] == "no_encontrado_exacto":
            st.warning(f"No encontré una coincidencia EXACTA para '{codigo_input}'.")
            st.info("Es posible que la web muestre productos recomendados en lugar del resultado.")
            st.link_button("🔎 Ver resultados en Depofit.com", resultado["url"])
            
        elif resultado["modo"] == "encontrado":
            # Badge de confirmación
            st.markdown(f"<div class='success-badge'>✅ Coincidencia verificada</div>", unsafe_allow_html=True)
            
            if resultado['imagen']:
                st.image(resultado['imagen'], use_column_width=True)
            
            st.markdown(f"### {resultado['titulo']}")
            st.markdown(f"<div class='price-tag'>{resultado['precio']}</div>", unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class='info-box'>
                <b>🏷️ Modelo:</b> {resultado['modelo']}<br>
                <small style='color:gray'>SKU Buscado: {codigo_input}</small>
            </div>
            """, unsafe_allow_html=True)
            
            st.write("")
            st.link_button("🔗 Ir al Producto", resultado['url'])

st.markdown("---")
st.caption("v4.0 • Verificación de Resultados")
