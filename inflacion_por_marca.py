#!/usr/bin/env python3
"""
inflacion_por_marca.py
----------------------
Calcula la inflacion REAL a nivel de marca usando los datos abiertos del
programa "Quien es Quien en los Precios" (QQP) de Profeco.

El INPC del INEGI publica solo el generico ("desodorantes") y esconde lo que
pasa con cada marca. QQP si trae marca, presentacion, cadena y sucursal.
Este script cruza dos periodos y reporta:

  - Variacion del precio de etiqueta por marca+presentacion
  - Variacion del precio por gramo/mililitro (detecta REDUFLACION)
  - Desglose por cadena comercial
  - Comparativo entre marcas del mismo producto

USO
---
  # Comparar agosto 2025 vs agosto 2026, desodorantes, en todo el pais
  python inflacion_por_marca.py \
      --base   qqp_2025_08.csv \
      --actual qqp_2026_08.csv \
      --producto "DESODORANTE"

  # Solo dos marcas, solo Coahuila
  python inflacion_por_marca.py \
      --base qqp_2025_08.csv --actual qqp_2026_08.csv \
      --producto "DESODORANTE" \
      --marca REXONA AMMENS \
      --estado COAHUILA

  # Canasta completa de higiene personal, desglose por cadena
  python inflacion_por_marca.py \
      --base qqp_2025_08.csv --actual qqp_2026_08.csv \
      --categoria "CUIDADO PERSONAL" --por-cadena

  # Varios archivos por periodo (comodines)
  python inflacion_por_marca.py \
      --base "qqp_2025_*.csv" --actual "qqp_2026_*.csv" \
      --producto DESODORANTE SHAMPOO PASTA

DONDE BAJAR LOS DATOS
---------------------
  datos.gob.mx -> buscar "Programa Quien es quien en los precios"
  Hay un CSV por mes. Baja el mes que quieras de cada anio.

REQUISITOS
----------
  pip install pandas
"""

import argparse
import glob
import re
import sys
import unicodedata

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta pandas. Instalalo con:  pip install pandas")


# --------------------------------------------------------------------------
# Lectura y normalizacion
# --------------------------------------------------------------------------

# Nombres de columna que puede traer QQP para cada campo que usamos.
# La comparacion ignora mayusculas, acentos, guiones bajos y espacios, asi que
# "fecha_registro", "FECHAREGISTRO" y "Fecha Registro" cuentan como el mismo.
COLUMNAS = {
    "producto": ["PRODUCTO"],
    "presentacion": ["PRESENTACION"],
    "marca": ["MARCA"],
    "categoria": ["CATEGORIA"],
    "catalogo": ["CATALOGO"],
    "precio": ["PRECIO"],
    "fecha": ["FECHAREGISTRO", "FECHA"],
    "cadena": ["CADENACOMERCIAL", "CADENA"],
    "giro": ["GIRO"],
    "tienda": ["NOMBRECOMERCIAL"],
    "estado": ["ESTADO"],
    "municipio": ["MUNICIPIO"],
}


def sin_acentos(texto):
    if not isinstance(texto, str):
        return texto
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper().strip()


class ColumnasFaltantes(Exception):
    """El CSV no trae las columnas minimas de QQP."""


# Filas por bloque. Un CSV anual de QQP puede traer 20+ millones de filas;
# leerlo entero ocupa unas 5 veces su tamano en RAM y tumba la maquina.
# Leyendo por bloques y filtrando cada bloque solo se guarda lo que interesa.
TAM_BLOQUE = 500_000


def clave_columna(nombre):
    """Reduce el nombre de una columna a solo letras y numeros en mayusculas,
    sin acentos. Los CSV de QQP han cambiado de formato entre anios
    ('cadena_comercial' en unos, 'CADENACOMERCIAL' en otros) y asi todos
    quedan reconocidos igual."""
    return re.sub(r"[^A-Z0-9]", "", sin_acentos(str(nombre)))


