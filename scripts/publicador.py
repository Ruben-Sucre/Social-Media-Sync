"""Small CLI to integrate with n8n or external orchestrators.

- `--get-next`   -> prints the next processed video path (one line)
- `--mark-posted VIDEO_ID` -> mark the given video as posted in the inventory

These primitives make it easy for a workflow system like n8n to query and mark
videos as posted after successful uploads.
"""
from __future__ import annotations

import argparse
from typing import Optional

from scripts.common import find_next_processed_pending, update_inventory_by_video_id, logger


def cli_get_next() -> Optional[str]:
    nxt = find_next_processed_pending()
    if not nxt:
        return None
    return nxt["path_local"]


def cli_mark_posted(video_id: str) -> bool:
    ok = update_inventory_by_video_id(video_id, {"status_fb": "posted"})
    if ok:
        logger.info("Marked %s as posted", video_id)
    else:
        logger.warning("Could not find %s to mark as posted", video_id)
    return ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--get-next", action="store_true", help="Print next processed video path")
    parser.add_argument("--mark-posted", metavar="VIDEO_ID", help="Mark a video as posted")

    args = parser.parse_args()

    if args.get_next:
        p = cli_get_next()
        if p:
            print(p)
        else:
            # no videos available
            print("")
    elif args.mark_posted:
        ok = cli_mark_posted(args.mark_posted)
        if not ok:
            raise SystemExit(2)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
