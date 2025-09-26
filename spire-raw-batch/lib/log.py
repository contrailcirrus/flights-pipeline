"""
Logging utilities.
"""

import logging
import sys
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def format_traceback() -> str:
    """Format current exception traceback as string."""
    return traceback.format_exc()
