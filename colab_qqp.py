"""
colab_qqp.py
------------
Funciones de apoyo para el cuaderno de Colab de "Calcula tu inflacion".

El cuaderno solo llama a estas funciones. La logica vive aqui para que las
correcciones lleguen al usuario con solo volver a ejecutar el Paso 1, sin
tener que cerrar y reabrir el cuaderno.
"""

import glob
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

import pandas as pd

VERSION = "2026-09-07.8"

DATOS = "datos"
RAIZ_DRIVE = "/content/drive/MyDrive"


def preparar():
    # inflacion_por_marca puede haber quedado importado de una ejecucion
    # anterior; sin recargarlo, el codigo nuevo que se acaba de descargar no
    # se usa y aparecen errores de funciones que "no existen".
    import importlib
    try:
        import inflacion_por_marca
        importlib.reload(inflacion_por_marca)
    except Exception:
        pass

    os.makedirs(DATOS, exist_ok=True)
    hay_unar = shutil.which("unar") is not None
    print(f"Listo.  (version del codigo: {VERSION})")
    if not hay_unar:
        print("Aviso: no se instalo el descompresor. Tendras que subir los CSV\n"
              "       ya descomprimidos a la carpeta de Drive.")
    return hay_unar


def _mb(ruta):
    return os.path.getsize(ruta) / 1e6


def ubicar(carpeta_en_drive):
    """Devuelve la ruta de la carpeta de Drive y muestra que hay adentro."""
    carpeta = os.path.join(RAIZ_DRIVE, carpeta_en_drive)

    if not os.path.isdir(carpeta):
        print(f"No existe la carpeta: {carpeta}\n")
        if os.path.isdir(RAIZ_DRIVE):
            print("Carpetas que tienes en Mi unidad:")
            for n in sorted(os.listdir(RAIZ_DRIVE)):
                if os.path.isdir(os.path.join(RAIZ_DRIVE, n)):
                    print("  ", n)
        return carpeta

    comprimidos = sorted(glob.glob(os.path.join(carpeta, "*.rar")) +
                         glob.glob(os.path.join(carpeta, "*.zip")))
    sueltos = sorted(glob.glob(os.path.join(carpeta, "*.csv")))

    print(f"Carpeta: {carpeta}\n")
    if comprimidos:
        print("Comprimidos (se extraen en el Paso 4):")
        for f in comprimidos:
            print(f"   {os.path.basename(f):<24} {_mb(f):>8,.0f} MB")
    if sueltos:
        print("\nCSV ya listos:")
        for f in sueltos:
            print(f"   {os.path.basename(f):<24} {_mb(f):>8,.0f} MB")
    if not comprimidos and not sueltos:
        print("La carpeta esta vacia o no tiene .rar ni .csv")
    return carpeta


def _aplanar():
    """Sube al nivel de datos/ los CSV que quedaron dentro de subcarpetas.
    Los comprimidos de QQP guardan los archivos en una carpeta por anio, y los
    patrones con comodin buscan en datos/, no adentro de esas carpetas."""
    movidos = 0
    for raiz, _, archivos in os.walk(DATOS, topdown=False):
        if os.path.abspath(raiz) == os.path.abspath(DATOS):
            continue
        for a in archivos:
            if a.lower().endswith(".csv"):
                destino = os.path.join(DATOS, a)
                if not os.path.exists(destino):
                    shutil.move(os.path.join(raiz, a), destino)
                    movidos += 1
        try:
            os.rmdir(raiz)
        except OSError:
            pass
    return movidos


def anio_de(nombre):
    """Saca el anio del nombre de un archivo de QQP.

    Los nombres traen numeros de pieza pegados al anio ("192015.csv" es la
    pieza 19 de 2015), asi que una busqueda simple de cuatro digitos puede
    leer "1920" donde en realidad dice pieza 19 + anio 2015. Se toman todas
    las secuencias de cuatro digitos, se descartan las que no son un anio
    plausible y se conserva la ultima: el anio va al final del nombre.
    """
    base = os.path.basename(nombre)
    candidatos = [int(base[i:i + 4]) for i in range(len(base) - 3)
                  if base[i:i + 4].isdigit()]
    plausibles = [a for a in candidatos if 2000 <= a <= 2035]
    return str(plausibles[-1]) if plausibles else None