def leer_csv(patron, args=None):
    """Lee uno o varios CSV de QQP por bloques, normalizando y filtrando sobre
    la marcha para no cargar el archivo completo en memoria."""
    rutas = sorted(glob.glob(patron))
    if not rutas:
        sys.exit(f"No encontre archivos que coincidan con: {patron}")

    marcos = []
    for ruta in rutas:
        piezas = None
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                piezas, filas, guardadas = [], 0, 0
                lector = pd.read_csv(ruta, encoding=enc, low_memory=False,
                                     on_bad_lines="skip", chunksize=TAM_BLOQUE)
                for bloque in lector:
                    filas += len(bloque)
                    bloque = normalizar(bloque)
                    if args is not None:
                        bloque = filtrar(bloque, args)
                    if not bloque.empty:
                        guardadas += len(bloque)
                        piezas.append(bloque)
                    print(f"\r  {ruta}: {filas:,} filas leidas, "
                          f"{guardadas:,} conservadas", end="", file=sys.stderr)
                break
            except UnicodeDecodeError:
                piezas = None
                continue
            except ColumnasFaltantes as e:
                print(file=sys.stderr)
                sys.exit(f"{ruta}: {e}")
            except pd.errors.ParserError:
                piezas = None
                continue

        if piezas is None:
            print(f"\n  ! No pude leer {ruta}, lo salto", file=sys.stderr)
            continue

        print(file=sys.stderr)
        if piezas:
            marcos.append(pd.concat(piezas, ignore_index=True))

    if not marcos:
        sys.exit("No pude leer ningun archivo, o los filtros no dejaron "
                 "ninguna fila. Prueba terminos mas amplios.")
    return pd.concat(marcos, ignore_index=True)


def normalizar(df):
    """Deja los nombres de columna estandarizados y limpia los textos."""
    mapa = {}
    for col in df.columns:
        clave = clave_columna(col)
        for destino, posibles in COLUMNAS.items():
            if clave in posibles and destino not in mapa.values():
                mapa[col] = destino
                break
    df = df.rename(columns=mapa)

    faltan = {"producto", "marca", "precio"} - set(df.columns)
    if faltan:
        raise ColumnasFaltantes(
            f"Al CSV le faltan columnas indispensables: {faltan}\n"
            f"Columnas encontradas: {list(df.columns)[:15]}")

    for col in ("producto", "marca", "presentacion", "cadena",
                "estado", "municipio", "categoria"):
        if col in df.columns:
            df[col] = df[col].apply(sin_acentos)

    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    df = df[df["precio"] > 0]

    if "presentacion" not in df.columns:
        df["presentacion"] = "(SIN PRESENTACION)"
    df["presentacion"] = df["presentacion"].fillna("(SIN PRESENTACION)")

    return df


# --------------------------------------------------------------------------
# Deteccion de reduflacion: extraer el contenido de la presentacion
# --------------------------------------------------------------------------

UNIDADES = {
    "KG": 1000.0, "KILOGRAMO": 1000.0, "KILO": 1000.0,
    "G": 1.0, "GR": 1.0, "GRS": 1.0, "GRAMOS": 1.0, "GRAMO": 1.0,
    "L": 1000.0, "LT": 1000.0, "LTS": 1000.0, "LITRO": 1000.0, "LITROS": 1000.0,
    "ML": 1.0, "MILILITRO": 1.0, "MILILITROS": 1.0,
}

PATRON = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(KG|KILOGRAMO|KILO|GRS|GR|GRAMOS|GRAMO|G|"
    r"LTS|LT|LITROS|LITRO|L|MILILITROS|MILILITRO|ML)\b"
)


def contenido(presentacion):
    """Devuelve el contenido en gramos o mililitros, o None si no se puede leer."""
    if not isinstance(presentacion, str):
        return None
    m = PATRON.search(presentacion)
    if not m:
        return None
    try:
        cantidad = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    factor = UNIDADES.get(m.group(2))
    if factor is None or cantidad <= 0:
        return None
    return cantidad * factor


