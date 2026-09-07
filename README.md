# Calcula tu inflación

Herramienta en Python para calcular la **inflación real a nivel de marca** con los
datos abiertos del programa *Quién es Quién en los Precios* (QQP) de Profeco.

El INPC del INEGI publica el genérico ("desodorantes") y esconde lo que pasa con
cada marca. QQP sí trae **marca, presentación, cadena y sucursal**, así que se
puede cruzar dos periodos y ver qué subió de verdad — y, sobre todo, detectar
**reduflación**: el producto que cuesta casi lo mismo pero trae menos contenido.

## Qué reporta

| Reporte | Qué te dice |
|---|---|
| Variación por marca + presentación | Cuánto subió el precio de etiqueta del mismo artículo exacto |
| Precio por 100 g / 100 ml | La inflación que de verdad pagas por unidad de contenido |
| Detección de reduflación | Compara etiqueta contra contenido: si el empaque encogió, aparece la brecha |
| Desglose por cadena comercial | Qué tienda subió más el mismo producto |

## Instalación

```bash
pip install -r requirements.txt
```

Requiere Python 3.8 o superior.

## De dónde bajar los datos

En [datos.gob.mx](https://datos.gob.mx) busca **"Programa Quien es quien en los precios"**.
Los datos vienen comprimidos, normalmente un archivo por año (`QQP_2025.rar`).

### Preparar los archivos

1. **Descomprime** cada `.rar` con WinRAR o 7-Zip. Adentro vienen los CSV.
2. **Crea una carpeta `datos/`** dentro del proyecto y mete ahí los CSV.
3. Deja los nombres con el año visible, para poder separar periodos con comodines.

```
CALCULA_TU_INFLACI-N/
├── inflacion_por_marca.py
├── datos/                    ← tus CSV descomprimidos (NO se suben a GitHub)
│   ├── QQP_2024.csv
│   └── QQP_2025.csv
└── ejemplos/                 ← datos de prueba, estos sí vienen en el repo
```

La carpeta `datos/` está en el `.gitignore`, así que git nunca va a intentar
subir esos archivos. **No los subas a GitHub**: pesan cientos de MB y el límite
por archivo son 100 MB.

### Sobre el tamaño de los archivos

Un año completo de QQP puede traer **más de 20 millones de filas**. Cargarlo
entero en memoria ocuparía unas 5 veces el tamaño del CSV — un archivo de 2 GB
pediría cerca de 10 GB de RAM.

Por eso el script **lee por bloques y filtra sobre la marcha**: solo guarda en
memoria las filas que pasan tus filtros. Aun así, **usa siempre al menos un
filtro** (`--producto`, `--categoria`, `--marca`...). Sin filtros no hay nada
que descartar y el archivo termina completo en memoria.

```bash
# bien: solo se guardan los desodorantes
python inflacion_por_marca.py --base "datos/QQP_2024.csv" \
    --actual "datos/QQP_2025.csv" --producto DESODORANTE

# mal: sin filtro, intenta guardar los 20 millones de filas
python inflacion_por_marca.py --base "datos/QQP_2024.csv" \
    --actual "datos/QQP_2025.csv"
```

Si aun así te quedas sin memoria, baja el tamaño de bloque con `--bloque 100000`.

Compara siempre el mismo mes o periodo de cada año para no mezclar estacionalidad.

## Uso

Prueba rápida con los datos de ejemplo que vienen en el repo:

```bash
python inflacion_por_marca.py \
    --base   ejemplos/qqp_ejemplo_base.csv \
    --actual ejemplos/qqp_ejemplo_actual.csv
```

Comparar agosto 2025 contra agosto 2026, desodorantes, en todo el país:

```bash
python inflacion_por_marca.py \
    --base   qqp_2025_08.csv \
    --actual qqp_2026_08.csv \
    --producto "DESODORANTE"
```

Solo dos marcas, solo Coahuila:

```bash
python inflacion_por_marca.py \
    --base qqp_2025_08.csv --actual qqp_2026_08.csv \
    --producto "DESODORANTE" \
    --marca REXONA AMMENS \
    --estado COAHUILA
```

Canasta completa de higiene personal, con desglose por cadena:

```bash
python inflacion_por_marca.py \
    --base qqp_2025_08.csv --actual qqp_2026_08.csv \
    --categoria "CUIDADO PERSONAL" --por-cadena
```

Varios archivos por periodo (comodines):

```bash
python inflacion_por_marca.py \
    --base "qqp_2025_*.csv" --actual "qqp_2026_*.csv" \
    --producto DESODORANTE SHAMPOO PASTA
```

## Opciones

| Opción | Para qué sirve |
|---|---|
| `--base` | CSV (o comodín) del periodo base. **Obligatorio** |
| `--actual` | CSV (o comodín) del periodo actual. **Obligatorio** |
| `--producto` | Filtrar por producto, ej. `DESODORANTE` |
| `--marca` | Filtrar por marca, ej. `REXONA AMMENS` |
| `--categoria` | Filtrar por categoría |
| `--estado` | Filtrar por estado, ej. `COAHUILA` |
| `--cadena` | Filtrar por cadena, ej. `WALMART HEB` |
| `--por-cadena` | Agrega el desglose por cadena comercial |
| `--min-obs` | Mínimo de observaciones por artículo (default 3) |
| `--csv` | Guarda el resultado en un archivo CSV |
| `--bloque` | Filas por bloque de lectura (default 500,000). Bájalo si te quedas sin memoria |

Los filtros son por coincidencia parcial y no distinguen acentos ni mayúsculas.

## Ejemplo de salida

```
====================================================================================================
DETECCION DE REDUFLACION  (precio por 100 g / 100 ml, sin exigir misma presentacion)
====================================================================================================
PRODUCTO / MARCA                              ETIQUETA  CONTENIDO      REAL    BRECHA
----------------------------------------------------------------------------------------------------
DESODORANTE | AMMENS                              2.9%     -20.0%     28.7%     25.7%  <-- ENCOGIO
DESODORANTE | REXONA                             15.5%       0.0%     15.5%      0.0%
```

AMMENS subió apenas 2.9% en la etiqueta, pero el envase pasó de 150 g a 120 g:
por gramo la subida real fue de **28.7%**. Esa brecha de 25.7 puntos es la
inflación que no se ve en el anaquel.

## Notas metodológicas

- Se usa la **mediana** de precios, no el promedio, para que unos pocos registros
  mal capturados no distorsionen el resultado.
- Un artículo solo entra al comparativo si aparece en **ambos** periodos con al
  menos `--min-obs` observaciones.
- El contenido se lee de la presentación (`BARRA 50 G`, `BOTELLA 700 ML`);
  las presentaciones que no traen cantidad legible quedan fuera del análisis por
  unidad, pero siguen contando en la variación de etiqueta.
- Compara siempre el mismo mes de cada año para evitar estacionalidad.

## Fuente

Datos: [Quién es Quién en los Precios](https://datos.gob.mx) — Profeco, datos abiertos.
