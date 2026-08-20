"""기존 유저에 로그인 자격(email/비밀번호)을 부여 — AUTH_ENABLED 부트스트랩/테스트용.

사용:
  uv run python set_user_password.py --list                         # uuid 후보 몇 개 보기
  uv run python set_user_password.py --uuid <uuid> --email a@b.com --password <pw>

비밀번호는 bcrypt 해시로만 저장한다(평문 저장 안 함).
"""

from __future__ import annotations

import argparse

from backend.app.services.auth import hash_password
from shared.database.repositories.users import list_users, set_user_credentials


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="uuid 후보 목록")
    ap.add_argument("--uuid")
    ap.add_argument("--email")
    ap.add_argument("--password")
    a = ap.parse_args()

    if a.list:
        for u in list_users(limit=10):
            print(f"{u['uuid']}  | {u.get('occupation')} · {u.get('district')}")
        return

    if not (a.uuid and a.email and a.password):
        ap.error("--uuid --email --password 를 모두 주거나 --list 를 쓰세요.")

    ok = set_user_credentials(a.uuid, a.email, hash_password(a.password))
    print("자격 설정 완료" if ok else f"해당 uuid 없음: {a.uuid}")


if __name__ == "__main__":
    main()
