from datetime import date


def main() -> None:
    """Print a greeting containing the current local date."""
    print(f"Hello! Today is {date.today().isoformat()}")


if __name__ == "__main__":
    main()