# --------------------------------------------------------------------------
# Filtros y agregacion
# --------------------------------------------------------------------------

def _patron_filtro(terminos):
    """Une los terminos del usuario en un patron seguro (escapa parentesis,
    guiones y demas metacaracteres de marcas como '7-UP' o 'COCA-COLA (LIGHT)')."""
    return "|".join(re.escape(sin_acentos(t)) for t in terminos)


def filtrar(df, args):
    if args.producto:
        patron = _patron_filtro(args.producto)
        df = df[df["producto"].str.contains(patron, na=False, regex=True)]
    if args.marca:
        patron = _patron_filtro(args.marca)
        df = df[df["marca"].str.contains(patron, na=False, regex=True)]
    if args.categoria and "categoria" in df.columns:
        patron = _patron_filtro(args.categoria)
        df = df[df["categoria"].str.contains(patron, na=False, regex=True)]
    if args.estado and "estado" in df.columns:
        patron = _patron_filtro(args.estado)
        df = df[df["estado"].str.contains(patron, na=False, regex=True)]
    if args.cadena and "cadena" in df.columns:
        patron = _patron_filtro(args.cadena)
        df = df[df["cadena"].str.contains(patron, na=False, regex=True)]
    return df


def resumir(df, llaves, min_obs):
    """Mediana de precio por llave. La mediana aguanta mejor los outliers
    de captura que el promedio."""
    g = df.groupby(llaves).agg(
        precio=("precio", "median"),
        n=("precio", "size"),
    ).reset_index()
    return g[g["n"] >= min_obs]


# --------------------------------------------------------------------------
# Reporte
# --------------------------------------------------------------------------

def pct(a, b):
    return (b / a - 1) * 100 if a and a > 0 else float("nan")


def tabla(comp, titulo, cols_id):
    print()
    print("=" * 100)
    print(titulo)
    print("=" * 100)
    if comp.empty:
        print("  (sin coincidencias entre los dos periodos)")
        return

    ancho_id = max(46, min(60, comp[cols_id].astype(str).apply(
        lambda r: len(" | ".join(r)), axis=1).max()))

    encabezado = " / ".join(c.upper() for c in cols_id)
    print(f"{encabezado:<{ancho_id}} "
          f"{'BASE':>9} {'ACTUAL':>9} {'VAR %':>8} {'$/100u':>9} "
          f"{'VAR REAL':>9} {'OBS':>6}")
    print("-" * 100)

    for _, r in comp.iterrows():
        ident = " | ".join(str(r[c]) for c in cols_id)[:ancho_id]
        var = r["var_pct"]
        var_real = r.get("var_unit_pct", float("nan"))
        unit = r.get("precio_unit_actual", float("nan"))

        marca_redu = ""
        if pd.notna(var_real) and pd.notna(var) and (var_real - var) > 2.0:
            marca_redu = "  <-- REDUFLACION"

        print(f"{ident:<{ancho_id}} "
              f"{r['precio_base']:>9.2f} {r['precio_actual']:>9.2f} "
              f"{var:>7.1f}% "
              f"{unit:>9.2f} " if pd.notna(unit) else
              f"{ident:<{ancho_id}} "
              f"{r['precio_base']:>9.2f} {r['precio_actual']:>9.2f} "
              f"{var:>7.1f}% {'-':>9} ", end="")
        print(f"{var_real:>8.1f}%" if pd.notna(var_real) else f"{'-':>9}",
              f"{int(r['n_actual']):>6}{marca_redu}")

    print("-" * 100)
    ponderada = comp["var_pct"].median()
    promedio = comp["var_pct"].mean()
    print(f"  Variacion MEDIANA: {ponderada:6.2f}%     "
          f"Variacion PROMEDIO: {promedio:6.2f}%     "
          f"Articulos comparados: {len(comp)}")

    if "var_unit_pct" in comp.columns:
        reales = comp["var_unit_pct"].dropna()
        if len(reales):
            print(f"  Variacion MEDIANA por unidad de contenido: {reales.median():6.2f}%"
                  f"   (esta es la inflacion que de verdad pagas)")


