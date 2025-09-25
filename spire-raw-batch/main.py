import os
import sys
import time


def main() -> int:
    log_level = os.getenv("LOG_LEVEL", "INFO")
    print(f"Hello from spire-raw-batch! LOG_LEVEL={log_level}")
    time.sleep(1)
    print("spire-raw-batch completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())

