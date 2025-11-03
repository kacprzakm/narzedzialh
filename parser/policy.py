import sys
import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

def main():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    attrs = {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            recipient = attrs.get("recipient", "")
            local = recipient.split("@")[0]
            exists = r.exists(f"rcpt:{local}")
            if exists:
                print("action=OK\n")
            else:
                print("action=REJECT User unknown\n")
            sys.stdout.flush()
            attrs = {}
        elif "=" in line:
            k, v = line.split("=", 1)
            attrs[k] = v

if __name__ == "__main__":
    main()