def comparar(base, actual, llaves, min_obs):
    b = resumir(base, llaves, min_obs).rename(
        columns={"precio": "precio_base", "n": "n_base"})
    a = resumir(actual, llaves, min_obs).rename(
        columns={"precio": "precio_actual", "n": "n_actual"})

    comp = b.merge(a, on=llaves, how="inner")
    if comp.empty:
        return comp

    comp["var_pct"] = comp.apply(
        lambda r: pct(r["precio_base"], r["precio_actual"]), axis=1)

    if "presentacion" in llaves:
        comp["contenido"] = comp["presentacion"].apply(contenido)
        comp["precio_unit_base"] = comp["precio_base"] / comp["contenido"] * 100
        comp["precio_unit_actual"] = comp["precio_actual"] / comp["contenido"] * 100
        # misma presentacion => la variacion unitaria es igual a la de etiqueta
        comp["var_unit_pct"] = comp["var_pct"]

    return comp.sort_values("var_pct", ascending=False)


def detectar_reduflacion(base, actual, min_obs):
    """Compara precio por gramo/ml entre periodos AGREGANDO por marca+producto,
    sin exigir la misma presentacion. Asi se ve el cambio de tamano."""
    resultados = []
    for etiqueta, df in (("base", base), ("actual", actual)):
        d = df.copy()
        d["contenido"] = d["presentacion"].apply(contenido)
        d = d[d["contenido"].notna() & (d["contenido"] > 0)]
        if d.empty:
            continue
        d["precio_unit"] = d["precio"] / d["contenido"] * 100
        g = d.groupby(["producto", "marca"]).agg(
            precio_unit=("precio_unit", "median"),
            contenido_tipico=("contenido", "median"),
            precio_etiqueta=("precio", "median"),
            n=("precio", "size"),
        ).reset_index()
        g = g[g["n"] >= min_obs]
        g["periodo"] = etiqueta
        resultados.append(g)

    if len(resultados) < 2:
        return pd.DataFrame()

    b, a = resultados
    comp = b.merge(a, on=["producto", "marca"], suffixes=("_base", "_actual"))
    if comp.empty:
        return comp

    comp["var_etiqueta"] = comp.apply(
        lambda r: pct(r["precio_etiqueta_base"], r["precio_etiqueta_actual"]), axis=1)
    comp["var_unitaria"] = comp.apply(
        lambda r: pct(r["precio_unit_base"], r["precio_unit_actual"]), axis=1)
    comp["var_contenido"] = comp.apply(
        lambda r: pct(r["contenido_tipico_base"], r["contenido_tipico_actual"]), axis=1)
    comp["brecha"] = comp["var_unitaria"] - comp["var_etiqueta"]

    return comp.sort_values("brecha", ascending=False)


def reporte_reduflacion(comp):
    print()
    print("=" * 100)
    print("DETECCION DE REDUFLACION  (precio por 100 g / 100 ml, sin exigir misma presentacion)")
    print("=" * 100)
    if comp.empty:
        print("  (no hay presentaciones legibles suficientes para este analisis)")
        return

    print(f"{'PRODUCTO / MARCA':<44} {'ETIQUETA':>9} {'CONTENIDO':>10} "
          f"{'REAL':>9} {'BRECHA':>9}")
    print("-" * 100)
    for _, r in comp.iterrows():
        ident = f"{r['producto']} | {r['marca']}"[:44]
        print(f"{ident:<44} {r['var_etiqueta']:>8.1f}% {r['var_contenido']:>9.1f}% "
              f"{r['var_unitaria']:>8.1f}% {r['brecha']:>8.1f}%"
              + ("  <-- ENCOGIO" if r["var_contenido"] < -1.5 else ""))
    print("-" * 100)
    print("  ETIQUETA  = lo que subio el precio que ves en el anaquel")
    print("  CONTENIDO = cuanto cambio el tamano tipico (negativo = encogio)")
    print("  REAL      = lo que subio el precio por gramo o mililitro")
    print("  BRECHA    = REAL menos ETIQUETA. Esto es la inflacion que el INPC")
    print("              puede no estar capturando en tu canasta.")


