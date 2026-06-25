import os
import subprocess
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Inicializar FastAPI
app = FastAPI(title="AURA API", version="0.5")

# Configurar CORS para permitir que el frontend de Vercel/Netlify se conecte
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En produccion, aqui ira tu URL de Vercel
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar Groq (Usa variables de entorno del servidor)
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Modelo de datos de entrada
class TareaInput(BaseModel):
    prompt: str

# ==========================================
# AGENTES Y SANDBOX
# ==========================================
def agente_estratega(prompt_usuario, error_previo=None, codigo_previo=None):
    system_instruccion = """
    Eres el 'Agente Estratega' de AURA. 
    Debes devolver UNICAMENTE un objeto JSON valido con las llaves "html", "css" y "js".
    - En "html" pon el contenido del body (sin <body> ni <html> tags, solo el contenido interno como <button> etc).
    - En "css" pon las reglas de estilo.
    - En "js" pon el codigo JavaScript.
    Si un lenguaje no es necesario, devuelve un string vacio para esa llave.
    No incluyas texto adicional, solo el JSON.
    """
    user_instruccion = f"Escribe codigo para: {prompt_usuario}"
    if error_previo:
        user_instruccion = f"Tu codigo anterior fallo. Error: {error_previo}. Corrigelo y devuelve el JSON."

    respuesta = groq_client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_instruccion},
            {"role": "user", "content": user_instruccion}
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"}
    )
    return respuesta.choices[0].message.content

def agente_critico_tutor(codigo_final, prompt_original):
    instruccion = f"""
    Eres el 'Agente Critico y Tutor' de AURA. El siguiente codigo ya fue ejecutado y funciona perfectamente.
    Tarea: {prompt_original}
    Codigo funcional: {codigo_final}
    
    METODO FEYNMAN (OBLIGATORIO): Explica la logica principal en EXACTAMENTE 3 lineas simples, 
    como si se lo explicaras a un adolescente de 17 anos. Sin tecnicismos.
    """
    respuesta = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": instruccion}],
        model="llama-3.1-8b-instant",
    )
    return respuesta.choices[0].message.content

def ejecutar_codigo(codigo_markdown):
    # Extraer el lenguaje del código markdown (ej: ```python, ```html)
    match = re.search(r"```(\w+)", codigo_markdown)
    lenguaje = match.group(1).lower() if match else "python"

    # Preservar el contenido completo del JSON para lógica de respuesta web posterior
    # El JSON puede aparecer como código separado o como una cadena simple
    import json
    json_data = None
    
    # Intentar parsear como JSON
    try:
        parsed = json.loads(codigo_markdown)
        if isinstance(parsed, dict) and all(key in parsed for key in ["html", "css", "js"]):
            json_data = parsed
    except:
        pass

    # Limpiar el código quitando las etiquetas markdown
    codigo_limpio = re.sub(r"```\w*\n?", "", codigo_markdown).replace("```", "").strip()

    if lenguaje in ["python", "py"]:
        extension = "py"
        comando = ["python3", f"temp_aura.{extension}"]
        # Ejecutar solo si es Python o Bash
        with open(f"temp_aura.{extension}", "w") as f:
            f.write(codigo_limpio)
        
        resultado = subprocess.run(comando, capture_output=True, text=True)
        
        if resultado.returncode == 0:
            return None, resultado.stdout, None
        else:
            return resultado.stderr, None, None
    else:
        # Lenguajes que no se pueden ejecutar directamente en un sandbox de Python
        # Se devuelve el JSON cuando está disponible
        mensaje = f"[Sandbox] Lenguaje '{lenguaje}' detectado. Vista previa en navegador habilitada debajo del codigo."
        return None, mensaje, json_data 

