"""Example demonstrating custom description parameter."""

from dataclasses import dataclass

from dataclass_args import build_config


@dataclass
class ServerConfig:
    """Server configuration."""

    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    workers: int = 4


def main():
    """
    Example showing custom ArgumentParser descriptions.

    Run with --help to see the custom description:
        python custom_description_example.py --help
    """

    # Custom description provides context-specific help
    config = build_config(
        ServerConfig,
        description="""
        Server Configuration Tool
        
        Configure the application server with custom host, port, and worker settings.
        The debug flag enables verbose logging for troubleshooting.
        """.strip(),
    )

    print("Server Configuration:")
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Debug: {config.debug}")
    print(f"  Workers: {config.workers}")


if __name__ == "__main__":
    main()