def anios_disponibles():
    """Cuenta cuantos archivos hay de cada anio.

    QQP no nombra igual todos los anios: unos traen "01-2024_01.csv" (mes,
    anio, pieza) y otros "012015.csv" (pieza y anio, sin mes). Lo unico
    confiable en el nombre es el anio; el mes se filtra despues leyendo la
    fecha de cada registro.
    """
    cuenta = Counter()
    if not os.path.isdir(DATOS):
        return cuenta
    for f in os.listdir(DATOS):
        if f.lower().endswith(".csv"):
            a = anio_de(f)
            if a:
                cuenta[a] += 1
    return cuenta


def _sugerir_patrones(cuenta):
    print("\nAnios disponibles (patron y cuantos archivos tiene cada uno):")
    for anio in sorted(cuenta):
        print(f"   *{anio}*.csv     {cuenta[anio]} archivos")
    print("\nCopia dos de estos patrones al Paso 5, y elige el mes en el Paso 6.")


def _anios_de(nombres):
    c = Counter()
    for f in nombres:
        a = anio_de(f)
        if a:
            c[a] += 1
    return c


def inspeccionar(carpeta, comprimidos="", cuantos=6):
    """Muestra que archivos trae cada comprimido, SIN extraerlo.

    Es la unica forma de saber si un .rar corresponde a su nombre antes de
    gastar minutos extrayendolo.
    """
    if comprimidos.strip():
        nombres = [n.strip() for n in comprimidos.split(",") if n.strip()]
    else:
        nombres = sorted(os.path.basename(f) for f in
                         glob.glob(os.path.join(carpeta, "*.rar")) +
                         glob.glob(os.path.join(carpeta, "*.zip")))

    for nombre in nombres:
        origen = os.path.join(carpeta, nombre)
        print(f"--- {nombre}")
        if not os.path.exists(origen):
            print("    NO ENCONTRADO\n")
            continue
        r = subprocess.run(["lsar", origen], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"    no pude leerlo: {(r.stderr or r.stdout)[:200]}\n")
            continue
        lineas = [l.strip() for l in r.stdout.splitlines()[1:] if l.strip()]
        csvs = [l for l in lineas if l.lower().endswith(".csv")]
        for l in csvs[:cuantos]:
            print("   ", l)
        if len(csvs) > cuantos:
            print(f"    ... y {len(csvs)-cuantos} archivos mas")
        anios = _anios_de(csvs)
        if anios:
            print("    anios adentro:",
                  ", ".join(f"{a} ({anios[a]})" for a in sorted(anios)))
        print()


def limpiar():
    """Vacia datos/. Util cuando quedaron archivos de corridas anteriores que
    ya no corresponden a los anios que se quieren comparar."""
    if os.path.isdir(DATOS):
        shutil.rmtree(DATOS)
    os.makedirs(DATOS, exist_ok=True)
    print("Carpeta datos/ vaciada.\n")


