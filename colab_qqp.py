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

VERSION = "2026-09-07.2"

DATOS = "datos"
RAIZ_DRIVE = "/content/drive/MyDrive"


def preparar():
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


def anios_disponibles():
    """Cuenta cuantos archivos hay de cada anio.

    QQP no nombra igual todos los anios: unos traen "01-2024_01.csv" (mes,
    anio, pieza) y otros "012015.csv" (pieza y anio, sin mes). Lo unico
    confiable en el nombre es el anio de cuatro digitos; el mes se filtra
    despues leyendo la fecha de cada registro.
    """
    cuenta = Counter()
    if not os.path.isdir(DATOS):
        return cuenta
    for f in os.listdir(DATOS):
        if not f.lower().endswith(".csv"):
            continue
        for anio in re.findall(r"(19|20)(\d{2})", f):
            cuenta["".join(anio)] += 1
            break
    return cuenta


def _sugerir_patrones(cuenta):
    print("\nAnios disponibles (patron y cuantos archivos tiene cada uno):")
    for anio in sorted(cuenta):
        print(f"   *{anio}*.csv     {cuenta[anio]} archivos")
    print("\nCopia dos de estos patrones al Paso 5, y elige el mes en el Paso 6.")


def extraer(carpeta, comprimidos):
    """Extrae los comprimidos indicados y deja todos los CSV en datos/."""
    os.makedirs(DATOS, exist_ok=True)

    for nombre in [n.strip() for n in comprimidos.split(",") if n.strip()]:
        origen = os.path.join(carpeta, nombre)
        if not os.path.exists(origen):
            print(f"NO ENCONTRADO: {nombre}")
            continue
        print(f"Extrayendo {nombre} ... (puede tardar varios minutos)")
        r = subprocess.run(["unar", "-q", "-f", "-D", "-o", DATOS, origen],
                           capture_output=True, text=True)
        print("  ok" if r.returncode == 0
              else f"  fallo: {(r.stderr or r.stdout)[:300]}")

    movidos = _aplanar()
    if movidos:
        print(f"\n{movidos} archivos sacados de sus subcarpetas")

    for f in glob.glob(os.path.join(carpeta, "*.csv")):
        destino = os.path.join(DATOS, os.path.basename(f))
        if not os.path.exists(destino):
            shutil.copy(f, destino)

    csvs = sorted(f for f in os.listdir(DATOS) if f.lower().endswith(".csv"))
    print(f"\n{len(csvs)} archivos CSV listos.")

    cuenta = anios_disponibles()
    if cuenta:
        _sugerir_patrones(cuenta)
    elif csvs:
        print("\nNo pude leer el anio de estos nombres:")
        for f in csvs[:20]:
            print("  ", f)
    else:
        print("No quedo ningun CSV. Revisa si la extraccion dijo 'fallo'.")
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
    else:
        _diagnostico()
    return ok


def calcular(patron_base, patron_actual, producto="", marca="", categoria="",
             estado="", cadena="", mes=0, por_cadena=True, min_obs=3,
             salida="resultado.csv"):
    """Corre el analisis y muestra el reporte."""
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
