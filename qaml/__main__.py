import qaml
import sys
import os

def main():
    # get a string of all args
    args_str = " ".join(sys.argv[1:])
    print(f"Running command: {args_str}")
    # get api key from environment variable
    api_key = os.environ.get("QAML_API_KEY")
    if api_key is None:
        print("Please set the QAML_API_KEY environment variable")
        sys.exit(1)
    client = qaml.Client(api_key=api_key)
    client.execute(args_str)

if __name__ == "__main__":
    main()

