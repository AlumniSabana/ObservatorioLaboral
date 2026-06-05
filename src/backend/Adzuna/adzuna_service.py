"""
Adzuna API Service for job data extraction and aggregation
"""

import requests
from typing import List, Dict, Any
from supabase import create_client
from config import ADZUNA_APP_ID, ADZUNA_APP_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, PROGRAMAS_KEYWORDS
import re
from collections import Counter
from typing import List, Dict, Any

# Initialize Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def borrar_todas_vacantes():
    """Borra todas las vacantes existentes antes de una nueva recolección"""
    try:
        # Borra todos los registros
        response = supabase.table("vacantes").delete().neq("id", 0).execute()
        count = len(response.data) if response.data else 0
        print(f"🗑️ Se eliminaron {count} registros anteriores de la base de datos.")
        return True
    except Exception as e:
        print(f"❌ Error al borrar vacantes: {str(e)}")
        return False


def buscar_vacantes_adzuna(keyword: str, num_pages: int = 2, country: str = 'us') -> List[Dict[str, Any]]:
    """
    Search for jobs on Adzuna API.
    """
    all_results = []
    
    for page in range(1, num_pages + 1):
        try:
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
            
            params = {
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "what": keyword,
                "results_per_page": 50,
                "sort_by": "date"
            }
            
            print(f"   🔍 Consultando '{keyword}' - Página {page}...")
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 400:
                print(f"   ❌ Error 400 para '{keyword}': Verifica credenciales")
                break
                
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            all_results.extend(results)
            
            print(f"   ✅ Encontrados {len(results)} resultados")
            
            if not results or len(results) < 50:
                break
                
        except Exception as e:
            print(f"   ❌ Error buscando '{keyword}' página {page}: {str(e)}")
            continue
    
    return all_results


