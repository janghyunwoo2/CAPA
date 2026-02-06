import time
import sys

def main():
    print("Log Generator started...", flush=True)
    print(f"Python version: {sys.version}", flush=True)
    
    counter = 1
    while True:
        print(f"Log message #{counter}", flush=True)
        counter += 1
        time.sleep(1)

if __name__ == "__main__":
    main()
