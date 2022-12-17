"""
Tests for aiocasambi
"""
import argparse
import asyncio
import logging
import logging.handlers
import sys
import os

from pprint import pprint, pformat

import yaml
import aiohttp
import async_timeout

sys.path.append(os.path.split(os.path.dirname(sys.argv[0]))[0])

try:
    import aiocasambi
except ModuleNotFoundError as err:
    pprint(sys.path)
    raise err

LOGGER = logging.getLogger(__name__)


def signalling_callback(signal, data):
    """
    Callback function
    """
    LOGGER.info(f"signalling_callback {signal}, {pformat(data)}")


async def get_casambi_controller(
    *,
    email,
    user_password,
    network_password,
    api_key,
    session,
    sslcontext,
    callback,
) -> aiocasambi.Controller:
    """Setup Casambi controller and verify credentials."""
    controller = aiocasambi.Controller(
        email=email,
        user_password=user_password,
        network_password=network_password,
        api_key=api_key,
        websession=session,
        sslcontext=sslcontext,
        callback=callback,
    )

    try:
        with async_timeout.timeout(10):
            await controller.create_session()
        return controller

    except aiocasambi.Unauthorized:
        LOGGER.warning("Connected to casambi but couldn't log in")

    except (asyncio.TimeoutError, aiocasambi.RequestError):
        LOGGER.exception("Error connecting to the Casambi")

    except aiocasambi.AiocasambiException:
        LOGGER.exception("Unknown Casambi communication error occurred")


def parse_config(config_file="casambi.yaml") -> dict:
    """
    Function for parsing yaml configuration file
    """
    result = {}

    if not os.path.isfile(config_file):
        return result  # empty dict

    with open(config_file, "r") as stream:
        result = yaml.safe_load(stream)

    return result


def setup_logger(*, debug=False) -> None:
    """
    Function for setting up the logging
    """
    root = logging.getLogger()
    formatter = logging.Formatter(
        "%(asctime)s %(process)d %(processName)-10s %(name)-8s %(funcName)-8s %(levelname)-8s %(message)s"
    )

    if debug:
        max_bytes = 3 * 10**7
        backup_count = 10
        file_handler = logging.handlers.RotatingFileHandler(
            "casambi.log", "a", max_bytes, backup_count
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    if debug:
        root.setLevel(logging.DEBUG)


async def main(
    *,
    email,
    network_password,
    api_key,
    sslcontext=False,
) -> None:
    """Main function."""
    LOGGER.info("Starting aioCasambi")

    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    websession = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=False), timeout=timeout
    )

    # Login without network password
    controller = await get_casambi_controller(
        email=email,
        user_password=None,
        network_password=network_password,
        api_key=api_key,
        sslcontext=sslcontext,
        session=websession,
        callback=signalling_callback,
    )

    # Login with network password

    if not controller:
        LOGGER.error("Couldn't connect to Casambi controller")
        await websession.close()
        return

    await controller.initialize()

    await controller.start_websockets()

    await controller.stop_websockets()
    await websession.close()


if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument("--email", type=str, required=False)
    PARSER.add_argument("--api_key", type=str, required=False)
    PARSER.add_argument(
        "--user_password",
        type=str,
        required=False,
        help="User password (site password)",
    )
    PARSER.add_argument("--network_password", type=str, required=False)
    PARSER.add_argument("-D", "--debug", action="store_true")
    ARGS = PARSER.parse_args()

    CONFIG = parse_config()

    if ARGS.email:
        CONFIG["email"] = ARGS.email

    if ARGS.user_password:
        CONFIG["user_password"] = ARGS.user_password

    if ARGS.network_password:
        CONFIG["network_password"] = ARGS.network_password

    if ARGS.api_key:
        CONFIG["api_key"] = ARGS.api_key

    if ARGS.debug:
        CONFIG["debug"] = True

    if "debug" not in CONFIG:
        CONFIG["debug"] = False

    setup_logger(debug=CONFIG["debug"])

    LOGGER.debug(f"Configuration: {pformat(CONFIG)}")

    try:
        asyncio.run(
            main(
                email=CONFIG["email"],
                network_password=CONFIG["network_password"],
                api_key=CONFIG["api_key"],
            )
        )
    except KeyboardInterrupt:
        pass
