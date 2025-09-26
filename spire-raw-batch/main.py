import sys
import time

from lib import environment


def main() -> int:
    print(f"Hello from spire-raw-batch! LOG_LEVEL={environment.LOG_LEVEL}")
    time.sleep(1)
    print("spire-raw-batch completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())

