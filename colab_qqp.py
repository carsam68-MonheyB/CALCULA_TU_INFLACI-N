"""
colab_qqp.py
------------
Apoyo para el cuaderno de Colab de "Calcula tu inflacion".

El cuaderno solo llama a cuatro funciones de aqui:

    preparar()                      alista el entorno
    ubicar(carpeta)                 encuentra los .rar en Drive
    analizar(...)                   hace todo el analisis
    ver_una_pieza(carpeta, rar)     solo si algo falla

La logica vive aqui y no en las celdas, para que las correcciones lleguen
con volver a ejecutar el primer paso, sin reabrir el cuaderno.

Por que no se descomprimen los .rar: un anio de QQP ocupa cerca de 5 GB
repartido en decenas de piezas. Aqui se saca una pieza, se filtra, se
guarda lo poco que sobrevive y se borra antes de seguir con la siguiente.
"""

import glob
import os
import shutil
import subprocess
import sys

import pandas as pd

VERSION = "2026-09-08"

RAIZ_DRIVE = "/content/drive/MyDrive"
TEMPORAL = "_pieza"
FILAS_POR_BLOQUE = 400_000

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# --------------------------------------------------------------------------
# Paso 1
# --------------------------------------------------------------------------

def preparar():
    """Recarga el codigo recien descargado y avisa si falta el descompresor."""
    import importlib
    try:
        import inflacion_por_marca
        importlib.reload(inflacion_por_marca)
    except Exception:
        pass

    print(f"Listo.  (version del codigo: {VERSION})")
    if shutil.which("unar") is None:
        print("Aviso: no se instalo el descompresor; vuelve a ejecutar este paso.")


def _ipm():
    """Importa inflacion_por_marca, recargandolo si quedo una version vieja."""
    import importlib
    import inflacion_por_marca as ipm
    if not hasattr(ipm, "opciones_lectura"):
        importlib.reload(ipm)
    return ipm


# --------------------------------------------------------------------------
# Paso 3
# --------------------------------------------------------------------------

def ubicar(carpeta_en_drive):
    """Devuelve la ruta de la carpeta y lista los comprimidos que hay ahi."""
    carpeta = os.path.join(RAIZ_DRIVE, carpeta_en_drive)

    if not os.path.isdir(carpeta):
        print(f"No existe la carpeta: {carpeta}\n")
        if os.path.isdir(RAIZ_DRIVE):
            print("Carpetas que tienes en Mi unidad:")
            for n in sorted(os.listdir(RAIZ_DRIVE)):
                if os.path.isdir(os.path.join(RAIZ_DRIVE, n)):
                    print("  ", n)
        return carpeta

    archivos = sorted(glob.glob(os.path.join(carpeta, "*.rar")) +
                      glob.glob(os.path.join(carpeta, "*.zip")))
    print(f"Carpeta: {carpeta}\n")
    if archivos:
        print("Comprimidos disponibles:")
        for f in archivos:
            print(f"   {os.path.basename(f):<24} {os.path.getsize(f)/1e6:>8,.1f} MB")
        print("\nEscribe dos de estos en el Paso 4.")
    else:
        print("No hay .rar ni .zip en esta carpeta.")
    return carpeta


# --------------------------------------------------------------------------
# Lectura de un comprimido, pieza por pieza
# --------------------------------------------------------------------------

