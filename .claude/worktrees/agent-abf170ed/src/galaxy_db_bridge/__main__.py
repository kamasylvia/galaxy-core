import sys

from galaxy_db_bridge.application.cli.commands import main as cli_main


def main():
    exit_code = cli_main()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