def consolidar_web(codigo_markdown):
    if not codigo_markdown:
        return codigo_markdown

    codigo_limpio = re.sub(r"```\w*\n?", "", codigo_markdown).replace("```", "").strip()

    if "<!DOCTYPE html>" in codigo_limpio:
        return codigo_limpio

    bloque_html = re.search(r"```(html|htm)\s*\n?(.*?)```", codigo_limpio, re.DOTALL)
    bloque_css = re.search(r"```css\s*\n?(.*?)```", codigo_limpio, re.DOTALL)
    bloque_js = re.search(r"```(javascript|js)\s*\n?(.*?)```", codigo_limpio, re.DOTALL)

    html_content = bloque_html.group(2) if bloque_html else ""
    css_content = bloque_css.group(1) if bloque_css else ""
    js_content = bloque_js.group(2) if bloque_js else ""

    if not html_content:
        html_content = ""

    html_document = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AURA Web Output</title>
"""

    if css_content:
        html_document += f"""    <style>
{css_content}
    </style>
"""

    html_document += """
</head>
<body>
"""

    if html_content:
        html_document += f"{html_content}\n"

    if js_content:
        html_document += f"""
    <script>
{js_content}
    </script>
"""

    html_document += """
</body>
</html>
"""

    return html_document.strip()

def procesar_tarea_aura(prompt_usuario):
    codigo_actual = None
    error_actual = None
    max_intentos = 3
    log_proceso = "[INICIO] AURA v0.5 API\n"
    
    for intento in range(max_intentos):
        log_proceso += f"\n[Intento {intento+1}] Estratega escribiendo/corrigiendo codigo..."
        codigo_actual = agente_estratega(prompt_usuario, error_actual, codigo_actual)
        
        log_proceso += "\n[Sandbox] Ejecutando codigo en entorno real..."
        error_actual, output, json_data = ejecutar_codigo(codigo_actual)
        
        # Si obtenemos JSON, usarlo inmediatamente (la IA ya lo construyó correctamente)
        if json_data is not None:
            log_proceso += "\n[Sandbox] JSON recibido de la IA. Construyendo HTML..."
            html_part = json_data.get("html", "")
            css_part = json_data.get("css", "")
            js_part = json_data.get("js", "")
            
            # Construir documento HTML unico CORREGIDO
            codigo_actual = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Botón Rojo con Confeti</title>
    <style>{css_part}</style>
</head>
<body>
    {html_part}
    <script>{js_part}</script>
</body>
</html>"""
            # No es necesario ejecutar en sandbox si ya tenemos el HTML final
            break
        
        if error_actual is None:
            log_proceso += "\n[Sandbox] Ejecucion exitosa. Sin errores."
            break
        else:
            log_proceso += "\n[Sandbox] Error encontrado. Reintentando..."
            
        if intento == max_intentos - 1 and error_actual:
            log_proceso += "\n[AURA] Se alcanzo el maximo de intentos sin exito."

    import json
    codigo_limpio_json = codigo_actual.replace("```json", "").replace("```", "").strip()
    try:
        data_json = json.loads(codigo_limpio_json)
        html_part = data_json.get("html", "")
        css_part = data_json.get("css", "")
        js_part = data_json.get("js", "")
        
        codigo_actual = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <style>
    {css_part}
    </style>
</head>
<body>
    {html_part}
    <script>
    {js_part}
    </script>
</body>
</html>"""
    except Exception:
        pass

    explicacion = agente_critico_tutor(codigo_actual, prompt_usuario)
    salida_consola = output if output else "No hubo salida en consola."
    
    return {
        "log": log_proceso,
        "codigo": codigo_actual,
        "consola": salida_consola,
        "explicacion": explicacion
    }

# ==========================================
# ENDPOINTS DE LA API
# ==========================================
@app.get("/")
def read_root():
    return {"status": "AURA API online", "version": "0.5"}

@app.post("/api/run")
def run_aura(tarea: TareaInput):
    if not tarea.prompt.strip():
        return {"error": "Prompt vacio"}
    resultado = procesar_tarea_aura(tarea.prompt)
    return resultado
