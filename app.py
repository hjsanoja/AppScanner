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
    /* Tarjeta general para comparación */
    .m3-card {
        background-color: #F3F6FC;
        border-radius: 24px;
        padding: 24px;
        margin-bottom: 16px;
    }
    /* Contenedor específico para cada tienda en la comparación */
    .store-card {
        background-color: #FFFFFF; /* Más claro para destacar */
        border-radius: 12px;
        padding: 15px;
        margin-top: 10px;
        border: 1px solid #E0E0E0;
        display: flex;
        justify-content: space-between;
        align-items: center;
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
    .price-value {
        font-size: 1.8em;
        font-weight: 700;
        color: #2E7D32; /* Verde para destacar el precio */
    }
    .error-tag {
        color: #D32F2F;
        font-weight: 500;
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
    """Convierte texto a minúsculas y elimina espacios para comparación."""
    if not texto: return ""
    return str(texto).lower().strip()

# --- HELPER: Decodificar Imagen ---
def leer_codigo_de_imagen(image_file):
    """Intenta leer un código de barras o QR de un archivo de imagen."""
    try:
        image = Image.open(image_file)
        codigos = decode(image)
        if codigos:
            return codigos[0].data.decode("utf-8")
    except Exception as e:
        st.error(f"Error leyendo imagen: {e}")
    return None

# --- LÓGICA DE SCRAPING DEPFIT ---
def buscar_depofit(sku, headers, base_url="https://depofit.com"):
    # Limpiamos el SKU de cualquier código de color/talla que pueda tener el usuario
    sku_buscado = normalizar_texto(sku)
    
    # Expresión Regular Flexible para buscar el SKU ignorando guiones/espacios
    sku_regex = re.escape(sku_buscado).replace(r'\-', '[\-\s]?').replace(r'\.', '[\.\s]?')
    
    url_busqueda = f"{base_url}/search?q={sku}"
    resultado = {"store": "Depofit.com", "status": "No Encontrado", "price": "---", "url": url_busqueda, "model": "N/A", "title": "N/A"}

    try:
        response_busqueda = requests.get(url_busqueda, headers=headers)
        tree_busqueda = html.fromstring(response_busqueda.content)
        
        # Buscamos enlaces de productos
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
            return resultado

        # Verificamos los 3 primeros candidatos para evitar falsos positivos
        for url_producto in urls_unicas[:3]: 
            page = requests.get(url_producto, headers=headers)
            tree = html.fromstring(page.content)
            
            titulo_texto = tree.xpath('//h1/text()')[0].strip() if tree.xpath('//h1/text()') else ""
            
            # USANDO LÓGICA ROBUSTA (en lugar del XPath dinámico del usuario)
            modelo_nodo = tree.xpath('//li[contains(., "Modelo")]//text()')
            modelo_texto = "".join(modelo_nodo).replace("Modelo:", "").replace("Modelo", "").strip() if modelo_nodo else ""
            
            texto_completo_producto = normalizar_texto(titulo_texto + " " + modelo_texto)
            
            # Verificación: ¿El SKU (flexible) se encuentra en la página del producto?
            es_match = bool(re.search(sku_regex, texto_completo_producto))
            
            if es_match:
                # Extracción de Precio (Estrategia Meta Data)
                meta_precio = tree.xpath('//meta[@property="og:price:amount"]/@content | //meta[@property="product:price:amount"]/@content')
                meta_moneda = tree.xpath('//meta[@property="og:price:currency"]/@content')
                price_value = meta_precio[0] if meta_precio else "---"
                currency_symbol = meta_moneda[0] if meta_moneda else "$"
                
                resultado['status'] = "Encontrado"
                resultado['price'] = f"{currency_symbol} {price_value}"
                resultado['url'] = url_producto
                resultado['model'] = modelo_texto
                resultado['title'] = titulo_texto
                
                imagen = tree.xpath('//meta[@property="og:image"]/@content')
                resultado['image'] = imagen[0] if imagen else None
                return resultado
        
        return resultado
    except Exception as e:
        resultado['status'] = f"Error: {e.__class__.__name__}"
        return resultado

# --- LÓGICA DE SCRAPING PLANETA SPORTS ---
def buscar_planetasports(sku, headers):
    base_url = "https://planetasports.com.ve"
    url_busqueda = f"{base_url}/category.php?keywords={sku}&search_in_description=1&provider=PlanetaSportsOfficial"
    resultado = {"store": "PlanetaSports.com.ve", "status": "No Encontrado", "price": "---", "url": url_busqueda, "model": "N/A", "title": "N/A"}
    sku_buscado = normalizar_texto(sku)
    
    try:
        response = requests.get(url_busqueda, headers=headers)
        tree = html.fromstring(response.content)

        # AJUSTE CLAVE: Buscamos cualquier enlace de producto en el área de contenido principal.
        producto_encontrado = tree.xpath('//div[@id="content"]//a[contains(@href, "productid=")]/@href')
        
        if not producto_encontrado:
             return resultado
        
        # Tomamos el primer producto encontrado
        url_producto = urljoin(base_url, producto_encontrado[0])
        
        # Accedemos a la página del producto para extraer los detalles
        page_producto = requests.get(url_producto, headers=headers)
        tree_producto = html.fromstring(page_producto.content)
        
        # 1. Extracción del Precio
        precio_nodo = tree_producto.xpath('//div[contains(@class, "product-info")]//div[contains(@class, "price")]/span/text()')
        
        # 2. Extracción de Título
        titulo_nodo = tree_producto.xpath('//h1/text()')
        
        # 3. Extracción de Modelo/SKU (Usando el XPath del usuario: //*[@id="description"]/text()[1])
        # Buscamos en la descripción completa, ya que el código de estilo puede estar ahí.
        description_text_nodes = tree_producto.xpath('//*[@id="description"]//text()')
        description_text = " ".join([t.strip() for t in description_text_nodes if t.strip()])
        
        # Intentar extraer el campo 'estilo' para el modelo
        estilo_nodo = tree_producto.xpath('//div[contains(@class, "product-info")]//div[contains(text(), "estilo")]/text()')
        model_value_full = next((d.strip() for d in estilo_nodo), description_text) # Usa descripción si no encuentra 'estilo'

        price_value = precio_nodo[0].strip() if precio_nodo else "---"
        title_value = titulo_nodo[0].strip() if titulo_nodo else "Título no detectado"
        
        # Verificación: Búsqueda flexible de SKU en el campo de estilo/descripción
        match_estilo = re.search(re.escape(sku_buscado), normalizar_texto(model_value_full))

        if match_estilo:
            resultado['status'] = "Encontrado"
            resultado['price'] = price_value
            resultado['url'] = url_producto
            # Limpiamos el texto de 'estilo:' si lo encontramos
            resultado['model'] = model_value_full.replace("estilo:", "").strip()
            resultado['title'] = title_value
        
        return resultado

    except Exception as e:
        resultado['status'] = f"Error: {e.__class__.__name__}"
        return resultado

# --- FUNCIÓN PRINCIPAL DE BÚSQUEDA Y COMPARACIÓN (RESTO DEL CÓDIGO SIN CAMBIOS) ---
def buscar_y_comparar(sku):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    depofit_data = buscar_depofit(sku, headers)
    planeta_data = buscar_planetasports(sku, headers)
    
    resultados = {
        "sku": sku,
        "depofit": depofit_data,
        "planeta": planeta_data
    }
    
    return resultados

# --- INTERFAZ DE USUARIO (UI) ---

st.markdown("<h2 style='text-align: center; font-weight: 700; margin-bottom: 20px;'>DepoScanner Pro 👟</h2>", unsafe_allow_html=True)

# --- SECCIÓN DE CÁMARA (Lógica de escaneo) ---
with st.expander("📸 Abrir Escáner de Cámara"):
    imagen_camara = st.camera_input("Toma una foto clara del código")

codigo_detectado = None

if imagen_camara:
    with st.spinner("Analizando código..."):
        codigo_leido = leer_codigo_de_imagen(imagen_camara)
        if codigo_leido:
            st.success(f"¡Código detectado! {codigo_leido}")
            codigo_detectado = codigo_leido
        else:
            st.warning("No se detectó ningún código legible en la imagen.")

# --- SECCIÓN DE BÚSQUEDA ---
valor_inicial = codigo_detectado if codigo_detectado else ""

codigo_input = st.text_input("", value=valor_inicial, placeholder="Escribe el SKU o escanea (Ej: 3ME10120664)...", label_visibility="collapsed")

st.write("") 

boton_presionado = st.button("Buscar y Comparar Precios")

if 'last_searched_code' not in st.session_state:
    st.session_state['last_searched_code'] = None

debe_buscar = boton_presionado or (codigo_detectado is not None and codigo_detectado != st.session_state.get('last_searched_code'))

if debe_buscar and codigo_input:
    st.session_state['last_searched_code'] = codigo_input 
    
    with st.spinner('Buscando información en ambas tiendas...'):
        resultados_comp = buscar_y_comparar(codigo_input)
    
    st.write("") 
    
    # --- MOSTRAR RESULTADOS CONSOLIDADOS ---
    
    depofit_data = resultados_comp['depofit']
    planeta_data = resultados_comp['planeta']
    
    fuente_principal = None
    if depofit_data['status'] == 'Encontrado':
        fuente_principal = depofit_data
    elif planeta_data['status'] == 'Encontrado':
        fuente_principal = planeta_data
    
    if fuente_principal and fuente_principal['status'] == 'Encontrado':
        st.markdown(f"""
        <div class='m3-card'>
            <div class='headline-small'>{fuente_principal['title']}</div>
            <div class='body-medium' style='color: #999;'>Modelo Buscado: <b>{codigo_input}</b></div>
        </div>
        """, unsafe_allow_html=True)
        
        if 'image' in fuente_principal and fuente_principal['image']:
            st.image(fuente_principal['image'], use_column_width=True)

    else:
         st.markdown(f"""<div class='m3-card'>
<div class='headline-small'>No se encontró coincidencia en ninguna tienda.</div>
<div class='body-medium' style='margin-top: 8px;'>El código <b>{codigo_input}</b> no fue verificado.</div>
</div>""", unsafe_allow_html=True)

    # 2. COMPARACIÓN DE PRECIOS
    
    st.markdown("### Comparativa de Precios")
    
    # Resultado Depofit
    if depofit_data['status'] == 'Encontrado':
        price_html = f"<span class='price-value'>{depofit_data['price']}</span>"
    else:
        price_html = f"<span class='error-tag'>{depofit_data['status']}</span>"
        
    st.markdown(f"""
    <div class='store-card'>
        <div style='font-weight: 500;'>{depofit_data['store']}</div>
        <div style='text-align: right;'>
            {price_html}<br>
            <a href='{depofit_data['url']}' target='_blank' style='font-size: 0.8em;'>Ver</a>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Resultado Planeta Sports
    if planeta_data['status'] == 'Encontrado':
        price_html = f"<span class='price-value'>{planeta_data['price']}</span>"
    else:
        price_html = f"<span class='error-tag'>{planeta_data['status']}</span>"
        
    st.markdown(f"""
    <div class='store-card'>
        <div style='font-weight: 500;'>{planeta_data['store']}</div>
        <div style='text-align: right;'>
            {price_html}<br>
            <a href='{planeta_data['url']}' target='_blank' style='font-size: 0.8em;'>Ver</a>
        </div>
    </div>
    """, unsafe_allow_html=True)


    st.markdown("---")
    st.caption("v10.0 • Verificación Final de SKU")

else:
    st.session_state['last_searched_code'] = None

st.markdown("<div style='text-align: center; color: #CCC; font-size: 12px;'>M3 Expressive UI</div>", unsafe_allow_html=True)
