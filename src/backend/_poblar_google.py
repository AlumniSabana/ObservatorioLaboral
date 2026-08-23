# -*- coding: utf-8 -*-
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from GoogleJobs.google_jobs_service import procesar_vacantes_google
r = procesar_vacantes_google(borrar=False)
print("RESULTADO:", json.dumps(r, ensure_ascii=False), flush=True)
