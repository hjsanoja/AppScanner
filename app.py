import streamlit as st
import requests
from lxml import html
from urllib.parse import urljoin

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
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE SCRAPING (El Cerebro Mejorado) ---
def buscar_producto(sku):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    base_url = "https://depofit.com"
    
    # PASO 1: BUSCAR EL PRODUCTO
    # Construimos la URL de búsqueda con el código que ingresaste
    url_busqueda = f"https://depofit.com/search?q={sku}"
    
    try:
        # Descargamos la página de búsqueda
        response_busqueda = requests.get(url_busqueda, headers=headers)
        tree_busqueda = html.fromstring(response_busqueda.content)
        
        # Buscamos enlaces que contengan "/products/"
        # Explicación: Buscamos dentro de 'main' o 'div' para evitar enlaces del menú superior
        # Tomamos el primer enlace que parezca un producto real
        enlaces_productos = tree_busqueda.xpath('//a[contains(@href, "/products/")]/@href')
        
        url_producto = None
        
        # Filtramos enlaces duplicados o irrelevantes (limpieza básica)
        for link in enlaces_productos:
            # Ignoramos enlaces que sean solo texto o vacíos
            if len(link) > 5:
                # Si el link es relativo (ej: /products/zapato), lo convertimos a absoluto
                url_producto = urljoin(base_url, link)
                break # Nos quedamos con el primero que encontramos
        
        if not url_producto:
            # Si no encontramos ningún enlace de producto en la búsqueda
            return {"modo": "busqueda_externa", "url": url_busqueda}

        # PASO 2: EXTRAER DATOS DEL PRODUCTO ENCONTRADO
        page = requests.get(url_producto, headers=headers)
        tree = html.fromstring(page.content)
        
        datos = {"modo": "encontrado"}
        
        # Título
        titulo = tree.xpath('//h1/text()')
        datos['titulo'] = titulo[0].strip() if titulo else "Título no detectado"
        
        # Precio (Buscamos símbolos de dinero o clases de precio)
        precios = tree.xpath('//span[contains(@class, "price")]/text() | //*[contains(text(), "$")]/text()')
        precios_limpios = [p.strip() for p in precios if "$" in p and len(p) < 20]
        datos['precio'] = precios_limpios[0] if precios_limpios else "Consultar Web"
        
        # Imagen
        imagen = tree.xpath('//meta[@property="og:image"]/@content')
        datos['imagen'] = imagen[0] if imagen else None
        
        # Modelo
        modelo_nodo = tree.xpath('//li[contains(., "Modelo")]//text()')
        if modelo_nodo:
            texto_modelo = "".join(modelo_nodo).replace("Modelo:", "").replace("Modelo", "").strip()
            datos['modelo'] = texto_modelo
        else:
            datos['modelo'] = "No especificado"
            
        datos['url'] = url_producto
        return datos

    except Exception as e:
        return {"modo": "error", "mensaje": f"Error técnico: {str(e)}"}

# --- INTERFAZ DE USUARIO ---

st.title("DepoScanner 👟")
st.write("Escanear o ingresar código de producto:")

codigo_input = st.text_input("SKU / Código", placeholder="Ej: 48.98721")

if st.button("BUSCAR PRODUCTO"):
    if not codigo_input:
        st.warning("⚠️ Por favor ingresa un código.")
    else:
        # Mostramos un spinner mientras Python hace el trabajo sucio
        with st.spinner(f'Buscando "{codigo_input}" en catálogo...'):
            resultado = buscar_producto(codigo_input)
        
        if resultado["modo"] == "error":
            st.error(resultado["mensaje"])
            
        elif resultado["modo"] == "busqueda_externa":
            st.warning(f"No encontré un producto automático para '{codigo_input}'.")
            st.link_button("🔎 Ver resultados manuales en Depofit", resultado["url"])
            
        elif resultado["modo"] == "encontrado":
            if resultado['imagen']:
                st.image(resultado['imagen'], use_column_width=True)
            
            st.markdown(f"### {resultado['titulo']}")
            st.markdown(f"<div class='price-tag'>{resultado['precio']}</div>", unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class='info-box'>
                <b>🏷️ Modelo detectado:</b> {resultado['modelo']}
            </div>
            """, unsafe_allow_html=True)
            
            st.write("")
            st.link_button("🔗 Ir al Producto", resultado['url'])

st.markdown("---")
st.caption("v2.0 • Auto-Discovery Mode")
