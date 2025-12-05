import streamlit as st
import requests
from lxml import html

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="DepoFit Scanner",
    page_icon="👟",
    layout="centered"
)

# Estilos CSS personalizados para que se vea bien en móviles
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
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

# --- LÓGICA DE SCRAPING (El Cerebro) ---
def buscar_producto(sku):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # 1. Búsqueda: Intenta encontrar el producto
    # Nota: Si Depofit tiene una URL predecible para búsqueda, la usamos.
    # Como el ejemplo directo es difícil de adivinar sin buscar primero,
    # aquí simulamos que si es el código de ejemplo, vamos directo a la URL conocida.
    # Para otros, enviamos a la página de búsqueda general.
    
    if sku.strip() == "48.98721":
        url = "https://depofit.com/products/zapatos-de-tenis-para-caballero-the-roger-pro"
    else:
        # Aquí intentamos construir una URL de búsqueda genérica
        # Si Depofit no permite scraping directo de la búsqueda, esto mostrará el enlace para que el usuario haga clic.
        url_busqueda = f"https://depofit.com/search?q={sku}"
        return {"modo": "busqueda_externa", "url": url_busqueda}

    try:
        page = requests.get(url, headers=headers)
        tree = html.fromstring(page.content)
        
        # 2. Extracción de datos (Usando XPaths Robustos)
        datos = {"modo": "encontrado"}
        
        # Título
        titulo = tree.xpath('//h1/text()')
        datos['titulo'] = titulo[0].strip() if titulo else "Título no detectado"
        
        # Precio (Busca clases comunes de precio o símbolo $)
        precios = tree.xpath('//span[contains(@class, "price")]/text() | //*[contains(text(), "$")]/text()')
        # Filtramos textos que tengan '$' y sean cortos (para evitar oraciones largas)
        precios_limpios = [p.strip() for p in precios if "$" in p and len(p) < 20]
        datos['precio'] = precios_limpios[0] if precios_limpios else "No disponible"
        
        # Imagen (Busca la metaetiqueta social, suele ser la mejor calidad)
        imagen = tree.xpath('//meta[@property="og:image"]/@content')
        datos['imagen'] = imagen[0] if imagen else None
        
        # Modelo (Específico para tu necesidad)
        # Busca cualquier elemento de lista que diga "Modelo"
        modelo_nodo = tree.xpath('//li[contains(., "Modelo")]//text()')
        if modelo_nodo:
             # Une el texto y quita la palabra "Modelo:"
            texto_modelo = "".join(modelo_nodo).replace("Modelo:", "").replace("Modelo", "").strip()
            datos['modelo'] = texto_modelo
        else:
            datos['modelo'] = "No especificado"
            
        datos['url'] = url
        return datos

    except Exception as e:
        return {"modo": "error", "mensaje": f"Error conectando: {str(e)}"}

# --- INTERFAZ DE USUARIO (La Cara) ---

st.title("DepoScanner 👟")
st.write("Escanear o ingresar código de producto:")

# Input grande
codigo_input = st.text_input("SKU / Código", placeholder="Ej: 48.98721")

if st.button("BUSCAR PRODUCTO"):
    if not codigo_input:
        st.warning("⚠️ Por favor ingresa un código.")
    else:
        with st.spinner('Conectando con Depofit...'):
            resultado = buscar_producto(codigo_input)
        
        if resultado["modo"] == "error":
            st.error(resultado["mensaje"])
            
        elif resultado["modo"] == "busqueda_externa":
            st.warning(f"El producto '{codigo_input}' no tiene enlace directo configurado en esta demo.")
            st.markdown("Pero puedes buscarlo directamente aquí:")
            st.link_button("🔎 Buscar en Depofit.com", resultado["url"])
            
        elif resultado["modo"] == "encontrado":
            # --- MOSTRAR RESULTADOS ---
            
            # Imagen
            if resultado['imagen']:
                st.image(resultado['imagen'], use_column_width=True)
            
            # Título y Precio
            st.markdown(f"### {resultado['titulo']}")
            st.markdown(f"<div class='price-tag'>{resultado['precio']}</div>", unsafe_allow_html=True)
            
            # Caja de detalles (Modelo)
            st.markdown(f"""
            <div class='info-box'>
                <b>🏷️ Modelo detectado:</b> {resultado['modelo']}
            </div>
            """, unsafe_allow_html=True)
            
            st.write("") # Espacio
            st.link_button("🔗 Ver en Web Oficial", resultado['url'])

# Pie de página simple
st.markdown("---")
st.caption("v1.0 • Scraper Web Móvil")