def extraer(carpeta, comprimidos, limpiar_antes=True):
    """Extrae los comprimidos indicados y deja todos los CSV en datos/.

    Reporta que anios aporto cada comprimido, porque el nombre del archivo no
    garantiza su contenido: conviene verlo antes de elegir los periodos.
    """
    if limpiar_antes:
        limpiar()
    os.makedirs(DATOS, exist_ok=True)

    for nombre in [n.strip() for n in comprimidos.split(",") if n.strip()]:
        origen = os.path.join(carpeta, nombre)
        if not os.path.exists(origen):
            print(f"NO ENCONTRADO: {nombre}")
            continue

        antes = set(os.listdir(DATOS))
        print(f"Extrayendo {nombre} ... (puede tardar varios minutos)")
        r = subprocess.run(["unar", "-q", "-f", "-D", "-o", DATOS, origen],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  FALLO: {(r.stderr or r.stdout)[:300]}")
            continue

        _aplanar()
        nuevos = [f for f in os.listdir(DATOS)
                  if f not in antes and f.lower().endswith(".csv")]
        anios = _anios_de(nuevos)
        if anios:
            detalle = ", ".join(f"{a} ({anios[a]} archivos)" for a in sorted(anios))
            print(f"  ok -> aporto: {detalle}")
            if not any(a in nombre for a in anios):
                print(f"  OJO: el archivo se llama '{nombre}' pero su contenido")
                print(f"       es de otro anio. Usa el anio real al elegir el periodo.")
        elif nuevos:
            print(f"  ok -> {len(nuevos)} archivos, sin anio legible en el nombre:")
            for f in sorted(nuevos)[:5]:
                print(f"        {f}")
        else:
            print("  ok, pero no agrego ningun archivo nuevo (ya estaban).")

    for f in glob.glob(os.path.join(carpeta, "*.csv")):
        destino = os.path.join(DATOS, os.path.basename(f))
        if not os.path.exists(destino):
            shutil.copy(f, destino)

    csvs = sorted(f for f in os.listdir(DATOS) if f.lower().endswith(".csv"))
    print(f"\n{len(csvs)} archivos CSV en total.")

    cuenta = anios_disponibles()
    if cuenta:
        _sugerir_patrones(cuenta)
    elif csvs:
        print("\nNo pude leer el anio de estos nombres:")
        for f in csvs[:20]:
            print("  ", f)
    else:
        print("No quedo ningun CSV. Revisa si la extraccion dijo 'FALLO'.")
    return csvs


def _diagnostico():
    print("=" * 60)
    print("QUE HAY EN datos/ AHORA MISMO")
    print("=" * 60)

    if not os.path.isdir(DATOS):
        print("\nNo existe la carpeta datos/. Ejecuta los Pasos 3 y 4.")
        return

    todo = sorted(os.listdir(DATOS))
    if not todo:
        print("\nLa carpeta esta VACIA.")
        print("El Paso 4 no dejo ningun archivo: vuelve a ejecutarlo y fijate")
        print("si dijo 'ok' o 'fallo' al extraer.")
        return

    carpetas = [f for f in todo if os.path.isdir(os.path.join(DATOS, f))]
    csvs = [f for f in todo if f.lower().endswith(".csv")]

    if carpetas:
        print(f"\nHay {len(carpetas)} CARPETA(S), no archivos sueltos:")
        for c in carpetas[:10]:
            dentro = os.listdir(os.path.join(DATOS, c))
            print(f"   {c}/   ({len(dentro)} archivos adentro)")
            for d in sorted(dentro)[:3]:
                print(f"      {d}")
        print("\n-> Vuelve a ejecutar el Paso 4: saca los archivos de las carpetas.")

    if csvs:
        print(f"\n{len(csvs)} archivos CSV:")
        for f in csvs[:25]:
            print("   ", f)
        if len(csvs) > 25:
            print(f"    ... y {len(csvs)-25} mas")
        cuenta = anios_disponibles()
        if cuenta:
            _sugerir_patrones(cuenta)
        else:
            print("\nNo pude leer el anio de estos nombres.")
            print("Mandame esta lista y ajusto el patron.")


def revisar(patron_base, patron_actual):
    """Comprueba que los dos patrones encuentren archivos. Si no, explica."""
    ok = True
    for etiqueta, patron in (("BASE  (año viejo)", patron_base),
                             ("ACTUAL(año nuevo)", patron_actual)):
        hallados = sorted(glob.glob(os.path.join(DATOS, patron)))
        print(f"{etiqueta}:")
        if hallados:
            for f in hallados:
                print(f"   {os.path.basename(f):<24} {_mb(f):>8,.0f} MB")
        else:
            ok = False
            print("   *** ningun archivo coincide ***")
        print()

    if ok:
        print("Listo, pasa al Paso 6.")
        return True
    _diagnostico()
    raise SystemExit(
        "\nDETENIDO en el Paso 5: los patrones no encuentran archivos.\n"
        "Corrige el patron arriba con alguno de los sugeridos y vuelve a "
        "ejecutar este paso.")


def calcular(patron_base, patron_actual, producto="", marca="", categoria="",
             estado="", cadena="", mes=0, por_cadena=True, min_obs=3,
             salida="resultado.csv"):
    """Corre el analisis y muestra el reporte."""
    for etiqueta, patron in (("BASE", patron_base), ("ACTUAL", patron_actual)):
        if not glob.glob(os.path.join(DATOS, patron)):
            print(f"El patron {etiqueta} ({patron}) no encuentra ningun archivo.\n")
            _diagnostico()
            return False

    cmd = [sys.executable, "inflacion_por_marca.py",
           "--base", os.path.join(DATOS, patron_base),
           "--actual", os.path.join(DATOS, patron_actual),
           "--min-obs", str(min_obs),
           "--csv", salida]

    for bandera, valor in (("--producto", producto), ("--marca", marca),
                           ("--categoria", categoria), ("--estado", estado),
                           ("--cadena", cadena)):
        if valor and valor.strip():
            cmd += [bandera] + valor.split()
    if mes:
        cmd += ["--mes", str(int(mes))]
    else:
        print("AVISO: sin mes se mezclan todos los meses del anio y el\n"
              "       resultado no sirve. Pon un mes en el Paso 6.\n")
    if por_cadena:
        cmd.append("--por-cadena")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print("--- detalle del error ---")
        print(proc.stderr[-3000:])
    return proc.returncode == 0


# --------------------------------------------------------------------------
# Procesar sin descomprimir el anio completo
# --------------------------------------------------------------------------
#
# Un anio de QQP ocupa cerca de 5 GB descomprimido, repartido en decenas de
# piezas de unos 100 MB. Descomprimir dos anios llena el disco de Colab y la
# extraccion se queda a medias. Aqui se saca una pieza, se filtra, se guarda
# lo poco que sobrevive y se borra la pieza antes de pasar a la siguiente:
# el disco nunca tiene mas de un archivo a la vez.

TEMPORAL = "_pieza"


def _piezas_de(ruta_comprimido):
    r = subprocess.run(["lsar", ruta_comprimido], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [l.strip() for l in r.stdout.splitlines()[1:]
            if l.strip().lower().endswith(".csv")]


def _importar_ipm():
    """Importa inflacion_por_marca recargandolo si ya estaba en memoria."""
    import importlib
    import inflacion_por_marca as ipm
    if not hasattr(ipm, "detectar_separador"):
        importlib.reload(ipm)
    return ipm


def _filtrar_pieza(ruta_csv, mes, filtros, tam_bloque=400_000):
    """Lee una pieza por bloques y devuelve solo las filas que interesan."""
    ipm = _importar_ipm()

    class Args:
        pass
    args = Args()
    for k in ("producto", "marca", "categoria", "estado", "cadena"):
        valor = filtros.get(k, "")
        setattr(args, k, valor.split() if valor and valor.strip() else None)
    args.mes = mes or None

    trozos = []
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            trozos = []
            sep = ipm.detectar_separador(ruta_csv, enc)
            for bloque in pd.read_csv(ruta_csv, encoding=enc, sep=sep,
                                      low_memory=False, on_bad_lines="skip",
                                      chunksize=tam_bloque):
                bloque = ipm.normalizar(bloque)
                bloque = ipm.filtrar(bloque, args)
                if not bloque.empty:
                    trozos.append(bloque)
            break
        except UnicodeDecodeError:
            continue
    return pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()


def cosechar(carpeta, comprimido, mes, filtros, guardar_en):
    """Recorre las piezas de un comprimido y guarda solo las filas filtradas.

    Devuelve la ruta del CSV chico resultante, o None si no sobrevivio nada.
    """
    origen = os.path.join(carpeta, comprimido)
    if not os.path.exists(origen):
        print(f"NO ENCONTRADO: {comprimido}")
        return None

    piezas = _piezas_de(origen)
    if not piezas:
        print(f"No pude leer el contenido de {comprimido}")
        return None

    print(f"{comprimido}: {len(piezas)} piezas")
    reunido, filas = [], 0

    for i, pieza in enumerate(piezas, 1):
        shutil.rmtree(TEMPORAL, ignore_errors=True)
        r = subprocess.run(["unar", "-q", "-f", "-o", TEMPORAL, origen, pieza],
                           capture_output=True, text=True)
        sacados = []
        for raiz, _, archivos in os.walk(TEMPORAL):
            sacados += [os.path.join(raiz, a) for a in archivos
                        if a.lower().endswith(".csv")]
        if r.returncode != 0 or not sacados:
            print(f"\r  pieza {i}/{len(piezas)}: no se pudo extraer      ")
            continue

        try:
            chico = _filtrar_pieza(sacados[0], mes, filtros)
        except Exception as e:                      # una pieza corrupta no
            print(f"\r  pieza {i}/{len(piezas)}: error ({e})      ")  # detiene todo
            chico = None
        finally:
            shutil.rmtree(TEMPORAL, ignore_errors=True)

        if chico is not None and not chico.empty:
            reunido.append(chico)
            filas += len(chico)
        print(f"\r  pieza {i}/{len(piezas)}   filas utiles: {filas:,}",
              end="", flush=True)

    print()
    if not reunido:
        print("  no sobrevivio ninguna fila con esos filtros")
        return None

    pd.concat(reunido, ignore_index=True).to_csv(guardar_en, index=False,
                                                 encoding="utf-8")
    tam = os.path.getsize(guardar_en) / 1e6
    print(f"  guardado: {guardar_en}  ({filas:,} filas, {tam:,.1f} MB)")
    return guardar_en


def analizar(carpeta, comprimido_base, comprimido_actual, mes, filtros,
             por_cadena=True, min_obs=3, salida="resultado.csv"):
    """Cosecha los dos anios y corre el analisis. Es todo el flujo en uno."""
    if not mes:
        print("FALTA EL MES: sin el se mezclan los doce meses del anio y el\n"
              "resultado no significa nada.")
        return False
    if not any(v.strip() for v in filtros.values() if v):
        print("FALTA UN FILTRO: pon al menos un producto o una categoria.")
        return False

    meses = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    print(f"Buscando {meses[mes]} en cada anio. Esto tarda varios minutos.\n")

    base = cosechar(carpeta, comprimido_base, mes, filtros, "_base.csv")
    if not base:
        print("\nNo se pudo preparar el periodo BASE.")
        return False
    actual = cosechar(carpeta, comprimido_actual, mes, filtros, "_actual.csv")
    if not actual:
        print("\nNo se pudo preparar el periodo ACTUAL.")
        return False

    print()
    cmd = [sys.executable, "inflacion_por_marca.py",
           "--base", base, "--actual", actual,
           "--min-obs", str(min_obs), "--csv", salida]
    if por_cadena:
        cmd.append("--por-cadena")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print("--- detalle del error ---")
        print(proc.stderr[-3000:])
    return proc.returncode == 0


def ver_una_pieza(carpeta, comprimido, cual=1):
    """Extrae UNA pieza y muestra sus primeras lineas tal como vienen.

    Sirve para ver el formato real del archivo (separador, encabezado) cuando
    la lectura falla.
    """
    ipm = _importar_ipm()

    origen = os.path.join(carpeta, comprimido)
    if not os.path.exists(origen):
        print(f"NO ENCONTRADO: {comprimido}")
        return

    piezas = _piezas_de(origen)
    if not piezas:
        print("No pude leer el contenido del comprimido.")
        return

    pieza = piezas[min(cual, len(piezas)) - 1]
    print(f"Sacando {pieza} de {comprimido} ...\n")
    shutil.rmtree(TEMPORAL, ignore_errors=True)
    r = subprocess.run(["unar", "-q", "-f", "-o", TEMPORAL, origen, pieza],
                       capture_output=True, text=True)
    sacados = []
    for raiz, _, archivos in os.walk(TEMPORAL):
        sacados += [os.path.join(raiz, a) for a in archivos
                    if a.lower().endswith(".csv")]
    if r.returncode != 0 or not sacados:
        print("No se pudo extraer:", (r.stderr or r.stdout)[:300])
        shutil.rmtree(TEMPORAL, ignore_errors=True)
        return

    ruta = sacados[0]
    print(f"tamano: {os.path.getsize(ruta)/1e6:,.0f} MB\n")
    lineas, enc = ipm.primeras_lineas(ruta, 3)
    print(f"codificacion que funciono: {enc}")
    if enc:
        print(f"separador detectado: {ipm.detectar_separador(ruta, enc)!r}\n")
    print("PRIMERAS LINEAS TAL COMO VIENEN:")
    print("-" * 70)
    for i, l in enumerate(lineas, 1):
        print(f"{i}| {l[:300]}")
    print("-" * 70)

    try:
        df = pd.read_csv(ruta, nrows=3, encoding=enc,
                         sep=ipm.detectar_separador(ruta, enc))
        print("\nColumnas que leyo pandas:")
        for c in list(df.columns)[:20]:
            print("   ", c)
    except Exception as e:
        print("\npandas no pudo leerlo:", e)
    finally:
        shutil.rmtree(TEMPORAL, ignore_errors=True)


def inventario(carpeta):
    """Tabla de: comprimido -> anio que realmente trae adentro.

    El nombre del .rar no siempre corresponde a su contenido, y descubrirlo
    hasta el final cuesta mucho tiempo. lsar lee la lista de archivos sin
    descomprimir, asi que revisar todos los comprimidos toma segundos.
    """
    archivos = sorted(glob.glob(os.path.join(carpeta, "*.rar")) +
                      glob.glob(os.path.join(carpeta, "*.zip")))
    if not archivos:
        print("No hay .rar ni .zip en", carpeta)
        return {}

    print(f"{'COMPRIMIDO':<22} {'AÑO REAL':>10} {'PIEZAS':>8}   {'CUADRA?'}")
    print("-" * 62)
    mapa = {}
    for ruta in archivos:
        nombre = os.path.basename(ruta)
        piezas = _piezas_de(ruta)
        if not piezas:
            print(f"{nombre:<22} {'?':>10} {'?':>8}   no pude leerlo")
            continue
        anios = _anios_de(piezas)
        if not anios:
            print(f"{nombre:<22} {'?':>10} {len(piezas):>8}   sin anio en los nombres")
            continue
        real = anios.most_common(1)[0][0]
        cuadra = "si" if real in nombre else f"NO (se llama {nombre.split('.')[0]})"
        print(f"{nombre:<22} {real:>10} {len(piezas):>8}   {cuadra}")
        mapa[nombre] = real

    por_anio = {}
    for nombre, anio in mapa.items():
        por_anio.setdefault(anio, []).append(nombre)
    print("\nPara comparar dos anios, usa estos comprimidos:")
    for anio in sorted(por_anio):
        print(f"   {anio}: {', '.join(sorted(por_anio[anio]))}")
    if len(por_anio) < 2:
        print("\nOJO: solo hay un anio disponible. Se necesitan dos para")
        print("     medir inflacion. Revisa la descarga de los demas archivos.")
    return mapa
