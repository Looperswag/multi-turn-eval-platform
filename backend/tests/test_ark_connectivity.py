"""ARK Judge 连通性测试。

直接读 backend/.env，发起一次真实调用：
- 用 dim1 prompt 评一个简单 case
- 验证 API 可达、密钥有效、JSON 解析正常
"""
import os
import sys
import time
from pathlib import Path


def load_env(env_path: Path) -> dict[str, str]:
    """轻量 .env 解析，不依赖 python-dotenv。"""
    out: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            out[key] = value
            os.environ.setdefault(key, value)
    return out


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]  # platform/
    env_path = repo_root / "backend" / ".env"
    if not env_path.exists():
        print(f"[FAIL] .env not found at {env_path}")
        return 1
    env = load_env(env_path)
    api_key = env.get("ARK_API_KEY", "")
    base_url = env.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    model_id = env.get("ARK_DEFAULT_MODEL", "doubao-seed-2-0-pro-260215")

    print("=" * 60)
    print("ARK Judge Connectivity Test")
    print("=" * 60)
    print(f"  base_url      : {base_url}")
    print(f"  model_id      : {model_id}")
    print(f"  api_key       : {api_key[:8]}…{api_key[-4:]} (len={len(api_key)})")
    print()

    if not api_key:
        print("[FAIL] ARK_API_KEY is empty")
        return 1

    try:
        from volcenginesdkarkruntime import Ark
    except ImportError as exc:
        print(f"[FAIL] volcengine SDK import error: {exc}")
        print("       pip install 'volcengine-python-sdk[ark]'")
        return 1

    # 让 backend/app/services/eval_engine 的代码可被 import
    sys.path.insert(0, str(repo_root / "backend"))

    try:
        from app.services.eval_engine.prompts import build_dim1_prompt
        from app.services.eval_engine.judge_client import extract_json
    except Exception as exc:
        print(f"[WARN] cannot import platform code ({exc}); will use inline minimal prompt")
        build_dim1_prompt = None
        extract_json = None

    if build_dim1_prompt:
        history = [
            {"turn_index": 1, "user_query": "电风扇推荐 落地扇", "rewritten_query": None},
        ]
        current = {
            "turn_index": 2,
            "user_query": "静音的 带遥控",
            "rewritten_query": "落地扇 静音 带遥控",
        }
        messages = build_dim1_prompt(history, current)
        print("[INFO] using real dim1 prompt from platform code")
    else:
        messages = [
            {
                "role": "user",
                "content": "请返回严格 JSON: {\"ok\": true, \"echo\": \"hello from judge\"}",
            }
        ]
        print("[INFO] using inline minimal prompt")

    client = Ark(base_url=base_url, api_key=api_key, timeout=60)
    t0 = time.time()
    try:
        completion = client.chat.completions.create(
            model=model_id,
            messages=messages,
            temperature=0.1,
        )
        elapsed = time.time() - t0
        content = completion.choices[0].message.content or ""
        print(f"\n[OK] ARK call succeeded in {elapsed:.2f}s")
        print("-" * 60)
        print("raw response (first 500 chars):")
        print(content[:500])
        print("-" * 60)
        if extract_json:
            parsed = extract_json(content)
            if parsed is None:
                print("[WARN] response is not valid JSON — judge may not follow schema")
                return 2
            print("[OK] response parsed as JSON:")
            for k, v in parsed.items():
                v_str = str(v)
                if len(v_str) > 80:
                    v_str = v_str[:77] + "…"
                print(f"    {k}: {v_str}")
        return 0
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"\n[FAIL] ARK call failed after {elapsed:.2f}s")
        print(f"       {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