def guardar_vacante(job: Dict[str, Any], programa: str) -> bool:
    """Guarda o actualiza una vacante en Supabase"""
    try:
        if 'id' not in job:
            return False
            
        location_data = job.get("location", {})
        area = location_data.get("area", [])
        country = area[0] if len(area) > 0 else None

        row = {
            "id": int(job["id"]),
            "title": job.get("title"),
            "company": job.get("company", {}).get("display_name"),
            "location": location_data.get("display_name"),
            "country": country,
            "latitude": job.get("latitude"),
            "longitude": job.get("longitude"),
            "description": job.get("description"),
            "category": job.get("category", {}).get("label"),
            "contract_time": job.get("contract_time"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "salary_is_predicted": bool(int(job.get("salary_is_predicted", 0))),
            "redirect_url": job.get("redirect_url"),
            "created_at": job.get("created"),
            "fuente": "adzuna",
            "programa_relacionado": programa,
        }

        supabase.table("vacantes").upsert(row, on_conflict="id").execute()
        return True

    except Exception as e:
        print(f"   ❌ Error guardando vacante '{job.get('title', 'Sin título')}': {str(e)}")
        return False


def procesar_todas_vacantes(borrar: bool = False):
    """Procesa todas las vacantes usando TODAS las keywords de cada programa"""
    print("🚀 Iniciando proceso completo de recolección de vacantes...\n")
    
    # 1. Borrar datos anteriores si se indica
    if borrar:
        borrar_todas_vacantes()
        total_vacantes = 0
        total_guardadas = 0

        for programa, keywords in PROGRAMAS_KEYWORDS.items():
            print(f"\n=== Procesando {programa} ===")
            vacantes_programa = 0
            
            for keyword in keywords:   # ← Iteramos por TODAS las keywords
                print(f"  🔑 Keyword: '{keyword}'")
                vacantes = buscar_vacantes_adzuna(keyword, num_pages=2)
                
                vacantes_programa += len(vacantes)
                total_vacantes += len(vacantes)
                
                guardadas = 0
                for vacante in vacantes:
                    if guardar_vacante(vacante, programa):
                        guardadas += 1
                        total_guardadas += 1
                
                print(f"     → {len(vacantes)} encontradas | {guardadas} guardadas")
            
            print(f"  ✅ Total para {programa}: {vacantes_programa} vacantes procesadas")

        print(f"\n🎉 === RESUMEN FINAL ===")
        print(f"   Total vacantes encontradas: {total_vacantes}")
        print(f"   Total vacantes guardadas: {total_guardadas}")
        print(f"   Programas procesados: {len(PROGRAMAS_KEYWORDS)}")

        return {
            "status": "completed",
            "total_vacantes": total_vacantes,
            "total_guardadas": total_guardadas,
            "programas_procesados": len(PROGRAMAS_KEYWORDS)
        }
    else:
        fetch_jobs_from_db()
        return {"status": "no_borrar", "message": "No se borraron vacantes, solo se obtuvieron de la base de datos"}

def fetch_jobs_from_db() -> List[Dict[str, Any]]:
    """Obtiene TODAS las vacantes de la base de datos usando paginación"""
    all_jobs = []
    page_size = 1000
    start = 0
    total_fetched = 0
    
    try:
        # Primero, obtenemos el conteo total (opcional pero recomendado)
        count_response = supabase.table("vacantes").select("*", count="exact", head=True).execute()
        total_records = count_response.count
        print(f"Total de registros en BD: {total_records}")
        
        # Bucle para traer todas las páginas
        while True:
            # CORRECCIÓN: .order("id") sin parámetro ascending
            response = supabase.table("vacantes")\
                .select("*")\
                .order("id")\
                .range(start, start + page_size - 1)\
                .execute()
            
            if not response.data or len(response.data) == 0:
                break
                
            all_jobs.extend(response.data)
            total_fetched += len(response.data)
            print(f"Página {start//page_size + 1}: {len(response.data)} registros (acumulado: {total_fetched})")
            
            # Si obtuvimos menos de page_size, es la última página
            if len(response.data) < page_size:
                break
                
            start += page_size
            
        print(f"✅ Total de registros obtenidos: {len(all_jobs)}")
        return all_jobs
        
    except Exception as e:
        print(f"Error fetching jobs from database: {str(e)}")
        return []


def normalize_title(title: str) -> str:
    """Normaliza títulos de cargos para agrupar variantes similares"""
    if not title:
        return "Sin título"
    
    title = title.lower()
    
    # Eliminar niveles de seniority
    title = re.sub(r'\b(sr\.?|senior|s\.r\.?|jr\.?|junior|lead|principal|staff|associate|entry\s*level|entry-level|entry)\b', '', title, flags=re.IGNORECASE)
    
    # Eliminar números romanos y niveles
    title = re.sub(r'\b(i{1,3}|iv|v|vi|vii|viii|ix|x|level\s*\d+|nivel\s*\d+)\b', '', title, flags=re.IGNORECASE)
    
    # Eliminar palabras comunes que no afectan el significado principal
    title = re.sub(r'\b(and|&|de|del|la|las|los|el|en|para|por|con|sin|sobre|tras|ante|bajo|cabe|contra|desde|durante|entre|hacia|hasta|mediante|según|vía|vs|versus)\b', '', title, flags=re.IGNORECASE)
    
    # Eliminar caracteres especiales y espacios extra
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    
    # Estandarizar términos comunes
    title = re.sub(r'\b(software\s+)?develop(er|ment|ing)\b', 'developer', title)
    title = re.sub(r'\b(software\s+)?engine(er|eering)\b', 'engineer', title)
    title = re.sub(r'\bdata\s+(scientist|analyst|engineer)\b', lambda m: f"data {m.group(1)}", title)
    title = re.sub(r'\bweb\s+develop(er|ment)\b', 'web developer', title)
    title = re.sub(r'\bmobile\s+develop(er|ment)\b', 'mobile developer', title)
    title = re.sub(r'\bfull[- ]stack\s+develop(er|ment)\b', 'full stack developer', title)
    title = re.sub(r'\bfront[- ]?end\s+develop(er|ment)\b', 'frontend developer', title)
    title = re.sub(r'\bback[- ]?end\s+develop(er|ment)\b', 'backend developer', title)
    title = re.sub(r'\bdevops\s+engineer\b', 'devops engineer', title)
    title = re.sub(r'\bcloud\s+engineer\b', 'cloud engineer', title)
    title = re.sub(r'\bproduct\s+manager\b', 'product manager', title)
    title = re.sub(r'\bproject\s+manager\b', 'project manager', title)
    title = re.sub(r'\bbusiness\s+analyst\b', 'business analyst', title)
    title = re.sub(r'\bquality\s+assurance\b', 'qa engineer', title)
    title = re.sub(r'\buta\s+analyst\b', 'data analyst', title)
    
    return title.strip()


def get_job_titles_with_normalization(jobs: List[Dict[str, Any]], top_n: int = 20) -> List[Dict[str, Any]]:
    """Cuenta títulos normalizados y retorna los más comunes"""
    title_counter = Counter()
    
    for job in jobs:
        original_title = job.get("title", "Sin título")
        normalized_title = normalize_title(original_title)
        title_counter[normalized_title] += 1
    
    # Mostrar estadísticas de normalización (debug)
    print(f"📊 Títulos originales únicos: {len(set(job.get('title', 'Sin título') for job in jobs))}")
    print(f"📊 Títulos normalizados únicos: {len(title_counter)}")
    
    # Retornar top N títulos normalizados
    return [
        {"title": title, "count": count}
        for title, count in title_counter.most_common(top_n)
    ]


def get_analytics() -> Dict[str, Any]:
    """Genera analytics completos con normalización de títulos"""
    jobs = fetch_jobs_from_db()
    
    if not jobs:
        return {
            "total_jobs": 0,
            "jobs_with_salary": 0,
            "job_titles": [],
            "categories": [],
            "contract_types": [],
            "salary_ranges": [],
            "companies": [],
            "programas": [],
        }

    # Most in-demand job titles (NORMALIZADOS)
    top_titles = get_job_titles_with_normalization(jobs, top_n=20)

    # Categories
    category_count = {}
    for job in jobs:
        category = job.get("category") or "Unknown"
        category_count[category] = category_count.get(category, 0) + 1
    top_categories = sorted(category_count.items(), key=lambda x: x[1], reverse=True)[:15]

    # Contract types
    contract_count = {}
    for job in jobs:
        contract = job.get("contract_time") or "Unknown"
        contract_count[contract] = contract_count.get(contract, 0) + 1
    top_contracts = sorted(contract_count.items(), key=lambda x: x[1], reverse=True)

    # Salary ranges (MEJORADO: usando rangos más realistas)
    jobs_with_salary = [j for j in jobs if j.get("salary_min") and j.get("salary_max")]
    
    if jobs_with_salary:
        # Usar rangos predefinidos más útiles visualmente
        salary_buckets = [
            (0, 30000, "Menos de $30k"),
            (30000, 50000, "$30k - $50k"),
            (50000, 70000, "$50k - $70k"),
            (70000, 90000, "$70k - $90k"),
            (90000, 120000, "$90k - $120k"),
            (120000, 150000, "$120k - $150k"),
            (150000, 200000, "$150k - $200k"),
            (200000, float('inf'), "Más de $200k")
        ]
        
        salary_ranges = []
        for min_val, max_val, label in salary_buckets:
            count = len([j for j in jobs_with_salary 
                        if min_val <= j["salary_min"] <= max_val])
            if count > 0:
                salary_ranges.append({
                    "range": label,
                    "count": count
                })
    else:
        salary_ranges = []

    # Top companies
    company_count = {}
    for job in jobs:
        company = job.get("company") or "Unknown"
        company_count[company] = company_count.get(company, 0) + 1
    top_companies = sorted(company_count.items(), key=lambda x: x[1], reverse=True)[:15]

    # Programs
    programa_count = {}
    for job in jobs:
        programa = job.get("programa_relacionado") or "Unknown"
        programa_count[programa] = programa_count.get(programa, 0) + 1
    top_programas = sorted(programa_count.items(), key=lambda x: x[1], reverse=True)[:15]

    analytics_data = {
        "total_jobs": len(jobs),
        "jobs_with_salary": len(jobs_with_salary),
        "job_titles": top_titles,
        "categories": [{"category": c, "count": co} for c, co in top_categories],
        "contract_types": [{"type": t, "count": c} for t, c in top_contracts],
        "salary_ranges": salary_ranges,
        "companies": [{"company": c, "count": co} for c, co in top_companies],
        "programas": [{"programa": p, "count": co} for p, co in top_programas],
    }
    
    # Mostrar top títulos para debug
    print("\n📊 TOP 10 CARGOS NORMALIZADOS:")
    for i, title_data in enumerate(top_titles[:10], 1):
        print(f"  {i}. {title_data['title']}: {title_data['count']} ocurrencias")
    
    return analytics_data


def get_salary_by_title(title: str) -> Dict[str, Any]:
    jobs = fetch_jobs_from_db()
    matching_jobs = [j for j in jobs if title.lower() in j.get("title", "").lower()]
    jobs_with_salary = [j for j in matching_jobs if j.get("salary_min") and j.get("salary_max")]
    
    if not jobs_with_salary:
        return {"title": title, "count": len(matching_jobs), "avg_min": None, "avg_max": None, "min_min": None, "max_max": None}
    
    avg_min = sum(j["salary_min"] for j in jobs_with_salary) / len(jobs_with_salary)
    avg_max = sum(j["salary_max"] for j in jobs_with_salary) / len(jobs_with_salary)
    
    return {
        "title": title,
        "count": len(matching_jobs),
        "avg_min": round(avg_min, 2),
        "avg_max": round(avg_max, 2),
        "min_min": min(j["salary_min"] for j in jobs_with_salary),
        "max_max": max(j["salary_max"] for j in jobs_with_salary),
    }


def get_salary_by_category(category: str) -> Dict[str, Any]:
    jobs = fetch_jobs_from_db()
    matching_jobs = [j for j in jobs if j.get("category") == category]
    jobs_with_salary = [j for j in matching_jobs if j.get("salary_min") and j.get("salary_max")]
    
    if not jobs_with_salary:
        return {"category": category, "count": len(matching_jobs), "avg_min": None, "avg_max": None}
    
    avg_min = sum(j["salary_min"] for j in jobs_with_salary) / len(jobs_with_salary)
    avg_max = sum(j["salary_max"] for j in jobs_with_salary) / len(jobs_with_salary)
    
    return {
        "category": category,
        "count": len(matching_jobs),
        "avg_min": round(avg_min, 2),
        "avg_max": round(avg_max, 2),
    }


# Ejecutar directamente si se corre el archivo
if __name__ == "__main__":
    procesar_todas_vacantes()