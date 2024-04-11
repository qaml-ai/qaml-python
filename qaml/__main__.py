import qaml
import sys
import os
import readline

def main():
    # get api key from environment variable
    api_key = os.environ.get("QAML_API_KEY")
    use_mjpeg = os.environ.get("QAML_USE_MJPEG", "true").lower() == "true"
    if api_key is None:
        print("Please set the QAML_API_KEY environment variable")
        sys.exit(1)
    print("Initializing device driver...")
    client = qaml.Client(api_key=api_key, use_mjpeg=use_mjpeg)
    # if no args, start repl
    if len(sys.argv) == 1:
        while True:
            try:
                command = input("Enter a command: ")
                client.execute(command)
            except EOFError:
                print("")
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        args_str = " ".join(sys.argv[1:])
        print(f"Running command: {args_str}")
        client.execute(args_str)

if __name__ == "__main__":
    main()

