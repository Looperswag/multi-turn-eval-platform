"""快速探测：试几组 (base_url, model_id) 组合，找出 ARK 能通的端点。"""
import os
import sys
from pathlib import Path


def load_env(env_path: Path) -> None:
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if key.strip() and value:
            os.environ.setdefault(key.strip(), value)


def probe(base_url: str, model_id: str, api_key: str) -> tuple[bool, str]:
    from volcenginesdkarkruntime import Ark
    client = Ark(base_url=base_url, api_key=api_key, timeout=30)
    try:
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "回复严格 JSON：{\"ok\": true}"}],
            temperature=0.1,
        )
        content = completion.choices[0].message.content or ""
        return True, content[:120]
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    load_env(repo_root / "backend" / ".env")
    api_key = os.environ.get("ARK_API_KEY", "")
    if not api_key:
        print("[FAIL] ARK_API_KEY missing")
        return 1

    env_base = os.environ.get("ARK_BASE_URL", "")
    env_model = os.environ.get("ARK_DEFAULT_MODEL", "")

    combos = [
        (env_base, env_model),
        ("https://ark.cn-beijing.volces.com/api/v3", env_model),
        ("https://ark.cn-beijing.volces.com/api/coding/v3", env_model),
        ("https://ark.cn-beijing.volces.com/api/coding/v3", "ark-code-latest"),
        ("https://ark.cn-beijing.volces.com/api/v3", "doubao-seed-2-0-pro-260215"),
    ]
    # 去重
    seen = set()
    unique: list[tuple[str, str]] = []
    for b, m in combos:
        if (b, m) in seen or not b or not m:
            continue
        seen.add((b, m))
        unique.append((b, m))

    print(f"api_key prefix: {api_key[:8]}...{api_key[-4:]}\n")
    for base, model in unique:
        print(f"-> base_url = {base}")
        print(f"   model    = {model}")
        ok, msg = probe(base, model, api_key)
        if ok:
            print(f"   [OK] reply head: {msg}")
        else:
            print(f"   [FAIL] {msg}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
