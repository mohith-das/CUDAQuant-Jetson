"""CLI entry point for CUDAQuant-Jetson."""
import click


@click.group()
@click.version_option()
def main() -> None:
    """CUDAQuant-Jetson — GPU-accelerated quantitative trading research."""
    pass


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8000, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the web server."""
    import uvicorn
    uvicorn.run(
        "cudaquant.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@main.command()
def version() -> None:
    """Print version and environment info."""
    import platform
    import sys

    from cudaquant import __version__

    click.echo(f"CUDAQuant-Jetson v{__version__}")
    click.echo(f"Python {sys.version}")
    click.echo(f"Platform: {platform.platform()}")
    click.echo(f"Machine: {platform.machine()}")


if __name__ == "__main__":
    main()
