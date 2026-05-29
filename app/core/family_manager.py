# app/core/family_manager.py  (file mới)
"""
Quản lý nhóm gia đình — tạo nhóm, tham gia, xem thành viên.

Dữ liệu lưu vào finance.db của user hiện tại (bảng family_groups, group_members
đã được tạo sẵn trong init_database()).

Cách dùng:
    from app.core.family_manager import FamilyManager
    fm = FamilyManager()

    # Tạo nhóm
    result = fm.create_group("Gia đình Nguyễn")
    print(result["invite_code"])   # "A3F9C2"

    # Tham gia nhóm
    result = fm.join_group("A3F9C2")

    # Xem nhóm hiện tại
    group = fm.get_my_group()
    members = fm.get_members(group["id"])
"""

from __future__ import annotations

import secrets
from typing import Optional
from app.data.models import get_connection
from user_session import session


class FamilyManager:
    """Quản lý nhóm gia đình trong Finance AI."""

    # ── Tạo nhóm ─────────────────────────────────────────────────────────────

    def create_group(self, name: str) -> dict:
        """
        Tạo nhóm gia đình mới.
        Mỗi user chỉ được tạo 1 nhóm (với tư cách owner).

        Trả về:
            {
              "success": bool,
              "message": str,
              "group_id": int,        # chỉ khi success=True
              "invite_code": str,     # 6 ký tự, chỉ khi success=True
              "name": str
            }
        """
        if not name.strip():
            return {"success": False, "message": "Tên nhóm không được để trống"}

        username = session.username
        invite_code = secrets.token_hex(3).upper()   # VD: "A3F9C2"

        with get_connection() as conn:
            # Kiểm tra đã là owner của nhóm nào chưa
            existing_owner = conn.execute(
                "SELECT id, name FROM family_groups WHERE owner_username=?",
                (username,)
            ).fetchone()
            if existing_owner:
                return {
                    "success": False,
                    "message": f"Bạn đã là chủ nhóm '{existing_owner['name']}'. "
                               "Hãy xóa nhóm cũ trước khi tạo nhóm mới."
                }

            # Kiểm tra đã là member của nhóm nào chưa
            existing_member = conn.execute("""
                SELECT fg.name FROM family_groups fg
                JOIN group_members gm ON fg.id = gm.group_id
                WHERE gm.username = ?
            """, (username,)).fetchone()
            if existing_member:
                return {
                    "success": False,
                    "message": f"Bạn đang là thành viên của nhóm '{existing_member['name']}'. "
                               "Hãy rời nhóm trước."
                }

            # Tạo nhóm
            cur = conn.execute("""
                INSERT INTO family_groups (name, owner_username, invite_code)
                VALUES (?, ?, ?)
            """, (name.strip(), username, invite_code))
            group_id = cur.lastrowid

            # Tự thêm owner vào danh sách thành viên
            conn.execute("""
                INSERT INTO group_members (group_id, username, role)
                VALUES (?, ?, 'owner')
            """, (group_id, username))

        return {
            "success": True,
            "group_id": group_id,
            "invite_code": invite_code,
            "name": name.strip(),
            "message": f"Đã tạo nhóm '{name.strip()}' thành công!"
        }

    # ── Tham gia nhóm ────────────────────────────────────────────────────────

    def join_group(self, invite_code: str) -> dict:
        """
        Tham gia nhóm bằng mã mời 6 ký tự.

        Trả về:
            {
              "success": bool,
              "message": str,
              "group_name": str,   # chỉ khi success=True
              "group_id": int
            }
        """
        code = invite_code.strip().upper()
        if len(code) != 6:
            return {"success": False, "message": "Mã mời phải có đúng 6 ký tự"}

        username = session.username

        with get_connection() as conn:
            # Tìm nhóm
            group = conn.execute(
                "SELECT * FROM family_groups WHERE invite_code=?", (code,)
            ).fetchone()
            if not group:
                return {"success": False, "message": f"Mã mời '{code}' không tồn tại"}

            # Không tự tham gia nhóm mình tạo (đã là owner/member)
            already = conn.execute("""
                SELECT role FROM group_members
                WHERE group_id=? AND username=?
            """, (group["id"], username)).fetchone()
            if already:
                role_text = "chủ nhóm" if already["role"] == "owner" else "thành viên"
                return {
                    "success": False,
                    "message": f"Bạn đã là {role_text} của nhóm '{group['name']}'"
                }

            # Thêm vào nhóm
            conn.execute("""
                INSERT INTO group_members (group_id, username, role)
                VALUES (?, ?, 'member')
            """, (group["id"], username))

        return {
            "success": True,
            "group_id": group["id"],
            "group_name": group["name"],
            "message": f"Đã tham gia nhóm '{group['name']}' thành công!"
        }

    # ── Rời nhóm ─────────────────────────────────────────────────────────────

    def leave_group(self) -> dict:
        """
        Rời nhóm hiện tại.
        Owner không thể rời — phải giải tán nhóm.
        """
        username = session.username
        group = self.get_my_group()
        if not group:
            return {"success": False, "message": "Bạn chưa tham gia nhóm nào"}

        if group["owner_username"] == username:
            return {
                "success": False,
                "message": "Bạn là chủ nhóm, không thể rời. "
                           "Hãy dùng 'Giải tán nhóm' để xóa nhóm."
            }

        with get_connection() as conn:
            conn.execute("""
                DELETE FROM group_members
                WHERE group_id=? AND username=?
            """, (group["id"], username))

        return {"success": True, "message": f"Đã rời nhóm '{group['name']}'"}

    def disband_group(self) -> dict:
        """Giải tán nhóm (chỉ owner). Xóa cả thành viên."""
        username = session.username
        with get_connection() as conn:
            group = conn.execute(
                "SELECT * FROM family_groups WHERE owner_username=?",
                (username,)
            ).fetchone()
            if not group:
                return {"success": False, "message": "Bạn không phải chủ nhóm nào"}

            conn.execute(
                "DELETE FROM group_members WHERE group_id=?", (group["id"],))
            conn.execute(
                "DELETE FROM family_groups WHERE id=?", (group["id"],))

        return {"success": True, "message": f"Đã giải tán nhóm '{group['name']}'"}

    # ── Truy vấn thông tin nhóm ───────────────────────────────────────────────

    def get_my_group(self) -> Optional[dict]:
        """
        Lấy thông tin nhóm mà user đang tham gia.
        Trả về None nếu chưa vào nhóm nào.
        """
        username = session.username
        with get_connection() as conn:
            row = conn.execute("""
                SELECT
                    fg.*,
                    gm.role AS my_role,
                    COUNT(gm2.username) AS member_count
                FROM family_groups fg
                JOIN group_members gm  ON fg.id = gm.group_id  AND gm.username = ?
                JOIN group_members gm2 ON fg.id = gm2.group_id
                GROUP BY fg.id
            """, (username,)).fetchone()
        return dict(row) if row else None

    def get_members(self, group_id: int) -> list[dict]:
        """Lấy danh sách thành viên của nhóm."""
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT
                    username,
                    role,
                    joined_at,
                    CASE role
                        WHEN 'owner'  THEN 'Chủ nhóm'
                        WHEN 'member' THEN 'Thành viên'
                        ELSE role
                    END AS role_display
                FROM group_members
                WHERE group_id = ?
                ORDER BY
                    CASE role WHEN 'owner' THEN 0 ELSE 1 END,
                    joined_at ASC
            """, (group_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_group_by_invite(self, invite_code: str) -> Optional[dict]:
        """Xem trước thông tin nhóm trước khi tham gia."""
        code = invite_code.strip().upper()
        with get_connection() as conn:
            group = conn.execute(
                "SELECT id, name, owner_username FROM family_groups WHERE invite_code=?",
                (code,)
            ).fetchone()
            if not group:
                return None
            count = conn.execute(
                "SELECT COUNT(*) as n FROM group_members WHERE group_id=?",
                (group["id"],)
            ).fetchone()
        result = dict(group)
        result["member_count"] = count["n"]
        return result
