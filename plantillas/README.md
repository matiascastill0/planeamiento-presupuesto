# Plantillas · armado con el Real 2026

Scripts locales (Python 3: pandas, openpyxl, lxml) que reconstruyen las 184 plantillas Ppto27 con el Real 2026 desde la TD Regional.

```bash
python3 parse_cache_v2.py cache_ago.pkl     # decodifica la caché de la TD (.xlsb)
python3 build_bd.py                          # insumos de homologación
python3 ruta_v2.py                           # reconstruye las plantillas (o: ruta_v2.py "MDK/01. PERU")
python3 v2_verificar.py                      # cuadre país × vehículo × CeCo × cuenta × mes
python3 control_duplicados.py && python3 validar_todo.py && python3 control_ipc.py && python3 control_fino.py
```

Reglas clave: Real 2026 Vista 1 y 3, sin INTERCOM ni ELIM, con ajustes; IPC siempre excluido; CeCo real numerado (nunca "Varios"); edición del Excel solo por XML (lxml) para no perder formato.

## Plantillas especiales

| Script | Qué arma |
|---|---|
| `intercom_plantilla.py` | Plantilla de intercompanies: filas **Contable** e **Intercom** por país y Nivel 2, con Contable + Intercom = Gestión y efecto 0 entre países. |
| `panama_comisiones_2027.py` | Formato de comisiones de Panamá (Commision Paid + TRASLADOS → BNK) con el Real 2026 y el Ppto 2026 de referencia, cuadrado contra la TD. |

## Controles antes de entregar

`v2_verificar.py` (0 diferencias por país × vehículo × CeCo × mes), `control_duplicados.py`, `validar_todo.py`, `control_ipc.py`, `control_ipc_rubros.py` y `control_fino.py`.

---

<sub>© 2026 Credicorp Capital. Uso interno. Ver [LICENSE](../LICENSE).</sub>
