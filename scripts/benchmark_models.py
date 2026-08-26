import asyncio
import json
import sys
import time
import httpx

sys.stdout.reconfigure(encoding="utf-8")

OLLAMA_URL = "http://localhost:11434"

PROMPTS = [
    {
        "name": "1. Clasificación Hermes (Rápida)",
        "system": "Eres Hermes. Responde SIEMPRE en JSON: {\"agente\": \"curador|estudio|sync|plan|hermes\", \"instruccion\": \"...\", \"razon\": \"...\"}",
        "prompt": "Miguel dice: 'Anota esto: Protocolo WebSockets vs HTTP/2 streaming'",
        "temperature": 0.1,
    },
    {
        "name": "2. Categorización Curador (JSON Complejo)",
        "system": "Categoriza la nota del usuario. Responde SOLO en JSON con formato: {\"area_sugerida\": \"...\", \"tags\": [\"tag1\", \"tag2\"], \"razon\": \"...\"}",
        "prompt": "Nota: 'El algoritmo Raft resuelve el consenso distribuido mediante elección de líder y replicación de log garantizando consistencia fuerte.'",
        "temperature": 0.3,
    },
    {
        "name": "3. Desglose Estratégico AgentePlan",
        "system": "Desglosa la meta en JSON: {\"objetivo\": {\"titulo\": \"...\", \"area\": \"...\"}, \"proyectos\": [{\"titulo\": \"...\", \"tareas\": [\"...\"]}], \"razon\": \"...\"}",
        "prompt": "Meta: 'Quiero dominar concurrencia en Python (asyncio, multiprocessing) antes del examen final.'",
        "temperature": 0.3,
    },
]

async def benchmark():
    print("=" * 70, flush=True)
    print("⚡ BENCHMARK DE VELOCIDAD Y RENDIMIENTO DE MODELOS OLLAMA", flush=True)
    print("=" * 70, flush=True)

    async with httpx.AsyncClient(timeout=180.0) as client:
        tags_res = await client.get(f"{OLLAMA_URL}/api/tags")
        if tags_res.status_code != 200:
            print(f"❌ Error al conectar con Ollama en {OLLAMA_URL}", flush=True)
            return

        all_models = [m["name"] for m in tags_res.json().get("models", [])]
        llm_models = [m for m in all_models if "embed" not in m and "gemma4" not in m]

        print(f"\nModelos a probar: {llm_models}\n", flush=True)
        resumen = {}

        for model in llm_models:
            print(f"\n{'─'*60}", flush=True)
            print(f"🔬 Evaluando modelo: {model}", flush=True)
            print(f"{'─'*60}", flush=True)

            model_stats = []
            for p_info in PROMPTS:
                print(f"  ▶ Prueba: {p_info['name']} ...", end=" ", flush=True)
                payload = {
                    "model": model,
                    "prompt": p_info["prompt"],
                    "system": p_info["system"],
                    "stream": False,
                    "options": {"temperature": p_info["temperature"], "num_predict": 120}
                }

                t_start = time.perf_counter()
                try:
                    res = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
                    t_total = time.perf_counter() - t_start

                    if res.status_code == 200:
                        data = res.json()
                        eval_count = data.get("eval_count", 0)
                        eval_duration = data.get("eval_duration", 0) / 1e9
                        tps = (eval_count / eval_duration) if eval_duration > 0 else 0
                        response_text = data.get("response", "").strip()

                        is_json = False
                        try:
                            json.loads(response_text)
                            is_json = True
                        except Exception:
                            is_json = False

                        json_status = "✅ JSON Válido" if is_json else "⚠️ No es JSON"
                        print(f"Completado en {t_total:.2f}s | {tps:.1f} tok/s | {eval_count} tokens | {json_status}", flush=True)

                        model_stats.append({
                            "prompt": p_info["name"],
                            "t_total": t_total,
                            "tps": tps,
                            "eval_count": eval_count,
                            "is_json": is_json,
                        })
                    else:
                        print(f"❌ Error HTTP {res.status_code}", flush=True)
                except Exception as e:
                    print(f"❌ Error: {e}", flush=True)

            resumen[model] = model_stats

        print("\n" + "=" * 70, flush=True)
        print("📊 TABLA COMPARATIVA DE RESULTADOS", flush=True)
        print("=" * 70, flush=True)
        print(f"{'Modelo':<22} | {'Latencia Prom.':<16} | {'Velocidad Prom.':<18} | {'JSON Válido':<12}", flush=True)
        print("-" * 70, flush=True)

        for model, stats in resumen.items():
            if not stats:
                continue
            avg_time = sum(s["t_total"] for s in stats) / len(stats)
            avg_tps = sum(s["tps"] for s in stats) / len(stats)
            json_success = sum(1 for s in stats if s["is_json"])
            json_pct = f"{json_success}/{len(stats)}"
            print(f"{model:<22} | {avg_time:6.2f} seg       | {avg_tps:6.1f} tokens/seg  | {json_pct:<12}", flush=True)

        print("=" * 70 + "\n", flush=True)

if __name__ == "__main__":
    asyncio.run(benchmark())