def _piezas(ruta):
    r = subprocess.run(["lsar", ruta], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [l.strip() for l in r.stdout.splitlines()[1:]
            if l.strip().lower().endswith(".csv")]


def _sacar(ruta, pieza):
    """Extrae una pieza al directorio temporal y devuelve su ruta, o None."""
    shutil.rmtree(TEMPORAL, ignore_errors=True)
    r = subprocess.run(["unar", "-q", "-f", "-o", TEMPORAL, ruta, pieza],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    for raiz, _, archivos in os.walk(TEMPORAL):
        for a in archivos:
            if a.lower().endswith(".csv"):
                return os.path.join(raiz, a)
    return None


def _filtrar(ruta_csv, mes, filtros):
    """Lee una pieza por bloques y devuelve solo las filas que interesan."""
    ipm = _ipm()

    class Args:
        pass
    args = Args()
    for campo in ("producto", "marca", "categoria", "estado", "cadena"):
        valor = filtros.get(campo, "")
        setattr(args, campo, valor.split() if valor and valor.strip() else None)
    args.mes = mes or None

    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            trozos = []
            for bloque in pd.read_csv(ruta_csv, encoding=enc, low_memory=False,
                                      on_bad_lines="skip",
                                      chunksize=FILAS_POR_BLOQUE,
                                      **ipm.opciones_lectura(ruta_csv, enc)):
                bloque = ipm.filtrar(ipm.normalizar(bloque), args)
                if not bloque.empty:
                    trozos.append(bloque)
            return pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()
        except UnicodeDecodeError:
            continue
    return pd.DataFrame()


def anios_en_datos(df):
    """Anios presentes en la columna de fecha. Es el unico dato del anio que
    no depende de como se llamen los archivos."""
    if "fecha" not in df.columns:
        return {}
    fechas = pd.to_datetime(df["fecha"], errors="coerce").dropna()
    return {} if fechas.empty else fechas.dt.year.value_counts().to_dict()


def _cosechar(carpeta, comprimido, mes, filtros, destino):
    """Recorre las piezas de un comprimido y guarda solo lo filtrado."""
    ruta = os.path.join(carpeta, comprimido)
    if not os.path.exists(ruta):
        print(f"  no existe: {comprimido}")
        return None

    piezas = _piezas(ruta)
    if not piezas:
        print(f"  no pude leer el contenido de {comprimido}")
        return None

    print(f"{comprimido}: {len(piezas)} piezas")
    reunido, filas, fallos = [], 0, 0

    for i, pieza in enumerate(piezas, 1):
        csv = _sacar(ruta, pieza)
        if csv is None:
            fallos += 1
        else:
            try:
                chico = _filtrar(csv, mes, filtros)
                if not chico.empty:
                    reunido.append(chico)
                    filas += len(chico)
            except Exception:
                fallos += 1
            finally:
                shutil.rmtree(TEMPORAL, ignore_errors=True)
        print(f"\r  pieza {i}/{len(piezas)}   filas utiles: {filas:,}",
              end="", flush=True)

    print()
    if fallos:
        print(f"  ({fallos} piezas no se pudieron leer)")
    if not reunido:
        print("  no sobrevivio ninguna fila con esos filtros")
        return None

    juntos = pd.concat(reunido, ignore_index=True)
    juntos.to_csv(destino, index=False, encoding="utf-8")
    anios = anios_en_datos(juntos)
    if anios:
        print("  anios en los datos: " +
              ", ".join(f"{a} ({n:,} filas)" for a, n in sorted(anios.items())))
    return destino


# --------------------------------------------------------------------------
# Paso 5
# --------------------------------------------------------------------------

def analizar(carpeta, comprimido_base, comprimido_actual, mes, filtros,
             por_cadena=True, min_obs=3, salida="resultado.csv"):
    """Cosecha los dos periodos y corre el analisis."""
    if not mes:
        print("Falta el MES. Sin el se mezclan los doce meses del anio.")
        return False
    if not any(v.strip() for v in filtros.values() if v):
        print("Falta un filtro. Escribe al menos un producto o una categoria.")
        return False

    print(f"Buscando {MESES[mes]} en cada comprimido. Esto tarda varios minutos.\n")

    base = _cosechar(carpeta, comprimido_base, mes, filtros, "_base.csv")
    if not base:
        return False
    actual = _cosechar(carpeta, comprimido_actual, mes, filtros, "_actual.csv")
    if not actual:
        return False

    ab = anios_en_datos(pd.read_csv(base))
    aa = anios_en_datos(pd.read_csv(actual))
    if ab and aa:
        pb, pa = max(ab, key=ab.get), max(aa, key=aa.get)
        print(f"\nComparando {MESES[mes]} {pb} contra {MESES[mes]} {pa}")
        if pb == pa:
            print("\nLos dos comprimidos traen el mismo anio; la comparacion")
            print("daria cero. Elige otros dos en el Paso 4.")
            return False

    cmd = [sys.executable, "inflacion_por_marca.py",
           "--base", base, "--actual", actual,
           "--min-obs", str(min_obs), "--csv", salida]
    if por_cadena:
        cmd.append("--por-cadena")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print("--- detalle del error ---")
        print(proc.stderr[-2000:])
    return proc.returncode == 0


# --------------------------------------------------------------------------
# Solo si algo falla
# --------------------------------------------------------------------------

def ver_una_pieza(carpeta, comprimido):
    """Muestra como viene un archivo por dentro: separador, encabezado y
    primeras lineas. Extrae una sola pieza, no el anio completo."""
    ipm = _ipm()
    ruta = os.path.join(carpeta, comprimido)
    if not os.path.exists(ruta):
        print(f"No existe: {comprimido}")
        return

    piezas = _piezas(ruta)
    if not piezas:
        print("No pude leer el contenido del comprimido.")
        return

    print(f"{comprimido}: {len(piezas)} piezas. Primeras:")
    for p in piezas[:5]:
        print("   ", p)

    csv = _sacar(ruta, piezas[0])
    if csv is None:
        print("\nNo se pudo extraer la primera pieza.")
        return

    try:
        print(f"\nPieza: {os.path.basename(csv)}  "
              f"({os.path.getsize(csv)/1e6:,.0f} MB)")
        lineas, enc = ipm.primeras_lineas(csv, 3)
        print(f"codificacion: {enc}")
        if enc:
            op = ipm.opciones_lectura(csv, enc)
            print(f"separador: {op['sep']!r}")
            print("encabezado:", "no trae" if "names" in op else "si trae")
        print("\nPrimeras lineas:")
        for i, l in enumerate(lineas, 1):
            print(f"{i}| {l[:200]}")
        df = pd.read_csv(csv, nrows=200, encoding=enc,
                         **ipm.opciones_lectura(csv, enc))
        print(f"\nColumnas: {list(df.columns)[:8]}")
    finally:
        shutil.rmtree(TEMPORAL, ignore_errors=True)
