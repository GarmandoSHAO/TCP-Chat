#!/usr/bin/env python3
"""
构建时图标生成工具

从 TCP-Chat.png 生成多尺寸 TCP-Chat.ico，
确保 EXE 文件图标、安装包图标与编辑器内 PNG 源图完全一致。

用法:
    python tools/build_icon.py                          # 默认：根目录 TCP-Chat.png
    python tools/build_icon.py --input path/to/png      # 指定输入
    python tools/build_icon.py --output path/to/ico     # 指定输出
    python tools/build_icon.py --force                  # 强制重建

退出码:
    0  = 成功（生成或跳过——ICO 已最新且不比 PNG 旧）
    1  = 源 PNG 不存在
    2  = Pillow 不可用
    3  = 转换失败
"""

import argparse
import os
import sys

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore


# ── 常量 ──────────────────────────────────────────────

DEFAULT_SIZES: tuple[int, ...] = (256, 128, 64, 48, 32, 24, 16)
"""ICO 中包含的尺寸列表，覆盖全部常见窗口缩放级别。"""

EXIT_OK = 0
EXIT_PNG_MISSING = 1
EXIT_NO_PILLOW = 2
EXIT_CONVERT_FAIL = 3


# ── 核心功能 ──────────────────────────────────────────


def build_icon(
    png_path: str = "TCP-Chat.png",
    ico_path: str = "TCP-Chat.ico",
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    force: bool = False,
) -> bool:
    """从 PNG 生成多尺寸 ICO 文件。

    使用 LANCZOS 高质量重采样，生成的 ICO 包含所有指定尺寸，
    确保在不同 DPI 和窗口缩放级别下图标清晰。

    Args:
        png_path: 源 PNG 文件路径。
        ico_path: 目标 ICO 文件路径。
        sizes:    ICO 中包含的尺寸列表，默认覆盖 16-256px。
        force:    是否强制重建。False 时仅在 ICO 不存在或比 PNG 旧时才重建。

    Returns:
        成功返回 True。

    Raises:
        FileNotFoundError: png_path 不存在。
        ImportError:       Pillow 未安装。
    """
    if not os.path.exists(png_path):
        raise FileNotFoundError(f"源 PNG 不存在: {png_path}")

    if Image is None:
        raise ImportError("Pillow 未安装，请运行: pip install Pillow")

    # 智能跳过：ICO 已最新则跳过
    if not force and os.path.exists(ico_path):
        png_mtime = os.path.getmtime(png_path)
        ico_mtime = os.path.getmtime(ico_path)
        if ico_mtime >= png_mtime:
            return True

    # 用 Pillow 打开 PNG 并生成多尺寸帧
    with Image.open(png_path) as src:
        frames: list[Image.Image] = []
        for size in sizes:
            resized = src.resize((size, size), Image.Resampling.LANCZOS)
            if resized.mode != "RGBA":
                resized = resized.convert("RGBA")
            frames.append(resized)

        # 写入 ICO：第一帧为主图，其余通过 append_images 附加
        frames[0].save(
            ico_path,
            format="ICO",
            append_images=frames[1:],
        )

    return True


# ── CLI 入口 ──────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        description="从 PNG 生成多尺寸 ICO 图标文件",
    )
    ap.add_argument(
        "--input",
        default="TCP-Chat.png",
        metavar="PATH",
        help="源 PNG 文件路径（默认: TCP-Chat.png）",
    )
    ap.add_argument(
        "--output",
        default="TCP-Chat.ico",
        metavar="PATH",
        help="目标 ICO 文件路径（默认: TCP-Chat.ico）",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="强制重建，即使 ICO 已最新",
    )
    ap.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=list(DEFAULT_SIZES),
        help=f"ICO 包含的尺寸列表（默认: {' '.join(map(str, DEFAULT_SIZES))}）",
    )
    args = ap.parse_args()

    try:
        result = build_icon(
            png_path=args.input,
            ico_path=args.output,
            sizes=tuple(args.sizes),
            force=args.force,
        )
    except FileNotFoundError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return EXIT_PNG_MISSING
    except ImportError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return EXIT_NO_PILLOW
    except Exception as e:
        print(f"[FAIL] ICO 生成失败: {e}", file=sys.stderr)
        return EXIT_CONVERT_FAIL

    if result:
        # 判断是跳过了还是生成了
        ico_mtime = os.path.getmtime(args.output) if os.path.exists(args.output) else 0
        png_mtime = os.path.getmtime(args.input) if os.path.exists(args.input) else 0
        if ico_mtime >= png_mtime and not args.force:
            print(f"  [OK] 图标已是最新: {args.output}")
        else:
            print(f"  [OK] 图标已生成: {args.output}")
        return EXIT_OK

    print("[FAIL] 未知错误", file=sys.stderr)
    return EXIT_CONVERT_FAIL


if __name__ == "__main__":
    sys.exit(main())
