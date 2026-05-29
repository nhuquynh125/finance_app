#!/usr/bin/env python3
# setup_theme.py
"""
Script cài đặt theme mới + logo cho Finance AI.

Chạy một lần từ thư mục gốc của project:
    python setup_theme.py

Script sẽ:
  1. Copy logo.png vào đúng vị trí
  2. Backup các file UI cũ
  3. Copy các file theme mới vào đúng vị trí
  4. Cập nhật dashboard_frame.py với màu mới
"""

import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ── Màu palette mới (từ logo) ─────────────────────────────────────────────────
NAVY_PRIMARY   = "#0B2A4A"
NAVY_LIGHT     = "#1A6BAF"
MINT_GREEN     = "#1D9E75"
ORANGE_ACCENT  = "#E8921A"
BG_LIGHT_BLUE  = "#F0F6FF"
BORDER_BLUE    = "#D0E4F7"


def backup_file(path: Path):
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        print(f"  [backup] {path.name} → {backup.name}")


def copy_output_to_project(filename: str, dest_relative: str):
    """Copy file từ outputs vào đúng vị trí trong project."""
    src = BASE_DIR / "outputs" / filename
    dst = BASE_DIR / dest_relative
    if not src.exists():
        print(f"  [skip] {filename} — không tìm thấy trong outputs/")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup_file(dst)
    shutil.copy2(src, dst)
    print(f"  [copy] {filename} → {dest_relative}")
    return True


def setup_logo():
    """Copy logo vào thư mục gốc project."""
    # Tìm logo trong nhiều vị trí
    candidates = [
        BASE_DIR / "logo.png",
        BASE_DIR / "logo-_k_nền.png",
        BASE_DIR / "assets" / "logo.png",
    ]
    for c in candidates:
        if c.exists():
            dst = BASE_DIR / "logo.png"
            if c != dst:
                shutil.copy2(c, dst)
                print(f"  [logo] Copied {c.name} → logo.png")
            else:
                print(f"  [logo] logo.png đã ở đúng vị trí")
            return True
    print("  [logo] ⚠ Không tìm thấy logo! Hãy copy logo.png vào thư mục gốc project.")
    return False


def patch_dashboard_colors():
    """Cập nhật màu sắc trong dashboard_frame.py."""
    dash_path = BASE_DIR / "app" / "ui" / "dashboard_frame.py"
    if not dash_path.exists():
        print("  [skip] dashboard_frame.py không tìm thấy")
        return

    content = dash_path.read_text(encoding="utf-8")
    original = content

    # Cập nhật màu bar chart (income/expense)
    content = content.replace(
        'color="#1D9E75", alpha=0.85, label="Thu"',
        'color="#1D9E75", alpha=0.9, label="Thu"'
    )
    content = content.replace(
        'color="#E24B4A", alpha=0.85, label="Chi"',
        'color="#E8921A", alpha=0.9, label="Chi"'   # Cam từ logo
    )

    # Cập nhật màu toolbar background
    content = content.replace(
        'bar.setStyleSheet("background:#fff; border-bottom:1px solid #e8e8e8;")',
        f'bar.setStyleSheet("background:#FFFFFF; border-bottom:1px solid {BORDER_BLUE};")'
    )

    if content != original:
        backup_file(dash_path)
        dash_path.write_text(content, encoding="utf-8")
        print("  [patch] dashboard_frame.py — màu biểu đồ cập nhật")
    else:
        print("  [skip] dashboard_frame.py — không có thay đổi cần thiết")


def patch_budget_frame_colors():
    """Cập nhật màu progress bar trong budget_frame."""
    budget_path = BASE_DIR / "app" / "ui" / "budget_frame.py"
    if not budget_path.exists():
        return
    content = budget_path.read_text(encoding="utf-8")
    original = content

    # Cập nhật màu progress OK → mint/navy gradient
    content = content.replace(
        "prog_color   = '#1D9E75'",
        f"prog_color   = '{MINT_GREEN}'"
    )

    if content != original:
        backup_file(budget_path)
        budget_path.write_text(content, encoding="utf-8")
        print("  [patch] budget_frame.py — màu cập nhật")


def create_assets_dir():
    """Tạo thư mục assets nếu chưa có."""
    assets = BASE_DIR / "assets"
    assets.mkdir(exist_ok=True)
    logo = BASE_DIR / "logo.png"
    if logo.exists():
        shutil.copy2(logo, assets / "logo.png")
        print(f"  [assets] logo.png → assets/logo.png")


def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║   Finance AI — Theme Setup (Navy/Logo)   ║")
    print("╚══════════════════════════════════════════╝\n")

    print("1. Thiết lập logo...")
    setup_logo()
    create_assets_dir()

    print("\n2. Cài đặt theme files...")
    # theme_engine.py
    copy_output_to_project("theme_engine.py", "app/core/theme_engine.py")
    # main_window.py
    copy_output_to_project("main_window.py",  "app/ui/main_window.py")
    # login_window.py
    copy_output_to_project("login_window.py", "app/ui/login_window.py")

    print("\n3. Patch màu sắc các frame...")
    patch_dashboard_colors()
    patch_budget_frame_colors()

    print("\n✅ Hoàn tất! Khởi động lại app để thấy thay đổi:")
    print("   python main.py\n")

    print("📝 Lưu ý:")
    print("   - Backup của các file gốc được lưu với đuôi .bak")
    print("   - Nếu có lỗi, khôi phục từ file .bak tương ứng")
    print("   - Logo cần đặt tại: <thư mục project>/logo.png\n")


if __name__ == "__main__":
    main()
