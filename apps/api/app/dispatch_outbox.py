"""Queue one bounded batch of pending mail; suitable for a scheduled container job."""

import json
import logging

from app.core.logging import configure_logging
from app.providers.email import dispatch_outbox


def main() -> None:
    configure_logging()
    try:
        queued = dispatch_outbox.run()
    except Exception:
        # Database and broker exception strings can contain credentials or PII.
        logging.getLogger("sbf.mail").error("Outbox dispatch failed; check database and broker connectivity")
        raise SystemExit(1) from None
    print(json.dumps({"queued": queued}))


if __name__ == "__main__":
    main()
