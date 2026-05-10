try:
    from kg_app.main import main
except ModuleNotFoundError:
    from main import main


if __name__ == "__main__":
    main()
