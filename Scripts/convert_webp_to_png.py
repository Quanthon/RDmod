"""Convert WebP images to PNG without resizing or overwriting existing files.

Usage: python Scripts/convert_webp_to_png.py [source_dir] [output_dir]
Requires: pip install Pillow
"""

import argparse
from pathlib import Path

from PIL import Image


def convert(source: Path, output: Path) -> dict:
    if source.is_file() and source.suffix.lower() == ".webp":
        paths = [source]
    elif source.is_dir():
        paths = sorted(source.iterdir())
    else:
        raise ValueError(f"请选择存在的 WebP 文件或目录：{source}")
    output.mkdir(parents=True, exist_ok=True)
    result = {"converted": 0, "skipped": 0, "errors": []}
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".webp":
            continue
        target = output / (path.stem + ".png")
        try:
            with Image.open(path) as image:
                if getattr(image, "is_animated", False):
                    raise ValueError("Animated WebP requires separate frame handling")
                image.load()
                with target.open("xb") as stream:
                    try:
                        image.save(stream, format="PNG")
                    except Exception:
                        stream.close()
                        target.unlink()
                        raise
            result["converted"] += 1
        except FileExistsError:
            result["skipped"] += 1
        except Exception as error:
            result["errors"].append(f"{path.name}: {error}")
    return result


def prompt_convert() -> int:
    try:
        raw = input("请输入或拖入 WebP 文件路径，然后按回车：\n").strip().strip('"')
        source = Path(raw)
        if not raw or not source.is_file() or source.suffix.lower() != ".webp":
            raise ValueError("请选择一个存在的 .webp 文件。")
        summary = convert(source, source.parent)
        target = source.with_suffix(".png")
        if summary["errors"]:
            print("转换失败：" + "\n".join(summary["errors"]))
            return 1
        if summary["skipped"]:
            print(f"已存在同名 PNG，未覆盖：{target}")
        else:
            print(f"转换完成：{target}")
        return 0
    except (ValueError, OSError, EOFError) as error:
        print(f"转换失败：{error}")
        return 1


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path,
                        default=root / "截图" / "已完成")
    parser.add_argument("output", nargs="?", type=Path,
                        default=root / "截图" / "已完成_PNG")
    parser.add_argument("--prompt", action="store_true")
    args = parser.parse_args()
    if args.prompt:
        raise SystemExit(prompt_convert())
    summary = convert(args.source, args.output)
    print(summary)
    raise SystemExit(bool(summary["errors"]))
