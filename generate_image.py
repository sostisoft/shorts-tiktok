#!/usr/bin/env python3
"""Generador de imágenes bajo demanda con FLUX.1 dev"""
import argparse
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from pipeline.image_gen import ImageGenerator


def main():
    parser = argparse.ArgumentParser(description="Genera imágenes con FLUX.1 dev")
    parser.add_argument("prompt", help="Descripción de la imagen")
    parser.add_argument("-o", "--output", help="Ruta de salida (default: output/ondemand/)")
    parser.add_argument("-W", "--width", type=int, default=1080, help="Ancho (default: 1080)")
    parser.add_argument("-H", "--height", type=int, default=1920, help="Alto (default: 1920)")
    parser.add_argument("--steps", type=int, default=25, help="Pasos de inferencia (default: 25)")
    parser.add_argument("--guidance", type=float, default=3.5, help="Guidance scale (default: 3.5)")
    parser.add_argument("--landscape", action="store_true", help="Formato horizontal 1920x1080")
    parser.add_argument("--square", action="store_true", help="Formato cuadrado 1024x1024")
    parser.add_argument("--model", choices=["dev", "schnell"], default="dev", help="Modelo (default: dev)")
    args = parser.parse_args()

    if args.landscape:
        args.width, args.height = 1920, 1080
    elif args.square:
        args.width, args.height = 1024, 1024

    gen = ImageGenerator(model=args.model)
    path = gen.generate_single(
        prompt=args.prompt,
        output_path=args.output,
        width=args.width,
        height=args.height,
        steps=args.steps,
        guidance=args.guidance,
    )
    print(f"\nImagen lista: {path}")


if __name__ == "__main__":
    main()
