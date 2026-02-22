from __future__ import annotations

import argparse
import json
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from app.core.multi_role_ai import (  # noqa: E402
    MultiRoleAIOrchestrator,
    load_roles_from_json,
    render_result_markdown,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-role AI orchestration.")
    parser.add_argument("--task", required=True, help="Main task statement.")
    parser.add_argument("--context", default="", help="Optional context.")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "compact", "precision"],
        help="Execution mode selection.",
    )
    parser.add_argument(
        "--roles",
        default="",
        help="Comma-separated role IDs. Example: planner,implementer,reviewer",
    )
    parser.add_argument(
        "--roles-file",
        default="",
        help="Optional JSON file to override role definitions.",
    )
    parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "json"],
        help="Output format.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    roles = None
    if args.roles_file:
        roles = load_roles_from_json(args.roles_file)

    orchestrator = MultiRoleAIOrchestrator(roles=roles)
    role_ids = [row.strip() for row in args.roles.split(",") if row.strip()] or None

    result = orchestrator.run(
        task=args.task,
        context=args.context,
        mode=args.mode,
        role_ids=role_ids,
    )

    if args.format == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_result_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
