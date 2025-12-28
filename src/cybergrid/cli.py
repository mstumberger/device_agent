"""Command-line interface for the RT-IoT device agent."""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: List of command-line arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments as namespace object

    Raises:
        SystemExit: If arguments are invalid or --help is requested
    """
    parser = argparse.ArgumentParser(
        prog="cybergrid-agent",
        description="CyberGrid Device Agent - IoT power measurement simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run                              # Run the agent
  %(prog)s run -c config.yaml               # Run with custom config
  %(prog)s run --log-level DEBUG            # Run with debug logging
  %(prog)s --version                        # Show version

MQTT Topics:
  device/{device_id}/status      - Device online/offline status (heartbeat)
  device/{device_id}/measurement - Power measurement readings
        """
    )

    parser.add_argument(
        "-v", "--version",
        action="store_true",
        help="Show version information and exit"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run the device agent",
        description="Start the CyberGrid device agent and begin publishing measurements"
    )
    run_parser.add_argument(
        "-c", "--config",
        type=Path,
        metavar="FILE",
        help="Path to configuration file (default: config.yaml in project root)"
    )
    run_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    run_parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Log output format (default: text)"
    )

    return parser.parse_args(argv)


def setup_logging(level: str, format_type: str) -> None:
    """Configure logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Either 'text' or 'json' format
    """
    log_level = getattr(logging, level.upper())

    if format_type == "json":
        log_format = '{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def show_version() -> None:
    """Display version information."""
    print("CyberGrid Device Agent v0.1.0")
    print("Python IoT power measurement simulator with MQTT support")
    sys.exit(0)


def validate_config_file(config_path: Optional[Path]) -> Path:
    """Validate configuration file path exists and is readable.

    Args:
        config_path: Path to configuration file (or None for default)

    Returns:
        Valid configuration file path

    Raises:
        SystemExit: If configuration file is not found or not readable
    """
    if config_path is None:
        # Use default location
        config_path = Path.cwd() / "config.yaml"

    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        print("Hint: Create a config.yaml file or specify --config <path>", file=sys.stderr)
        sys.exit(1)

    if not config_path.is_file():
        print(f"Error: Configuration path is not a file: {config_path}", file=sys.stderr)
        sys.exit(1)

    return config_path


async def cmd_run(args: argparse.Namespace) -> int:
    """Run the device agent.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    # Import here to avoid circular imports
    from cybergrid.main import DeviceAgent

    setup_logging(args.log_level, args.log_format)

    # Validate configuration file exists
    config_path = validate_config_file(args.config)

    # Determine project root (config file's parent directory)
    project_root = config_path.parent

    # Create and run agent
    agent = DeviceAgent(project_root)

    # Setup signal handlers for graceful shutdown
    def handler() -> None:
        agent._shutdown_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, handler)
    loop.add_signal_handler(signal.SIGTERM, handler)

    try:
        await agent.run()
        return 0
    except KeyboardInterrupt:
        agent.info("Shutdown requested via SIGINT")
        await agent.shutdown()
        return 0
    except Exception as e:
        logging.error(f"Unhandled exception: {e}", exc_info=True)
        return 1


async def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    args = parse_args(argv)

    if args.version:
        show_version()
        return 0

    if args.command != "run":
        print("Error: No command specified. Use 'run' to start the agent.", file=sys.stderr)
        print("Use 'cybergrid-agent --help' for usage information.", file=sys.stderr)
        return 1

    return await cmd_run(args)


def blocking_main() -> None:
    """Synchronous wrapper for CLI entry point."""
    sys_exit = asyncio.run(main())
    raise SystemExit(sys_exit)


if __name__ == "__main__":
    blocking_main()
