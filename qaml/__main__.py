import qaml

def main():
    # get a string of all args
    args_str = " ".join(sys.argv[1:])
    print(f"Running command: {args_str}")
    client = qaml.Client()
    client.execute(args_str)

if __name__ == "__main__":
    main()

