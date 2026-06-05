def main():
    print("Hello from ahp-project!")


if __name__ == "__main__":
    main()

    from django.core.management.utils import get_random_secret_key
    print(get_random_secret_key())
