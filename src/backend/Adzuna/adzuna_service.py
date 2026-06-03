"""
Adzuna API Service for job data extraction and aggregation
"""

import requests
from typing import List, Dict, Any
from supabase import create_client
from config import ADZUNA_APP_ID, ADZUNA_APP_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, PROGRAMAS_KEYWORDS

# Initialize Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def buscar_vacantes_adzuna(keyword: str, num_pages: int = 1, country: str = 'us') -> List[Dict[str, Any]]:
    """
    Search for jobs on Adzuna API.
    
    Args:
        keyword: Job title or keyword to search
        num_pages: Number of pages to retrieve (50 results per page)
        country: Country code (us, uk, ca, etc.)
    
    Returns:
        List of job listings
    """
    all_results = []
    
    # Codificar el keyword para la URL
    encoded_keyword = keyword.replace(' ', '+')
    
    for page in range(1, num_pages + 1):
        try:
            # Construir la URL correctamente
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
            
            params = {
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "what": keyword,
                "results_per_page": 50,
                "sort_by": "date"
            }
            
            print(f"Consultando API para '{keyword}' - Página {page}...")
            
            response = requests.get(
                url,
                params=params,
                timeout=30,
            )
            
            # Verificar respuesta
            if response.status_code == 400:
                print(f"Error 400 para '{keyword}': Verifica tus credenciales de API")
                print(f"URL: {response.url}")
                print(f"Respuesta: {response.text}")
                break
                
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            all_results.extend(results)
            
            print(f"  Encontrados {len(results)} resultados en página {page}")
            
            # Si no hay más resultados o es la última página
            if not results or len(results) < 50:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Error buscando en Adzuna para '{keyword}' página {page}: {str(e)}")
            continue
        except Exception as e:
            print(f"Error inesperado para '{keyword}': {str(e)}")
            continue
    
    return all_results


def guardar_vacante(job: Dict[str, Any], programa: str) -> bool:
    """
    Save or update a job listing in Supabase.
    
    Args:
        job: Job data from Adzuna
        programa: Related program name
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Verificar que el job tenga ID
        if 'id' not in job:
            print(f"Job sin ID: {job.get('title', 'Unknown')}")
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
        print(f"Error guardando vacante: {str(e)}")
        return False


def procesar_todas_vacantes():
    """
    Procesa todas las vacantes para los programas definidos
    """
    resultados = {}
    
    for programa, keywords in PROGRAMAS_KEYWORDS.items():
        print(f"\n=== Procesando {programa} ===")
        vacantes_programa = []
        
        for keyword in keywords:
            print(f"  Buscando: {keyword}")
            vacantes = buscar_vacantes_adzuna(keyword, num_pages=2)
            vacantes_programa.extend(vacantes)
            
            # Guardar cada vacante en Supabase
            for vacante in vacantes:
                guardar_vacante(vacante, programa)
        
        resultados[programa] = {
            "total_encontradas": len(vacantes_programa),
            "keywords_utilizadas": keywords
        }
        
        print(f"  Total encontradas para {programa}: {len(vacantes_programa)}")
    
    return resultados


def fetch_jobs_from_db() -> List[Dict[str, Any]]:
    """
    Fetch all jobs from Supabase.
    
    Returns:
        List of jobs
    """
    try:
        response = supabase.table("vacantes").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching jobs from database: {str(e)}")
        return []


def get_analytics() -> Dict[str, Any]:
    """
    Generate analytics from job data.
    
    Returns:
        Dictionary with various analytics
    """
    jobs = fetch_jobs_from_db()
    
    if not jobs:
        return {
            "total_jobs": 0,
            "job_titles": [],
            "categories": [],
            "contract_types": [],
            "salary_ranges": [],
            "companies": [],
            "programas": [],
        }

    # Most in-demand job titles
    title_count = {}
    for job in jobs:
        title = job.get("title", "Unknown")
        title_count[title] = title_count.get(title, 0) + 1
    
    top_titles = sorted(title_count.items(), key=lambda x: x[1], reverse=True)[:20]

    # Categories (contract types)
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

    # Salary ranges
    salary_ranges = []
    jobs_with_salary = [j for j in jobs if j.get("salary_min") and j.get("salary_max")]
    
    if jobs_with_salary:
        salary_min = min(j["salary_min"] for j in jobs_with_salary)
        salary_max = max(j["salary_max"] for j in jobs_with_salary)
        
        # Create salary bins
        bin_size = (salary_max - salary_min) / 5 if salary_max > salary_min else 10000
        for i in range(5):
            bin_start = salary_min + (i * bin_size)
            bin_end = bin_start + bin_size
            count = len([j for j in jobs_with_salary 
                        if bin_start <= j["salary_min"] <= bin_end])
            salary_ranges.append({
                "range": f"${bin_start:,.0f} - ${bin_end:,.0f}",
                "count": count
            })

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

    return {
        "total_jobs": len(jobs),
        "jobs_with_salary": len(jobs_with_salary),
        "job_titles": [{"title": t, "count": c} for t, c in top_titles],
        "categories": [{"category": c, "count": co} for c, co in top_categories],
        "contract_types": [{"type": t, "count": c} for t, c in top_contracts],
        "salary_ranges": salary_ranges,
        "companies": [{"company": c, "count": co} for c, co in top_companies],
        "programas": [{"programa": p, "count": co} for p, co in top_programas],
    }


def get_salary_by_title(title: str) -> Dict[str, Any]:
    """
    Get salary information for a specific job title.
    
    Args:
        title: Job title to search
    
    Returns:
        Salary statistics
    """
    jobs = fetch_jobs_from_db()
    matching_jobs = [j for j in jobs if title.lower() in j.get("title", "").lower()]
    jobs_with_salary = [j for j in matching_jobs if j.get("salary_min") and j.get("salary_max")]
    
    if not jobs_with_salary:
        return {
            "title": title,
            "count": len(matching_jobs),
            "avg_min": None,
            "avg_max": None,
            "min_min": None,
            "max_max": None,
        }
    
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
    """
    Get salary information for a specific job category.
    
    Args:
        category: Job category
    
    Returns:
        Salary statistics
    """
    jobs = fetch_jobs_from_db()
    matching_jobs = [j for j in jobs if j.get("category") == category]
    jobs_with_salary = [j for j in matching_jobs if j.get("salary_min") and j.get("salary_max")]
    
    if not jobs_with_salary:
        return {
            "category": category,
            "count": len(matching_jobs),
            "avg_min": None,
            "avg_max": None,
        }
    
    avg_min = sum(j["salary_min"] for j in jobs_with_salary) / len(jobs_with_salary)
    avg_max = sum(j["salary_max"] for j in jobs_with_salary) / len(jobs_with_salary)
    
    return {
        "category": category,
        "count": len(matching_jobs),
        "avg_min": round(avg_min, 2),
        "avg_max": round(avg_max, 2),
    }


# Ejecutar el proceso si se llama directamente
if __name__ == "__main__":
    resultados = procesar_todas_vacantes()
    print("\n=== RESUMEN FINAL ===")
    for programa, data in resultados.items():
        print(f"{programa}: {data['total_encontradas']} vacantes encontradas")