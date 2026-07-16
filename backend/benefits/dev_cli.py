"""Standalone runner for the Benefits agent.

    uv run python -m benefits.dev_cli --member MBR00183 "what would a colonoscopy cost me"
    uv run python -m benefits.dev_cli --member MBR00183 --json "colonoscopy"
    uv run python -m benefits.dev_cli --demo

Runs the deterministic core only -- no LLM, no network, no API key. That is the
point: if the model is unavailable on demo day, this still produces correct,
grounded, four-part answers.
"""

import argparse
import json
import sys

from ..src.agents.benefits import answer_benefits_question, load_members

DEMO_MEMBER = "MBR00183"

DEMO_SCRIPT: list[tuple[str, str, str]] = [
    (DEMO_MEMBER, "not_required", "what would a colonoscopy cost me"),
    ("MBR00125", "not_required", "what would a colonoscopy cost me"),
    ("MBR00125", "not_required", "is depression screening covered"),
    (DEMO_MEMBER, "not_required", "does an MRI need prior authorization"),
    (DEMO_MEMBER, "not_required", "is CPT 99213 covered"),
    (DEMO_MEMBER, "not_required", "is acupuncture covered"),
    (DEMO_MEMBER, "expired", "what would a colonoscopy cost me"),
]


def _render(member_id: str, roi: str, question: str, as_json: bool) -> None:
    answer = answer_benefits_question(question, member_id=member_id, roi_status=roi)

    if as_json:
        print(answer.model_dump_json(indent=2))
        return

    member = load_members()[member_id]
    print(f"\nQ  [{member_id} {member.plan_type}/{member.language_preference} roi={roi}] {question}")
    print(f"A  {answer.answer_text}")
    print(f"   next step: {answer.next_step}")
    if answer.grounded_on:
        print(f"   grounded on: {', '.join(answer.grounded_on)} / {answer.plan_type}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="benefits.dev_cli", description=__doc__)
    p.add_argument("question", nargs="*", help="the coverage question")
    p.add_argument("--member", default=DEMO_MEMBER, help="member id (default: %(default)s)")
    p.add_argument("--roi", default="not_required", help="roi status (try: expired)")
    p.add_argument("--json", action="store_true", help="print the structured card")
    p.add_argument("--demo", action="store_true", help="run the scripted golden path")
    args = p.parse_args(argv)

    if args.demo:
        for member_id, roi, question in DEMO_SCRIPT:
            _render(member_id, roi, question, args.json)
        print()
        return 0

    if not args.question:
        p.error("give a question, or use --demo")

    _render(args.member, args.roi, " ".join(args.question), args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
