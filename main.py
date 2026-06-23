import os
import subprocess
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Inicializar FastAPI
app = FastAPI(title="AURA API", version="0.4")

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
    instruccion = f"""
    Eres el 'Agente Estratega' de AURA. Escribe codigo Python para: {prompt_usuario}.
    Devuelve UNICAMENTE el codigo dentro de un bloque markdown (```python ... ```).
    """
    if error_previo:
        instruccion = f"""
        Eres el 'Agente Estratega' de AURA. Tu codigo anterior fallo.
        Codigo anterior: {codigo_previo}
        Error de ejecucion: {error_previo}
        Corrige el codigo. Devuelve UNICAMENTE el codigo corregido en un bloque markdown (```python ... ```).
        """
    
    respuesta = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": instruccion}],
        model="llama-3.3-70b-versatile",
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
    codigo_limpio = codigo_markdown.replace("```python", "").replace("```", "").strip()
    
    with open("temp_aura.py", "w") as f:
        f.write(codigo_limpio)
    
    resultado = subprocess.run(["python3", "temp_aura.py"], capture_output=True, text=True)
    
    if resultado.returncode == 0:
        return None, resultado.stdout 
    else:
        return resultado.stderr, None 

def procesar_tarea_aura(prompt_usuario):
    codigo_actual = None
    error_actual = None
    max_intentos = 3
    log_proceso = "[INICIO] AURA v0.4 API\n"
    
    for intento in range(max_intentos):
        log_proceso += f"\n[Intento {intento+1}] Estratega escribiendo/corrigiendo codigo..."
        codigo_actual = agente_estratega(prompt_usuario, error_actual, codigo_actual)
        
        log_proceso += "\n[Sandbox] Ejecutando codigo en entorno real..."
        error_actual, output = ejecutar_codigo(codigo_actual)
        
        if error_actual is None:
            log_proceso += "\n[Sandbox] Ejecucion exitosa. Sin errores."
            break
        else:
            log_proceso += "\n[Sandbox] Error encontrado. Reintentando..."
            
        if intento == max_intentos - 1 and error_actual:
            log_proceso += "\n[AURA] Se alcanzo el maximo de intentos sin exito."
    
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
    return {"status": "AURA API online", "version": "0.4"}

@app.post("/api/run")
def run_aura(tarea: TareaInput):
    if not tarea.prompt.strip():
        return {"error": "Prompt vacio"}
    resultado = procesar_tarea_aura(tarea.prompt)
    return resultado