# --------------------------------------------------------------------------

def main():
    global TAM_BLOQUE
    p = argparse.ArgumentParser(
        description="Inflacion por marca con datos abiertos de Profeco (QQP).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True,
                   help="CSV (o comodin) del periodo base, ej. agosto 2025")
    p.add_argument("--actual", required=True,
                   help="CSV (o comodin) del periodo actual, ej. agosto 2026")
    p.add_argument("--producto", nargs="+", help="Filtrar por producto, ej. DESODORANTE")
    p.add_argument("--marca", nargs="+", help="Filtrar por marca, ej. REXONA AMMENS")
    p.add_argument("--categoria", nargs="+", help="Filtrar por categoria")
    p.add_argument("--estado", nargs="+", help="Filtrar por estado, ej. COAHUILA")
    p.add_argument("--cadena", nargs="+", help="Filtrar por cadena, ej. WALMART HEB")
    p.add_argument("--por-cadena", action="store_true",
                   help="Desglosar tambien por cadena comercial")
    p.add_argument("--min-obs", type=int, default=3,
                   help="Minimo de observaciones por articulo (default 3)")
    p.add_argument("--csv", help="Guardar el resultado en este archivo CSV")
    p.add_argument("--bloque", type=int, default=TAM_BLOQUE,
                   help=f"Filas por bloque de lectura (default {TAM_BLOQUE:,}). "
                        "Bajalo si te quedas sin memoria.")
    args = p.parse_args()

    TAM_BLOQUE = args.bloque

    if not any((args.producto, args.marca, args.categoria,
                args.estado, args.cadena)):
        print("AVISO: no pusiste ningun filtro, asi que se va a conservar el\n"
              "       archivo completo en memoria. Con los CSV anuales de QQP\n"
              "       eso puede tumbar la maquina. Usa --producto o --categoria\n"
              "       para quedarte solo con lo que te interesa.\n",
              file=sys.stderr)

    print("Leyendo periodo BASE...", file=sys.stderr)
    base = leer_csv(args.base, args)
    print("Leyendo periodo ACTUAL...", file=sys.stderr)
    actual = leer_csv(args.actual, args)

    print(f"\nTras filtros: {len(base):,} registros base, "
          f"{len(actual):,} registros actuales", file=sys.stderr)
    if base.empty or actual.empty:
        sys.exit("Los filtros dejaron algun periodo vacio. Prueba terminos mas amplios.")

    llaves = ["producto", "marca", "presentacion"]
    comp = comparar(base, actual, llaves, args.min_obs)
    tabla(comp, "INFLACION POR MARCA Y PRESENTACION (misma presentacion en ambos periodos)",
          llaves)

    reporte_reduflacion(detectar_reduflacion(base, actual, args.min_obs))

    if args.por_cadena and "cadena" in base.columns:
        llaves_c = ["producto", "marca", "cadena"]
        comp_c = comparar(base, actual, llaves_c, args.min_obs)
        tabla(comp_c, "INFLACION POR CADENA COMERCIAL", llaves_c)

    if args.csv and not comp.empty:
        comp.to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"\nResultado guardado en {args.csv}")

    print("\nNOTA: se usa la MEDIANA de precios, no el promedio, para que unos")
    print("pocos registros mal capturados no distorsionen el resultado.")
    print("Compara siempre el mismo mes de cada anio para evitar estacionalidad.")


if __name__ == "__main__":
    main()
